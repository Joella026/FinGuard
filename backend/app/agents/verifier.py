from __future__ import annotations

from app.models.contracts import AnomalySignal, FinancialFact, MetricCalculation


def verify_result(facts: list[FinancialFact], calculations: list[MetricCalculation], signals: list[AnomalySignal]) -> list[str]:
    """Return human-review items; never silently upgrades uncertain extraction to verified."""
    issues: list[str] = []
    fact_ids = {fact.fact_id for fact in facts}
    for fact in facts:
        if not fact.source_text or fact.page_number < 1:
            issues.append(f"事实 {fact.fact_id} 缺少可定位证据。")
    for calculation in calculations:
        missing = set(calculation.input_fact_ids) - fact_ids
        if missing:
            issues.append(f"计算 {calculation.calculation_id} 引用了不存在的事实：{sorted(missing)}")
    for signal in signals:
        missing = set(signal.fact_ids) - fact_ids
        if missing:
            issues.append(f"风险信号 {signal.signal_id} 缺少事实支撑：{sorted(missing)}")
    return issues

