from __future__ import annotations

from app.models.contracts import AnalysisResult, RuleAssessment


RULES = {
    "FQ-001": {
        "title": "利润与经营现金流背离",
        "metrics": ["net_profit_parent_period_change", "operating_cashflow_period_change"],
        "labels": ["归母净利润同比", "经营现金流同比"],
        "limits": [0.0, 0.0],
        "operators": [">", "<"],
        "possible": ["回款节奏或营运资本变化可能影响现金流；仅凭本规则不能确定成因。"],
        "next": ["核对现金流量表、应收账款账龄及期后回款。"],
    },
    "FQ-002": {
        "title": "应收账款增长快于收入",
        "metrics": ["accounts_receivable_period_change", "revenue_period_change"],
        "labels": ["应收账款同比", "营业收入同比"],
        "limits": [0.2],
        "operators": [">"],
        "possible": ["赊销政策或回款时间可能影响应收增速；不能据此认定收入异常。"],
        "next": ["核对信用政策、客户集中度、账龄和期后回款。"],
    },
    "FQ-003": {
        "title": "存货增长快于收入",
        "metrics": ["inventory_period_change", "revenue_period_change"],
        "labels": ["存货同比", "营业收入同比"],
        "limits": [0.2],
        "operators": [">"],
        "possible": ["备货、产品结构或销售节奏可能影响存货增速；需要结合附注确认。"],
        "next": ["核对存货构成、库龄、跌价准备和期后销售。"],
    },
    "FQ-004": {
        "title": "非经常性损益贡献较高",
        "metrics": ["nonrecurring_contribution"],
        "labels": ["非经常性损益贡献率"],
        "limits": [0.3],
        "operators": [">"],
        "possible": ["一次性收益或扣非调整可能影响利润构成；具体项目仍需查附注。"],
        "next": ["核对非经常性损益明细、持续性及主营业务利润。"],
    },
}


def enrich_result(result: AnalysisResult) -> AnalysisResult:
    """Build display explanations from saved facts and calculations without mutating old files."""
    periods = sorted({fact.report_period for fact in result.facts})
    latest = periods[-1] if periods else ""
    calc_map = {(item.report_period, item.metric_code): item for item in result.calculations}
    fact_map = {fact.fact_id: fact for fact in result.facts}
    def fact_inputs(ids: list[str]) -> list[dict]:
        return [{"fact_id": fid, "label": fact_map[fid].metric_name, "period": fact_map[fid].report_period,
                 "value": fact_map[fid].value, "unit": fact_map[fid].unit} for fid in ids if fid in fact_map]
    source = {item.rule_id: item for item in result.rule_assessments}
    assessments: list[RuleAssessment] = []
    for rule_id, spec in RULES.items():
        saved = source.get(rule_id)
        steps = []
        missing = []
        calc_ids = []
        fact_ids = []
        selected = [calc_map.get((latest, key)) for key in spec["metrics"]]
        for key, label, calc in zip(spec["metrics"], spec["labels"], selected):
            if calc is None:
                missing.append(f"{label}：缺少已核验事实或可比完整年报")
            elif calc.result is None:
                missing.append(f"{label}：分母为零，无法计算")
            if calc:
                calc_ids.append(calc.calculation_id)
                fact_ids.extend(calc.input_fact_ids)
        fact_ids = list(dict.fromkeys(fid for fid in fact_ids if fid in fact_map))
        if not missing:
            if rule_id == "FQ-001":
                for calc, label, limit, operator in zip(selected, spec["labels"], spec["limits"], spec["operators"]):
                    value = calc.result
                    steps.append({"label": label, "value": value, "threshold": limit, "operator": operator,
                                  "difference": value - limit, "passed": value > limit if operator == ">" else value < limit,
                                  "unit": "ratio", "formula": calc.formula, "calculation_ids": [calc.calculation_id],
                                  "fact_ids": calc.input_fact_ids, "fact_inputs": fact_inputs(calc.input_fact_ids)})
            else:
                primary = selected[0]
                secondary = selected[1] if len(selected) > 1 else None
                difference = primary.result - secondary.result if secondary else primary.result
                steps.append({"label": "增速差" if secondary else spec["labels"][0], "value": difference,
                              "inputs": [{"label": label, "value": calc.result} for label, calc in zip(spec["labels"], selected)],
                              "threshold": spec["limits"][0], "operator": ">", "difference": difference - spec["limits"][0],
                              "passed": difference > spec["limits"][0], "unit": "ratio",
                              "formula": "前者同比 − 营业收入同比" if secondary else primary.formula,
                              "calculation_ids": [calc.calculation_id for calc in selected], "fact_ids": fact_ids,
                              "fact_inputs": fact_inputs(fact_ids)})
        status = "insufficient" if missing else "triggered" if all(step["passed"] for step in steps) else "clear"
        reason = ("；".join(missing) if missing else "满足全部严格阈值，需进一步核查。" if status == "triggered"
                  else "未同时满足规则的严格阈值。")
        assessments.append(RuleAssessment(rule_id=rule_id, title=spec["title"], status=status, reason=reason,
                                          steps=steps, fact_ids=fact_ids, calculation_ids=calc_ids,
                                          missing_inputs=missing, possible_explanations=spec["possible"],
                                          next_checks=spec["next"]))
    result.rule_assessments = assessments
    return result
