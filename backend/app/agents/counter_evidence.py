from __future__ import annotations

from app.models.contracts import AnomalySignal, MetricCalculation


def add_counter_evidence(signals: list[AnomalySignal], calculations: list[MetricCalculation]) -> list[AnomalySignal]:
    by_period = {(item.report_period, item.metric_code): item for item in calculations}
    for signal in signals:
        cfo_quality = by_period.get((signal.report_period, "cfo_to_net_profit"))
        if cfo_quality and cfo_quality.result is not None and cfo_quality.result >= 1:
            signal.counter_evidence.append("经营现金流/归母净利润不低于 1，部分缓解了利润现金转化风险。")
        net_margin = by_period.get((signal.report_period, "net_margin"))
        if net_margin and net_margin.result is not None and net_margin.result > 0:
            signal.counter_evidence.append("当期净利率为正，仍需结合行业与业务背景做进一步判断。")
    return signals

