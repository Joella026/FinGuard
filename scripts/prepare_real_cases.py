"""Register and audit the two local competition cases against human-reviewed facts."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import DATA_DIR, RUNS_DIR, ensure_directories  # noqa: E402
from app.models.contracts import AnalysisRunRequest, FactReviewRequest, Report  # noqa: E402
from app.services.analysis import run_analysis  # noqa: E402
from app.services.extraction import create_extraction  # noqa: E402
from app.services.extraction_store import load_extraction, review_fact  # noqa: E402
from app.services.report_store import list_reports, save_report  # noqa: E402


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register(case: dict, report_spec: dict) -> Report:
    source = ROOT / report_spec["source_path"]
    if not source.is_file():
        raise FileNotFoundError(f"缺少来源年报：{source}，来源链接：{report_spec['source_url']}")
    if file_hash(source) != report_spec["sha256"]:
        raise ValueError(f"来源年报哈希不符：{source}")
    year = report_spec["year"]
    existing = next((item for item in list_reports() if item.company_code == case["company_code"] and item.report_period == f"{year}FY" and item.sha256 == report_spec["sha256"]), None)
    if existing:
        if report_spec["source_url"] and not existing.source_url:
            existing.source_url = report_spec["source_url"]
            save_report(existing)
        return existing
    report = Report(
        company_code=case["company_code"],
        company_name=case["company_name"],
        report_period=f"{year}FY",
        report_type="annual_report",
        original_filename=source.name,
        stored_path="",
        sha256=report_spec["sha256"],
        source_url=report_spec["source_url"],
    )
    target = DATA_DIR / "raw_reports" / f"{report.report_id}_{source.name}"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    report.stored_path = str(target)
    save_report(report)
    return report


def prepare_case(case: dict) -> None:
    reports = [register(case, spec) for spec in case["reports"]]
    report_ids = [item.report_id for item in reports]
    existing = None
    for path in (DATA_DIR / "extractions").glob("*.json"):
        batch = load_extraction(path.stem)
        if batch.report_ids == report_ids:
            existing = batch
            break
    batch = existing or create_extraction(report_ids)
    expected = {(spec["year"], code): answer for spec in case["reports"] for code, answer in spec["facts"].items()}
    if len(batch.facts) != 12:
        raise ValueError(f"{case['company_name']} 预期 12 项事实，实际 {len(batch.facts)} 项")
    for fact in batch.facts:
        raw, unit, page = expected[(fact.report_year, fact.metric_code)]
        if fact.raw_value is None or not math.isclose(fact.raw_value, raw, rel_tol=0, abs_tol=0.005) or fact.raw_unit != unit or fact.page_number != page or not fact.source_text:
            raise ValueError(f"标准答案不符：{case['company_name']} {fact.report_year} {fact.metric_code}")
        if fact.verification_status != "verified":
            batch = review_fact(batch.extraction_id, fact.fact_id, FactReviewRequest(action="verify", reason="与年报原文、单位和标准答案逐项核对"))
    existing_run = next((path for path in RUNS_DIR.glob("*/manifest.json") if json.loads(path.read_text(encoding="utf-8")).get("extraction_id") == batch.extraction_id), None)
    if existing_run:
        run_id = existing_run.parent.name
    else:
        result = run_analysis(AnalysisRunRequest(extraction_id=batch.extraction_id))
        run_id = result.run.run_id
    print(f"{case['company_name']}: 12/12 facts verified, review={batch.extraction_id}, analysis={run_id}")


def main() -> None:
    ensure_directories()
    catalog = json.loads((ROOT / "data" / "benchmark" / "real_cases.json").read_text(encoding="utf-8"))
    for case in catalog["cases"]:
        prepare_case(case)


if __name__ == "__main__":
    main()
