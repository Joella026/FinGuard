import pytest

from app.models.contracts import ExtractionBatch, ExtractionStatus, Report
from app.services.analysis import _rule_assessments
from app.services import extraction
from app.services.extraction import _validate_reports
from app.tools.fact_extractor import extract_financial_facts


def report(period: str = "2025FY") -> Report:
    return Report(
        company_code="000001.SZ",
        report_period=period,
        report_type="annual_report",
        original_filename="sample.pdf",
        stored_path="sample.pdf",
        sha256="test",
    )


def test_preserves_negative_sign_and_parentheses():
    header = "主要会计数据\n单位：元\n2025年 2024年\n"
    footer = "\n经营活动产生的现金流量净额 5 6"
    negative = extract_financial_facts(report(), [{"page_number": 1, "text": header + "营业收入 -123.00 120" + footer}])
    parentheses = extract_financial_facts(report(), [{"page_number": 1, "text": header + "营业收入 (123.00) 120" + footer}])
    assert negative[0].value == -123
    assert parentheses[0].value == -123


def test_uses_nearby_declared_unit():
    text = "主要会计数据\n单位：万元\n2025年 2024年\n营业收入 123.00 100\n经营活动产生的现金流量净额 5 6"
    facts = extract_financial_facts(report(), [{"page_number": 1, "text": text}])
    assert facts[0].raw_unit == "万元"
    assert facts[0].raw_value == 123
    assert facts[0].value == 1_230_000


def test_selects_current_year_consolidated_amount_and_thousand_unit():
    pages = [
        {"page_number": 9, "text": "主要会计数据\n2025年 2024年\n营业收入（千元） 456,451,731 407,149,600\n归属于上市公司股东的扣除非经常性损\n益的净利润（千元） 41,267,233 35,741,418\n经营活动产生的现金流量净额（千元） 53,345,930 60,511,572"},
        {"page_number": 100, "text": "合并及公司资产负债表\n2025年12月31日\n(除特别注明外，金额单位为人民币千元)\n合并 合并 公司 公司\n应收账款 四(5) 40,450,097 35,798,974 - -\n存货 四(11) 64,628,834 63,339,188 - -"},
    ]
    pages = [{"page_number": n, "text": ""} for n in range(1, 9)] + pages[:1] + [{"page_number": n, "text": ""} for n in range(10, 100)] + pages[1:]
    facts = extract_financial_facts(report(), pages)
    by_metric = {fact.metric_code: fact for fact in facts}
    assert by_metric["revenue"].value == 456_451_731_000
    assert by_metric["deducted_net_profit"].value == 41_267_233_000
    assert by_metric["accounts_receivable"].value == 40_450_097_000
    assert by_metric["inventory"].page_number == 100


def test_rejects_different_companies_and_nonconsecutive_years():
    first = report("2023FY")
    second = report("2025FY")
    with pytest.raises(ValueError, match="连续"):
        _validate_reports([first, second])
    second.report_period = "2024FY"
    second.company_code = "000002.SZ"
    with pytest.raises(ValueError, match="同一家公司"):
        _validate_reports([first, second])


@pytest.mark.parametrize("period", ["2025FY", "2025H1", "2025Q1", "2025Q3"])
def test_single_report_can_be_verified(period):
    assert _validate_reports([report(period)]) == [2025]


def test_two_reports_still_require_full_annual_periods():
    with pytest.raises(ValueError, match="年度报告"):
        _validate_reports([report("2024FY"), report("2025H1")])


def test_single_report_cross_year_rules_are_insufficient():
    batch = ExtractionBatch(report_ids=["one"], company_code="000001", years=[2025], facts=[])
    assessments = _rule_assessments(batch, set())
    assert all(item.status == "insufficient" for item in assessments[:3])


def test_blank_pdf_requires_review(monkeypatch):
    reports = [report("2024FY"), report("2025FY")]
    reports[0].report_id = "one"
    reports[1].report_id = "two"
    monkeypatch.setattr(extraction, "load_report", lambda report_id: reports[0] if report_id == "one" else reports[1])
    monkeypatch.setattr(extraction, "parse_pdf_report", lambda path: [{"page_number": 1, "text": ""}])
    monkeypatch.setattr(extraction, "save_extraction", lambda batch: None)
    batch = extraction.create_extraction(["one", "two"])
    assert batch.status == ExtractionStatus.REVIEW_REQUIRED
    assert all(fact.value is None for fact in batch.facts)
    assert any("扫描版" in issue for issue in batch.issues)
