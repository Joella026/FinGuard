from __future__ import annotations

import shutil
import re
import json
import hashlib
from pathlib import Path

import requests
from pypdf import PdfReader
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import DATA_DIR, ROOT_DIR, RUNS_DIR, ensure_directories
from app.models.contracts import (
    AnalysisResult,
    AnalysisRunRequest,
    DemoCase,
    ExtractionBatch,
    ExtractionCreateRequest,
    FactReviewRequest,
    Report,
)
from app.services.analysis import run_analysis, _report_html
from app.services.rule_explanations import enrich_result
from app.services.demo_cases import list_demo_cases, load_demo_case
from app.services.disclosures import DisclosureSearch, import_disclosure, search_disclosures
from app.services.extraction import create_extraction
from app.services.extraction_store import load_extraction, review_fact
from app.services.history import list_history
from app.services.report_store import list_reports, load_report, save_report
from app.tools.audit import sha256_file

ensure_directories()
app = FastAPI(title="FinGuard API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.3.0"}


@app.get("/history")
def history(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return _frontend_index()
    try:
        return JSONResponse([item.model_dump(mode="json") for item in list_history()])
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/api/history")
def history_json():
    try:
        return JSONResponse([item.model_dump(mode="json") for item in list_history()])
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/demo-cases", response_model=list[DemoCase])
def demo_cases() -> list[DemoCase]:
    return list_demo_cases()


@app.post("/demo-cases/{case_id}/load", response_model=ExtractionBatch)
def create_demo_extraction(case_id: str) -> ExtractionBatch:
    try:
        return load_demo_case(case_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/reports", response_model=list[Report])
def reports() -> list[Report]:
    return list_reports()


@app.get("/disclosures/search", response_model=DisclosureSearch)
def disclosures_search(code: str, year_from: int = Query(2024), year_to: int = Query(2026)) -> DisclosureSearch:
    try:
        return search_disclosures(code, year_from, year_to)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ConnectionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


class DisclosureImportRequest(BaseModel):
    company_code: str
    announcement_id: str
    report_year: int


@app.post("/disclosures/import", response_model=Report)
def disclosures_import(request: DisclosureImportRequest) -> Report:
    try:
        return import_disclosure(request.company_code, request.announcement_id, request.report_year)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ConnectionError, OSError, requests.RequestException) as error:
        raise HTTPException(status_code=502, detail=f"公告下载失败：{error}") from error


@app.post("/reports/upload", response_model=Report)
async def upload_report(
    file: UploadFile = File(...),
    company_code: str = Form(""),
    report_period: str = Form(...),
    report_type: str = Form("annual_report"),
    company_name: str | None = Form(None),
    currency: str = Form("CNY"),
) -> Report:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 财务报告")
    name = (company_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写报告主体名称")
    code = company_code.strip().upper()
    if code and (len(code) > 40 or not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", code)):
        raise HTTPException(status_code=400, detail="报告主体标识仅支持字母、数字、点、横线和下划线，最多 40 个字符")
    if not code:
        code = "LOCAL-" + hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:12].upper()
    currency = currency.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(status_code=400, detail="币种须填写三位 ISO 货币代码，例如 CNY、HKD 或 USD")
    period = report_period.strip().upper()
    if len(period) != 6 or not period[:4].isdigit() or period[4:] not in {"FY", "H1", "Q1", "Q2", "Q3", "Q4"}:
        raise HTTPException(status_code=400, detail="报告期间须使用 YYYYFY、YYYYH1 或 YYYYQ1 至 YYYYQ4")
    report = Report(
        company_code=code,
        company_name=name,
        currency=currency,
        report_period=period,
        report_type=report_type,
        original_filename=Path(file.filename or "report.pdf").name,
        stored_path="",
        sha256="",
    )
    safe_name = f"{report.report_id}_{report.original_filename}"
    target = DATA_DIR / "raw_reports" / safe_name
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    if target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="上传的 PDF 是空文件")
    with target.open("rb") as handle:
        valid_pdf = handle.read(5) == b"%PDF-"
    if not valid_pdf:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF")
    try:
        if not PdfReader(str(target)).pages:
            raise ValueError("PDF 没有页面")
    except Exception as error:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="PDF 已损坏、加密或没有可读取的页面") from error
    report.stored_path = str(target)
    report.sha256 = sha256_file(target)
    save_report(report)
    return report


@app.get("/reports/{report_id}/file")
def report_file(report_id: str):
    try:
        report = load_report(report_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    path = Path(report.stored_path).resolve()
    raw_root = (DATA_DIR / "raw_reports").resolve()
    try:
        path.relative_to(raw_root)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="报告文件路径无效") from error
    if not path.exists():
        raise HTTPException(status_code=404, detail="原始报告文件不存在")
    return FileResponse(path, media_type="application/pdf", filename=report.original_filename, content_disposition_type="inline")


@app.post("/extractions", response_model=ExtractionBatch)
def start_extraction(request: ExtractionCreateRequest) -> ExtractionBatch:
    try:
        return create_extraction(request.report_ids)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"PDF 解析失败：{error}") from error


@app.get("/extractions/{extraction_id}", response_model=ExtractionBatch)
def get_extraction(extraction_id: str) -> ExtractionBatch:
    try:
        return load_extraction(extraction_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.patch("/extractions/{extraction_id}/facts/{fact_id}", response_model=ExtractionBatch)
def update_fact(extraction_id: str, fact_id: str, request: FactReviewRequest) -> ExtractionBatch:
    try:
        return review_fact(extraction_id, fact_id, request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/analysis/runs", response_model=AnalysisResult)
def create_analysis_run(request: AnalysisRunRequest) -> AnalysisResult:
    try:
        return run_analysis(request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"分析失败：{error}") from error


def _run_file(run_id: str, filename: str) -> Path:
    path = RUNS_DIR / run_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="未找到运行记录或输出文件")
    return path


@app.get("/analysis/runs/{run_id}")
def get_run(run_id: str):
    result = AnalysisResult.model_validate(json.loads(_run_file(run_id, "final_result.json").read_text(encoding="utf-8")))
    return JSONResponse(enrich_result(result).model_dump(mode="json"))


@app.get("/analysis/runs/{run_id}/facts")
def get_facts(run_id: str):
    return FileResponse(_run_file(run_id, "extracted_facts.json"), media_type="application/json")


@app.get("/analysis/runs/{run_id}/signals")
def get_signals(run_id: str):
    return FileResponse(_run_file(run_id, "anomaly_signals.json"), media_type="application/json")


@app.get("/analysis/runs/{run_id}/evidence")
def get_evidence(run_id: str):
    return FileResponse(_run_file(run_id, "evidence_links.json"), media_type="application/json")


@app.get("/analysis/runs/{run_id}/report")
def get_report(run_id: str):
    result = AnalysisResult.model_validate(json.loads(_run_file(run_id, "final_result.json").read_text(encoding="utf-8")))
    return HTMLResponse(_report_html(result))


FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


def _frontend_index():
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise HTTPException(status_code=503, detail="前端尚未构建，请先运行 npm run build")
    return FileResponse(index)


@app.get("/", include_in_schema=False)
def frontend_home():
    return _frontend_index()


@app.get("/review/{extraction_id}", include_in_schema=False)
def frontend_review(extraction_id: str):
    return _frontend_index()


@app.get("/analysis/{run_id}", include_in_schema=False)
def frontend_analysis(run_id: str):
    return _frontend_index()
