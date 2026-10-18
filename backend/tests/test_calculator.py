from app.models.contracts import FinancialFact
from app.tools.calculator import calculate_financial_metrics


def fact(period: str, code: str, value: float) -> FinancialFact:
    return FinancialFact(report_id="report", company_code="000001.SZ", report_period=period, metric_code=code, metric_name=code, value=value, source_file="sample.pdf", page_number=1, source_text="evidence")


def test_calculates_period_change_and_quality_metrics():
    facts = [
        fact("2024FY", "revenue", 100), fact("2025FY", "revenue", 120),
        fact("2024FY", "net_profit_parent", 10), fact("2025FY", "net_profit_parent", 15),
        fact("2025FY", "operating_cashflow", 12), fact("2025FY", "deducted_net_profit", 9),
    ]
    results = calculate_financial_metrics(facts)
    by_code = {item.metric_code: item for item in results if item.report_period == "2025FY"}
    assert by_code["revenue_period_change"].result == 0.2
    assert by_code["net_margin"].result == 0.125
    assert by_code["cfo_to_net_profit"].result == 0.8
    assert by_code["nonrecurring_contribution"].result == 0.4


def test_does_not_compare_different_companies_or_incomparable_periods():
    facts = [
        FinancialFact(report_id="a", company_code="A", report_period="2024FY", metric_code="revenue", metric_name="revenue", value=100, source_file="a.pdf", page_number=1, source_text="evidence"),
        FinancialFact(report_id="b", company_code="B", report_period="2025FY", metric_code="revenue", metric_name="revenue", value=200, source_file="b.pdf", page_number=1, source_text="evidence"),
        FinancialFact(report_id="c", company_code="A", report_period="2025H1", metric_code="revenue", metric_name="revenue", value=60, source_file="c.pdf", page_number=1, source_text="evidence"),
    ]
    assert not [item for item in calculate_financial_metrics(facts) if item.metric_code == "revenue_period_change"]

