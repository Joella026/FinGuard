from __future__ import annotations

import hashlib
import html
from datetime import UTC, datetime

from app.agents.counter_evidence import add_counter_evidence
from app.agents.earnings_driver import build_earnings_driver_tree
from app.agents.narrative import NarrativeGenerationError, generate_verified_narrative
from app.agents.verifier import verify_result
from app.config import OPENAI_MODEL, ROOT_DIR, RUNS_DIR
from app.models.contracts import (
    AgentRun,
    AnalysisResult,
    AnalysisRunRequest,
    EvidenceLink,
    ExtractionBatch,
    RuleAssessment,
    VerificationStatus,
)
from app.services.extraction_store import load_extraction
from app.services.ledger import persist_run
from app.services.rule_explanations import enrich_result
from app.tools.audit import append_tool_log, git_commit, write_json
from app.tools.calculator import calculate_financial_metrics
from app.tools.rules import detect_anomaly_signals


RULE_REQUIREMENTS = {
    "FQ-001": ("利润与经营现金流背离", {"net_profit_parent", "operating_cashflow"}, True),
    "FQ-002": ("应收账款增长快于收入", {"accounts_receivable", "revenue"}, True),
    "FQ-003": ("存货增长快于收入", {"inventory", "revenue"}, True),
    "FQ-004": ("非经常性损益贡献较高", {"net_profit_parent", "deducted_net_profit"}, False),
}


def _rule_assessments(batch: ExtractionBatch, triggered_ids: set[str]) -> list[RuleAssessment]:
    latest_year = max(batch.years)
    available = {
        (fact.report_year, fact.metric_code)
        for fact in batch.facts
        if fact.verification_status == VerificationStatus.VERIFIED and fact.value is not None
    }
    assessments: list[RuleAssessment] = []
    for rule_id, (title, metrics, needs_two_years) in RULE_REQUIREMENTS.items():
        if needs_two_years and len(batch.report_ids) < 2:
            assessments.append(RuleAssessment(rule_id=rule_id, title=title, status="insufficient", reason="仅核验一份报告，缺少上年完整年报，无法判断跨年变化。"))
            continue
        required_years = batch.years if needs_two_years else [latest_year]
        missing = [f"{year} {metric}" for year in required_years for metric in metrics if (year, metric) not in available]
        if missing:
            assessments.append(RuleAssessment(rule_id=rule_id, title=title, status="insufficient", reason="缺少核验数据，无法判断。"))
        elif rule_id in triggered_ids:
            assessments.append(RuleAssessment(rule_id=rule_id, title=title, status="triggered", reason="达到项目预设核查阈值。"))
        else:
            assessments.append(RuleAssessment(rule_id=rule_id, title=title, status="clear", reason="本次数据未触发项目预设规则。"))
    return assessments


def _deterministic_summary(batch: ExtractionBatch, signal_count: int, insufficient_count: int) -> str:
    periods = "、".join(sorted({fact.report_period for fact in batch.facts}))
    company = batch.company_name or batch.company_code
    result = f"本次分析识别出 {signal_count} 项需要进一步核查的财务信号。" if signal_count else "本次分析未触发已有异常规则。"
    limitation = f"另有 {insufficient_count} 项规则因数据不足无法判断。" if insufficient_count else "四项规则均已完成判断。"
    return f"已对 {company} {periods} 的已核验数据完成确定性计算。{result}{limitation}结果仅用于辅助核验，不构成投资建议。"


