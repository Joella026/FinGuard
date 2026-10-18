from __future__ import annotations

from pathlib import Path

from app.models.contracts import ExtractionBatch, FinancialFact, Report, VerificationStatus
from app.services.extraction_store import save_extraction
from app.services.report_store import load_report
from app.tools.fact_extractor import METRICS, extract_financial_facts
from app.tools.pdf_parser import parse_pdf_report


def report_year(report: Report) -> int:
    period = report.report_period.upper()
    if len(period) != 6 or not period[:4].isdigit() or period[4:] not in {"FY", "H1", "Q1", "Q2", "Q3", "Q4"}:
        raise ValueError(f"{report.original_filename} 的报告期间不受支持")
    return int(period[:4])


def _validate_reports(reports: list[Report]) -> list[int]:
    if len(reports) not in {1, 2}:
        raise ValueError("请选择一份报告核验，或两份连续年报进行对比")
    if len(reports) == 1:
        return [report_year(reports[0])]
    if len({item.company_code for item in reports}) != 1:
        raise ValueError("两份报告必须属于同一家公司")
    if len({item.currency for item in reports}) != 1:
        raise ValueError("两份报告的币种必须一致；跨币种金额不能直接对比")
    if any(not item.report_period.upper().endswith("FY") for item in reports):
        raise ValueError("两份报告对比仅支持完整年度报告")
    years = sorted(report_year(item) for item in reports)
    if years[0] == years[1]:
        raise ValueError("不能选择同一年度的重复报告")
    if years[1] != years[0] + 1:
        raise ValueError("必须选择连续两个年度的报告")
    return years


def _missing_fact(report: Report, metric_code: str) -> FinancialFact:
    metric_name, statement_type, _ = METRICS[metric_code]
    return FinancialFact(
        report_id=report.report_id,
        company_code=report.company_code,
        report_period=report.report_period,
        report_year=report_year(report),
        metric_code=metric_code,
        metric_name=metric_name,
        value=None,
        raw_value=None,
        raw_unit="元",
        unit=report.currency,
        statement_type=statement_type,
        source_file=report.original_filename,
        page_number=0,
        source_text="",
        extraction_method="not_found",
        verification_status=VerificationStatus.REVIEW_REQUIRED,
    )


def create_extraction(report_ids: list[str]) -> ExtractionBatch:
    reports = [load_report(report_id) for report_id in report_ids]
    years = _validate_reports(reports)
    reports.sort(key=report_year)
    facts: list[FinancialFact] = []
    issues: list[str] = []

    for report in reports:
        try:
            pages = parse_pdf_report(Path(report.stored_path))
        except Exception as error:
            raise ValueError(f"{report.original_filename} 无法解析为 PDF，请检查文件是否损坏或加密") from error
        extracted = extract_financial_facts(report, pages)
        by_metric = {item.metric_code: item for item in extracted}
        for metric_code in METRICS:
            fact = by_metric.get(metric_code) or _missing_fact(report, metric_code)
            facts.append(fact)
            if fact.value is None:
                issues.append(f"{report.report_period} 未自动找到{fact.metric_name}，需要人工补充或标记暂缺。")
        if not any(str(page["text"]).strip() for page in pages):
            issues.append(f"{report.original_filename} 未解析到可用文本，可能是扫描版 PDF。")

    batch = ExtractionBatch(
        report_ids=[item.report_id for item in reports],
        company_code=reports[0].company_code,
        company_name=reports[0].company_name,
        years=years,
        facts=facts,
        issues=issues,
    )
    save_extraction(batch)
    return batch
