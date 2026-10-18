from __future__ import annotations

from collections import defaultdict

from app.models.contracts import AnomalySignal, FinancialFact, MetricCalculation


def detect_anomaly_signals(facts: list[FinancialFact], calculations: list[MetricCalculation]) -> list[AnomalySignal]:
    facts_by_period: dict[str, dict[str, FinancialFact]] = defaultdict(dict)
    for fact in facts:
        facts_by_period[fact.report_period][fact.metric_code] = fact
    calcs_by_period: dict[str, dict[str, MetricCalculation]] = defaultdict(dict)
    for calculation in calculations:
        calcs_by_period[calculation.report_period][calculation.metric_code] = calculation

    signals: list[AnomalySignal] = []
    for period in facts_by_period:
        calcs = calcs_by_period[period]
        profit_change = calcs.get("net_profit_parent_period_change")
        cfo_change = calcs.get("operating_cashflow_period_change")
        if profit_change and cfo_change and profit_change.result is not None and cfo_change.result is not None and profit_change.result > 0 and cfo_change.result < 0:
            signals.append(AnomalySignal(rule_id="FQ-001", title="利润与经营现金流背离", severity="medium", report_period=period, fact_ids=profit_change.input_fact_ids + cfo_change.input_fact_ids, calculation_ids=[profit_change.calculation_id, cfo_change.calculation_id], interpretation="归母净利润增长而经营活动现金流下降，出现利润—现金流背离信号。", follow_up="核查应收账款账龄、期后回款、收入确认政策及营运资本变化。"))
        receivable_change = calcs.get("accounts_receivable_period_change")
        revenue_change = calcs.get("revenue_period_change")
        if receivable_change and revenue_change and receivable_change.result is not None and revenue_change.result is not None and receivable_change.result > revenue_change.result + 0.2:
            signals.append(AnomalySignal(rule_id="FQ-002", title="应收账款增长快于收入", severity="medium", report_period=period, fact_ids=receivable_change.input_fact_ids + revenue_change.input_fact_ids, calculation_ids=[receivable_change.calculation_id, revenue_change.calculation_id], interpretation="应收账款增速显著高于营业收入增速，收入现金转化效率需要关注。", follow_up="核查主要客户信用政策、账龄结构、集中度和期后回款。"))
        inventory_change = calcs.get("inventory_period_change")
        if inventory_change and revenue_change and inventory_change.result is not None and revenue_change.result is not None and inventory_change.result > revenue_change.result + 0.2:
            signals.append(AnomalySignal(rule_id="FQ-003", title="存货增长快于收入", severity="medium", report_period=period, fact_ids=inventory_change.input_fact_ids + revenue_change.input_fact_ids, calculation_ids=[inventory_change.calculation_id, revenue_change.calculation_id], interpretation="存货增速显著高于营业收入增速，需关注库存周转与减值压力。", follow_up="核查存货构成、库龄、跌价准备和产销匹配情况。"))
        nonrecurring = calcs.get("nonrecurring_contribution")
        if nonrecurring and nonrecurring.result is not None and nonrecurring.result > 0.3:
            signals.append(AnomalySignal(rule_id="FQ-004", title="非经常性损益贡献较高", severity="medium", report_period=period, fact_ids=nonrecurring.input_fact_ids, calculation_ids=[nonrecurring.calculation_id], interpretation="非经常性损益对归母净利润贡献超过 30%，利润可持续性需要审慎评估。", follow_up="核查非经常性损益明细、持续性和与主营业务的关系。"))
    return signals

