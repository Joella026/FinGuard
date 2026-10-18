from app.models.contracts import FinancialFact
from app.tools.calculator import calculate_financial_metrics
from app.tools.rules import detect_anomaly_signals


def make_fact(period: str, code: str, value: float) -> FinancialFact:
    return FinancialFact(report_id="report", company_code="000001.SZ", report_period=period, metric_code=code, metric_name=code, value=value, source_file="sample.pdf", page_number=1, source_text="evidence")


def test_detects_profit_cashflow_divergence():
    facts = [
        make_fact("2024FY", "net_profit_parent", 10), make_fact("2025FY", "net_profit_parent", 20),
        make_fact("2024FY", "operating_cashflow", 20), make_fact("2025FY", "operating_cashflow", 10),
    ]
    signals = detect_anomaly_signals(facts, calculate_financial_metrics(facts))
    assert any(signal.rule_id == "FQ-001" for signal in signals)


def test_detects_all_four_rules_and_has_clean_case():
    risky = [
        make_fact("2024FY", "revenue", 100), make_fact("2025FY", "revenue", 110),
        make_fact("2024FY", "net_profit_parent", 10), make_fact("2025FY", "net_profit_parent", 15),
        make_fact("2024FY", "operating_cashflow", 10), make_fact("2025FY", "operating_cashflow", 5),
        make_fact("2024FY", "accounts_receivable", 10), make_fact("2025FY", "accounts_receivable", 15),
        make_fact("2024FY", "inventory", 10), make_fact("2025FY", "inventory", 14),
        make_fact("2025FY", "deducted_net_profit", 9),
    ]
    assert {item.rule_id for item in detect_anomaly_signals(risky, calculate_financial_metrics(risky))} == {"FQ-001", "FQ-002", "FQ-003", "FQ-004"}

    clean = [
        make_fact("2024FY", "revenue", 100), make_fact("2025FY", "revenue", 110),
        make_fact("2024FY", "net_profit_parent", 10), make_fact("2025FY", "net_profit_parent", 11),
        make_fact("2024FY", "operating_cashflow", 10), make_fact("2025FY", "operating_cashflow", 11),
        make_fact("2024FY", "accounts_receivable", 10), make_fact("2025FY", "accounts_receivable", 11),
        make_fact("2024FY", "inventory", 10), make_fact("2025FY", "inventory", 11),
        make_fact("2025FY", "deducted_net_profit", 10.5),
    ]
    assert detect_anomaly_signals(clean, calculate_financial_metrics(clean)) == []

