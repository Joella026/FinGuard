from app.models.contracts import AgentRun, AnalysisResult, FinancialFact
from app.services.analysis import _report_html
from app.services.rule_explanations import enrich_result
from app.tools.calculator import calculate_financial_metrics
from app.tools.rules import detect_anomaly_signals


def fact(period: str, metric: str, value: float, source: str = "annual.pdf") -> FinancialFact:
    return FinancialFact(report_id="r", company_code="000001", report_period=period, metric_code=metric,
                         metric_name=metric, value=value, source_file=source, page_number=8, source_text="原文 <script>x</script>")


def build(values: dict[str, dict[str, float]]) -> AnalysisResult:
    facts = [fact(period, metric, value) for period, metrics in values.items() for metric, value in metrics.items()]
    calculations = calculate_financial_metrics(facts)
    return enrich_result(AnalysisResult(run=AgentRun(report_ids=["r"], company_code="000001"), facts=facts,
                                        calculations=calculations, signals=detect_anomaly_signals(facts, calculations),
                                        report_url="/report"))


def test_four_rules_have_numeric_steps_and_fact_links():
    result = build({"2024FY": {"revenue": 100, "net_profit_parent": 10, "operating_cashflow": 20,
                                "accounts_receivable": 10, "inventory": 10},
                    "2025FY": {"revenue": 110, "net_profit_parent": 15, "deducted_net_profit": 9,
                                "operating_cashflow": 10, "accounts_receivable": 15, "inventory": 14}})
    assert all(item.status == "triggered" for item in result.rule_assessments)
    assert [round(item.steps[-1]["difference"], 2) for item in result.rule_assessments] == [-0.5, 0.2, 0.1, 0.1]
    assert all(item.fact_ids and item.calculation_ids and item.next_checks for item in result.rule_assessments)
    assert all(item.steps[-1]["passed"] for item in result.rule_assessments)


def test_single_report_zero_denominator_and_missing_are_insufficient():
    result = build({"2026Q1": {"revenue": 100, "net_profit_parent": 0, "deducted_net_profit": 5,
                                "operating_cashflow": 9}})
    assert all(item.status == "insufficient" for item in result.rule_assessments)
    assert "分母为零" in result.rule_assessments[-1].reason
    assert result.rule_assessments[-1].fact_ids


def test_clear_rules_and_escaped_report():
    result = build({"2024FY": {"revenue": 100, "net_profit_parent": 10, "operating_cashflow": 10,
                                "accounts_receivable": 10, "inventory": 10},
                    "2025FY": {"revenue": 110, "net_profit_parent": 11, "deducted_net_profit": 10,
                                "operating_cashflow": 11, "accounts_receivable": 11, "inventory": 11}})
    assert all(item.status == "clear" for item in result.rule_assessments)
    output = _report_html(result)
    assert "<script>" not in output and "&lt;script&gt;" in output
    assert "未触发 4 项" in output