def _report_html(result: AnalysisResult) -> str:
    result = enrich_result(result)
    esc = lambda value: html.escape(str(value))
    def pct(value: float | None) -> str:
        return "无法计算" if value is None else f"{value * 100:.2f}%"
    def step_facts(step: dict) -> str:
        return esc("；".join(f"{fact['period']} {fact['label']} {fact['value']:,.2f} {fact['unit']}" for fact in step["fact_inputs"]))
    status_names = {"triggered": "需要关注", "clear": "未触发", "insufficient": "无法判断"}
    counts = {key: sum(item.status == key for item in result.rule_assessments) for key in status_names}
    period_label = "、".join(sorted({f.report_period for f in result.facts}))
    facts = "".join(
        "<tr>"
        f"<td>{html.escape(f.report_period)}</td><td>{html.escape(f.metric_name)}</td>"
        f"<td>{f.value:,.2f} {esc(f.unit)}</td><td>{html.escape(f.source_file)} P.{f.page_number}</td>"
        f"<td>{html.escape(f.source_text)}</td><td>{esc('; '.join(f'{r.previous_value} → {r.new_value}：{r.reason}' for r in f.revisions) or '无修改')}</td></tr>"
        for f in result.facts
        if f.value is not None
    )
    calculations = "".join(
        "<tr>"
        f"<td>{html.escape(item.report_period)}</td><td>{html.escape(item.metric_name)}</td>"
        f"<td>{'无法计算' if item.result is None else f'{item.result:.2f} 倍' if item.metric_code == 'cfo_to_net_profit' else pct(item.result)}</td>"
        f"<td><code>{html.escape(item.formula)}</code></td><td>{esc(', '.join(item.input_fact_ids))}</td></tr>"
        for item in result.calculations
    )
    assessments = "".join(
        f"<section><h3>{esc(item.title)} · {status_names[item.status]}</h3><p>{esc(item.reason)}</p>"
        + "".join(f"<p><b>{esc(step['label'])}</b>：{pct(step['value'])} {esc(step['operator'])} {pct(step['threshold'])}；距阈值 {pct(step['difference'])}；{'满足' if step['passed'] else '不满足'}。公式：{esc(step['formula'])}；原始金额：{step_facts(step)}；计算 ID：{esc(', '.join(step['calculation_ids']))}</p>" for step in item.steps)
        + f"<p>可能解释：{esc('；'.join(item.possible_explanations))}</p><p>下一步核查：{esc('；'.join(item.next_checks))}</p><p>输入事实 ID：{esc(', '.join(item.fact_ids))}</p></section>"
        for item in result.rule_assessments
    )
    narrative = f"<h2>模型辅助解读</h2><p>{html.escape(result.narrative)}</p>" if result.narrative else ""
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>FinGuard 分析报告</title>
<style>body{{font-family:Arial,'Microsoft YaHei';max-width:1100px;margin:40px auto;padding:0 24px;line-height:1.65;color:#3b302a;background:#f6f0e6}}h1,h2{{color:#4b3b32}}table{{border-collapse:collapse;width:100%;font-size:14px;background:#fffdf9}}td,th{{border:1px solid #e5d8c7;padding:9px;text-align:left}}th{{background:#f2e9dc}}code{{color:#865038}}</style></head><body>
<h1>FinGuard 可审计财务分析报告</h1><p>报告期间：{esc(period_label)} · 已核验事实：{len(result.facts)} 项</p><p>{html.escape(result.summary)}</p><p>需要关注 {counts['triggered']} 项 · 未触发 {counts['clear']} 项 · 无法判断 {counts['insufficient']} 项</p><p>运行 ID：{html.escape(result.run.run_id)}</p>{narrative}
<h2>分析过程</h2><table><tr><th>期间</th><th>指标</th><th>结果</th><th>公式</th><th>输入事实 ID</th></tr>{calculations}</table>
<h2>异常信号与判断步骤</h2>{assessments}
<h2>原文证据</h2><table><tr><th>期间</th><th>指标</th><th>标准化金额（报告币种）</th><th>证据位置</th><th>原文摘录</th><th>修改记录</th></tr>{facts}</table>
<p>本报告用于辅助财务核验，不构成投资建议。</p></body></html>"""


def run_analysis(request: AnalysisRunRequest) -> AnalysisResult:
    if not request.extraction_id:
        raise ValueError("请先完成数据抽取与人工核验")
    batch = load_extraction(request.extraction_id)
    unresolved = [fact for fact in batch.facts if fact.verification_status not in {VerificationStatus.VERIFIED, VerificationStatus.MISSING}]
    if unresolved:
        raise ValueError(f"仍有 {len(unresolved)} 项数据尚未确认")

    facts = [fact for fact in batch.facts if fact.verification_status == VerificationStatus.VERIFIED and fact.value is not None]
    if not facts:
        raise ValueError("没有可用于分析的已核验数据")

    run = AgentRun(report_ids=batch.report_ids, company_code=batch.company_code, status="running", git_commit=git_commit(ROOT_DIR))
    run_dir = RUNS_DIR / run.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    append_tool_log(run_dir, "run.started", {"extraction_id": batch.extraction_id, "goal": request.analysis_goal})

    calculations = calculate_financial_metrics(facts)
    append_tool_log(run_dir, "calculate_financial_metrics", {"calculation_count": len(calculations)})
    signals = add_counter_evidence(detect_anomaly_signals(facts, calculations), calculations)
    append_tool_log(run_dir, "detect_anomaly_signals", {"signal_count": len(signals)})
    assessments = _rule_assessments(batch, {signal.rule_id for signal in signals})
    summary = _deterministic_summary(batch, len(signals), sum(item.status == "insufficient" for item in assessments))

    narrative = None
    narrative_error = None
    if request.use_gpt_narrative:
        try:
            narrative = generate_verified_narrative(run_dir, facts, calculations, signals)
            if narrative is None:
                narrative_error = "未配置 OPENAI_API_KEY，已保留确定性分析结果。"
        except NarrativeGenerationError as error:
            narrative_error = f"模型摘要生成失败：{error}"
            append_tool_log(run_dir, "openai.responses.error", {"error": str(error)})

    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    run.model = OPENAI_MODEL if narrative else None
    run.output_path = str(run_dir)
    result = AnalysisResult(
        run=run,
        facts=facts,
        calculations=calculations,
        signals=signals,
        narrative=narrative,
        narrative_error=narrative_error,
        report_url=f"/analysis/runs/{run.run_id}/report",
        summary=summary,
        rule_assessments=assessments,
    )
    result = enrich_result(result)
    result.summary = _deterministic_summary(batch, sum(item.status == "triggered" for item in result.rule_assessments), sum(item.status == "insufficient" for item in result.rule_assessments))
    evidence = [EvidenceLink(fact_id=f.fact_id, source_file=f.source_file, page_number=f.page_number, excerpt=f.source_text) for f in facts]
    write_json(run_dir / "manifest.json", {"run": run.model_dump(mode="json"), "extraction_id": batch.extraction_id, "output_hash_seed": hashlib.sha256(run.run_id.encode()).hexdigest()})
    write_json(run_dir / "extracted_facts.json", [fact.model_dump(mode="json") for fact in facts])
    write_json(run_dir / "calculations.json", [item.model_dump(mode="json") for item in calculations])
    write_json(run_dir / "anomaly_signals.json", [item.model_dump(mode="json") for item in signals])
    write_json(run_dir / "earnings_driver_tree.json", build_earnings_driver_tree(calculations))
    write_json(run_dir / "evidence_links.json", [item.model_dump(mode="json") for item in evidence])
    write_json(run_dir / "verification.json", {"issues": verify_result(facts, calculations, signals)})
    write_json(run_dir / "final_result.json", result.model_dump(mode="json"))
    persist_run(RUNS_DIR / "finguard.sqlite", run, facts)
    (run_dir / "final_report.html").write_text(_report_html(result), encoding="utf-8")
    append_tool_log(run_dir, "run.completed", {"output_path": str(run_dir)})
    return result
