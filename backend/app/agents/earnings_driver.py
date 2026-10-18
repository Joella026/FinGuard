from __future__ import annotations

from app.models.contracts import MetricCalculation


def build_earnings_driver_tree(calculations: list[MetricCalculation]) -> list[dict[str, object]]:
    """Produces a transparent, numeric driver outline; GPT may only describe it later."""
    drivers: list[dict[str, object]] = []
    labels = {
        "revenue_period_change": "营业收入变化",
        "net_profit_parent_period_change": "归母净利润变化",
        "deducted_net_profit_period_change": "扣非净利润变化",
        "nonrecurring_contribution": "非经常性损益贡献率",
        "net_margin": "净利率",
    }
    for calculation in calculations:
        if calculation.metric_code in labels and calculation.result is not None:
            drivers.append({"period": calculation.report_period, "driver": labels[calculation.metric_code], "value": calculation.result, "calculation_id": calculation.calculation_id})
    return drivers

