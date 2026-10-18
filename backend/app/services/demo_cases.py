from __future__ import annotations

import json

from app.config import DATA_DIR
from app.models.contracts import DemoCase, ExtractionBatch, ExtractionStatus, FinancialFact, StatementType, VerificationStatus
from app.services.extraction_store import save_extraction
from app.services.extraction import create_extraction
from app.services.report_store import list_reports


DEMO_CASE = DemoCase(
    case_id="synthetic-manufacturing-2024-2025",
    name="制造业利润质量演示",
    company_code="DEMO001",
    company_name="演示制造股份",
    years=[2024, 2025],
    description="合成数据，仅用于体验核验、计算、异常识别与证据回溯流程。",
)

REAL_CASES = [
    DemoCase(case_id="midea-2024-2025", name="美的集团真实财报", company_code="000333", company_name="美的集团", years=[2024, 2025], description="两份年度报告，先核验 12 项财务事实，再查看确定性分析。", synthetic=False),
    DemoCase(case_id="moutai-2024-2025", name="贵州茅台真实财报", company_code="600519", company_name="贵州茅台", years=[2024, 2025], description="备用真实案例，包含完整原始 PDF 与证据页码。", synthetic=False),
]

VALUES = {
    2024: {
        "revenue": 10_000_000_000,
        "net_profit_parent": 600_000_000,
        "deducted_net_profit": 560_000_000,
        "operating_cashflow": 700_000_000,
        "accounts_receivable": 1_000_000_000,
        "inventory": 900_000_000,
    },
    2025: {
        "revenue": 11_000_000_000,
        "net_profit_parent": 780_000_000,
        "deducted_net_profit": 430_000_000,
        "operating_cashflow": 500_000_000,
        "accounts_receivable": 1_450_000_000,
        "inventory": 1_200_000_000,
    },
}

METADATA = {
    "revenue": ("营业收入", StatementType.INCOME),
    "net_profit_parent": ("归属于上市公司股东的净利润", StatementType.INCOME),
    "deducted_net_profit": ("扣除非经常性损益后的净利润", StatementType.INCOME),
    "operating_cashflow": ("经营活动产生的现金流量净额", StatementType.CASHFLOW),
    "accounts_receivable": ("应收账款", StatementType.BALANCE),
    "inventory": ("存货", StatementType.BALANCE),
}


def list_demo_cases() -> list[DemoCase]:
    registered = {(report.company_code, report.report_period, report.sha256) for report in list_reports()}
    available = [case for case in REAL_CASES if len(_real_case_reports(case.case_id)) == 2 and all(
        (case.company_code, f"{spec['year']}FY", spec["sha256"]) in registered
        for spec in _real_case_reports(case.case_id)
    )]
    return available + [DEMO_CASE]


def _real_case_reports(case_id: str) -> list[dict]:
    benchmark = DATA_DIR / "benchmark" / "real_cases.json"
    if not benchmark.exists():
        return []
    cases = json.loads(benchmark.read_text(encoding="utf-8"))["cases"]
    return next((case["reports"] for case in cases if case["case_id"] == case_id), [])


def load_demo_case(case_id: str) -> ExtractionBatch:
    real_case = next((case for case in REAL_CASES if case.case_id == case_id), None)
    if real_case:
        reports = list_reports()
        selected = []
        for spec in _real_case_reports(case_id):
            year = spec["year"]
            match = next((report for report in reports if report.company_code == real_case.company_code and report.report_period == f"{year}FY" and report.sha256 == spec["sha256"]), None)
            if match is None:
                raise FileNotFoundError(f"{real_case.company_name} {year} 年报尚未登记")
            selected.append(match.report_id)
        if len(selected) != 2:
            raise FileNotFoundError(f"{real_case.company_name} 的两份案例年报尚未准备完成")
        return create_extraction(selected)
    if case_id != DEMO_CASE.case_id:
        raise FileNotFoundError(f"未找到演示案例 {case_id}")
    facts: list[FinancialFact] = []
    for year in DEMO_CASE.years:
        for index, (metric_code, value) in enumerate(VALUES[year].items(), start=1):
            metric_name, statement_type = METADATA[metric_code]
            facts.append(
                FinancialFact(
                    report_id=f"demo-{year}",
                    company_code=DEMO_CASE.company_code,
                    report_period=f"{year}FY",
                    report_year=year,
                    metric_code=metric_code,
                    metric_name=metric_name,
                    value=value,
                    raw_value=value / 100_000_000,
                    raw_unit="亿元",
                    statement_type=statement_type,
                    source_file=f"演示制造股份{year}年年度报告（合成）.pdf",
                    page_number=20 + index,
                    source_text=f"合成演示证据：{metric_name} {value / 100_000_000:.2f} 亿元。",
                    extraction_method="demo_fixture",
                    verification_status=VerificationStatus.VERIFIED,
                    review_note="内置演示标准答案",
                )
            )
    batch = ExtractionBatch(
        report_ids=["demo-2024", "demo-2025"],
        company_code=DEMO_CASE.company_code,
        company_name=DEMO_CASE.company_name,
        years=DEMO_CASE.years,
        status=ExtractionStatus.READY,
        facts=facts,
        issues=["当前为合成演示数据，正式参赛前请替换为团队核验过的真实上市公司案例。"],
    )
    save_extraction(batch)
    return batch
