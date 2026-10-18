from __future__ import annotations

from collections import defaultdict

from app.models.contracts import FinancialFact, MetricCalculation


def _period_key(period: str) -> tuple[int, int]:
    digits = "".join(char for char in period if char.isdigit())
    year = int(digits[:4]) if len(digits) >= 4 else 0
    quarter = 4 if any(token in period.upper() for token in ("FY", "Q4", "年度", "年报")) else 2 if "H1" in period.upper() or "半年" in period or "Q2" in period.upper() else 1 if "Q1" in period.upper() or "一季" in period else 3 if "Q3" in period.upper() or "三季" in period else 0
    return year, quarter


def _fact_groups(facts: list[FinancialFact]) -> dict[tuple[str, str, str], list[FinancialFact]]:
    grouped: dict[tuple[str, str, str], list[FinancialFact]] = defaultdict(list)
    for fact in facts:
        if fact.value is not None:
            grouped[(fact.company_code, fact.scope, fact.metric_code)].append(fact)
    for items in grouped.values():
        items.sort(key=lambda item: _period_key(item.report_period))
    return grouped


def calculate_financial_metrics(facts: list[FinancialFact]) -> list[MetricCalculation]:
    grouped = _fact_groups(facts)
    calculations: list[MetricCalculation] = []
    for (_, _, metric), items in grouped.items():
        for current, previous in zip(items[1:], items):
            current_year, current_part = _period_key(current.report_period)
            previous_year, previous_part = _period_key(previous.report_period)
            if current_part != 4 or previous_part != 4 or current_year != previous_year + 1:
                continue
            if current.report_period == previous.report_period:
                continue
            result = None if previous.value == 0 else (current.value - previous.value) / abs(previous.value)
            calculations.append(MetricCalculation(metric_code=f"{metric}_period_change", metric_name=f"{current.metric_name}变化率", report_period=current.report_period, formula="(current - prior) / abs(prior)", input_fact_ids=[current.fact_id, previous.fact_id], result=result, note=f"对比期间：{previous.report_period}"))

    for period in sorted({fact.report_period for fact in facts}, key=_period_key):
        by_metric = {fact.metric_code: fact for fact in facts if fact.report_period == period and fact.value is not None}
        revenue = by_metric.get("revenue")
        net_profit = by_metric.get("net_profit_parent")
        cashflow = by_metric.get("operating_cashflow")
        deducted = by_metric.get("deducted_net_profit")
        if revenue and net_profit:
            calculations.append(MetricCalculation(metric_code="net_margin", metric_name="净利率", report_period=period, formula="net_profit / revenue", input_fact_ids=[net_profit.fact_id, revenue.fact_id], result=None if revenue.value == 0 else net_profit.value / revenue.value))
        if cashflow and net_profit:
            calculations.append(MetricCalculation(metric_code="cfo_to_net_profit", metric_name="经营现金流/归母净利润", report_period=period, formula="operating_cashflow / net_profit", input_fact_ids=[cashflow.fact_id, net_profit.fact_id], result=None if net_profit.value == 0 else cashflow.value / net_profit.value))
        if deducted and net_profit:
            calculations.append(MetricCalculation(metric_code="nonrecurring_contribution", metric_name="非经常性损益贡献率", report_period=period, formula="(net_profit - deducted_net_profit) / net_profit", input_fact_ids=[net_profit.fact_id, deducted.fact_id], result=None if net_profit.value == 0 else (net_profit.value - deducted.value) / net_profit.value))
    return calculations

