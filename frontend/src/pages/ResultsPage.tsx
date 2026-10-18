import { useEffect, useState } from "react";
import { Alert, Button, Card, Collapse, Descriptions, Drawer, Empty, Flex, Space, Spin, Tabs, Tag, Typography } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { formatMoney, formatMultiple, formatPercent } from "../format";
import type { AnalysisResult, Calculation, FinancialFact, RuleAssessment } from "../types";

const { Title, Text, Paragraph } = Typography;
const names: Record<string, string> = { revenue: "营业收入", net_profit_parent: "归母净利润", deducted_net_profit: "扣非净利润", operating_cashflow: "经营现金流", accounts_receivable: "应收账款", inventory: "存货" };
const order = Object.keys(names);
const labels: Record<string, string> = { triggered: "需要关注", clear: "未触发", insufficient: "无法判断" };
const calcValue = (calc: Calculation) => calc.metric_code === "cfo_to_net_profit" ? formatMultiple(calc.result) : formatPercent(calc.result);

export default function ResultsPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<AnalysisResult>();
  const [reviewId, setReviewId] = useState<string>();
  const [companyName, setCompanyName] = useState<string>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [focus, setFocus] = useState<FinancialFact[]>([]);
  useEffect(() => {
    setLoading(true);
    api.result(runId).then(setResult).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
    api.history().then((items) => { const item = items.find((entry) => entry.run_id === runId); setReviewId(item?.extraction_id); setCompanyName(item?.company_name); }).catch(() => undefined);
  }, [runId]);
  if (loading) return <div className="center-state"><Spin size="large" /></div>;
  if (error) return <Alert type="error" showIcon message="结果读取失败" description={error} />;
  if (!result) return <Empty description="未找到分析结果" />;

  const periods = [...new Set(result.facts.map((fact) => fact.report_period))].sort();
  const latest = periods.at(-1) || "";
  const company = companyName || result.facts[0]?.company_code || result.run.company_code;
  const factsById = Object.fromEntries(result.facts.map((fact) => [fact.fact_id, fact]));
  const latestFacts = Object.fromEntries(result.facts.filter((fact) => fact.report_period === latest).map((fact) => [fact.metric_code, fact]));
  const counts = { triggered: result.rule_assessments.filter((item) => item.status === "triggered").length, clear: result.rule_assessments.filter((item) => item.status === "clear").length, insufficient: result.rule_assessments.filter((item) => item.status === "insufficient").length };
  const openFacts = (ids: string[]) => setFocus(ids.map((id) => factsById[id]).filter(Boolean));
  const factButton = (ids: string[], label = "查看原文证据") => <Button type="link" className="evidence-action" disabled={!ids.length} onClick={() => openFacts(ids)}>{label}</Button>;
  const sorted = [...result.rule_assessments].sort((a, b) => ({ triggered: 0, clear: 1, insufficient: 2 }[a.status] - { triggered: 0, clear: 1, insufficient: 2 }[b.status]));
  const detail = (item: RuleAssessment) => <div className="rule-detail"><Paragraph>{item.reason}</Paragraph>
    {item.steps.map((step, index) => <div className="rule-step" key={index}><div><strong>{step.label}</strong><span className="numeric">{formatPercent(step.value)} {step.operator} {formatPercent(step.threshold)}</span><Tag color={step.passed ? "success" : "default"}>{step.passed ? "满足" : "不满足"}</Tag></div>
      {step.inputs && step.inputs.length > 1 && <Text type="secondary">输入增速：{step.inputs.map((input) => `${input.label} ${formatPercent(input.value)}`).join("；")}</Text>}
      <Text type="secondary">原始金额：{step.fact_inputs.map((input) => `${input.period} ${input.label} ${formatMoney(input.value, input.unit)}`).join("；")}</Text>
      <Text type="secondary">距阈值 {formatPercent(step.difference)} · 公式：{step.formula}</Text>{factButton(step.fact_ids, "查看输入事实与 PDF 页码")}</div>)}
    {item.missing_inputs.length > 0 && <Paragraph type="secondary">缺少：{item.missing_inputs.join("；")}</Paragraph>}
    {item.status === "triggered" && <><Paragraph><strong>可能解释：</strong>{item.possible_explanations.join("；")}</Paragraph><Paragraph><strong>下一步核查：</strong>{item.next_checks.join("；")}</Paragraph></>}
  </div>;

  const overview = <div className="result-stack"><Card className="result-lead"><Text type="secondary">{company} · {periods.join(" / ")} · {periods.length === 1 ? "本期分析" : "连续年度分析"}</Text><Title level={3}>已核验 {result.facts.length} 项事实，发现 {counts.triggered} 项需关注信号</Title><Paragraph>{result.summary}</Paragraph><Flex gap={10} wrap="wrap"><Tag color="error">需关注 {counts.triggered}</Tag><Tag color="success">未触发 {counts.clear}</Tag><Tag color="warning">无法判断 {counts.insufficient}</Tag></Flex></Card>
    {result.narrative && <Card size="small" title="模型辅助解读"><Paragraph>{result.narrative}</Paragraph></Card>}{result.narrative_error && <Alert type="info" showIcon message={result.narrative_error} />}
    <div className="overview-metrics">{["revenue", "net_profit_parent", "operating_cashflow"].map((key) => <Card key={key} className="overview-metric" onClick={() => latestFacts[key] && openFacts([latestFacts[key].fact_id])}><Text type="secondary">{names[key]} · {latest}</Text><strong className="numeric">{formatMoney(latestFacts[key]?.value, latestFacts[key]?.unit)}</strong><small>点击查看证据</small></Card>)}</div>
    {counts.triggered > 0 && <Card title="优先核查"><div className="priority-list">{sorted.filter((item) => item.status === "triggered").map((item) => <div key={item.rule_id}><Tag color="error">需关注</Tag><strong>{item.title}</strong><span>{item.steps.map((step) => `${step.label} ${formatPercent(step.value)}`).join("；")}</span>{factButton(item.fact_ids, "查看证据")}</div>)}</div></Card>}
  </div>;

  const process = <div className="result-stack"><Alert type="info" showIcon message={periods.length === 1 ? "本期分析：展示可计算比率，跨年同比规则暂无法判断。" : "连续年度分析：先核对输入事实，再看公式、结果与规则判断。"} />
    <Card title="输入事实"><div className="process-grid">{order.map((key) => <div className="process-row" key={key}><strong>{names[key]}</strong>{periods.map((period) => { const fact = result.facts.find((item) => item.report_period === period && item.metric_code === key); return <span key={period}><Text type="secondary">{period}</Text><b className="numeric">{formatMoney(fact?.value, fact?.unit)}</b>{fact && factButton([fact.fact_id], "出处")}</span>; })}</div>)}</div></Card>
    <Card title="公式 → 计算结果 → 判断"><div className="calculation-list">{result.calculations.filter((item) => periods.length > 1 || !item.metric_code.endsWith("_period_change")).map((calc) => <div className="calculation-row" key={calc.calculation_id}><div><Text type="secondary">{calc.report_period}</Text><strong>{calc.metric_name}</strong><code>{calc.formula}</code></div><div><b className="numeric">{calcValue(calc)}</b><small>{calc.result === null || calc.result === undefined ? "无法计算；检查分母与输入事实" : "依据已核验事实计算"}</small>{factButton(calc.input_fact_ids, "输入与出处")}</div></div>)}</div></Card>
    <Card title="规则判断"><div className="judgment-list">{sorted.map((item) => <div key={item.rule_id}><Tag color={item.status === "triggered" ? "error" : item.status === "insufficient" ? "warning" : "success"}>{labels[item.status]}</Tag><strong>{item.title}</strong><span>{item.reason}</span></div>)}</div></Card>
  </div>;

  const signals = <div className="result-stack"><Alert type="info" showIcon message="信号表示达到预设核查条件，不代表已证实的业务成因。" />
    {sorted.filter((item) => item.status === "triggered").map((item) => <Card key={item.rule_id} className="triggered-rule" title={<Space><Tag color="error">需要关注</Tag>{item.title}</Space>} extra={<Text type="secondary">{item.rule_id}</Text>}>{detail(item)}</Card>)}
    {counts.clear > 0 && <Card title={`未触发 · ${counts.clear} 项`}><Collapse ghost items={sorted.filter((item) => item.status === "clear").map((item) => ({ key: item.rule_id, label: item.title, children: detail(item) }))} /></Card>}
    {counts.insufficient > 0 && <Card title={`无法判断 · ${counts.insufficient} 项`}><div className="missing-list">{sorted.filter((item) => item.status === "insufficient").map((item) => <div key={item.rule_id}><strong>{item.title}</strong><span>{item.missing_inputs.join("；") || item.reason}</span></div>)}</div></Card>}
  </div>;

  const evidence = <div className="result-stack"><Alert type="info" showIcon message="以下为本次运行使用的已核验事实；修改记录与 PDF 原文可逐项查看。" /><Card title="原文证据"><div className="evidence-list">{result.facts.map((fact) => <div className="evidence-row" key={fact.fact_id}><div><Text type="secondary">{fact.report_period} · {fact.metric_name}</Text><strong className="numeric">{formatMoney(fact.value, fact.unit)}</strong><Text type="secondary">{fact.source_file} · PDF 第 {fact.page_number} 页</Text></div><div><p>{fact.source_text}</p>{fact.revisions.length > 0 && <small>修改记录：{fact.revisions.map((revision) => `${revision.previous_value ?? "暂缺"} → ${revision.new_value ?? "暂缺"}（${revision.reason}）`).join("；")}</small>}{!fact.report_id.startsWith("demo-") && <Button type="link" href={`/reports/${fact.report_id}/file#page=${fact.page_number}`} target="_blank">打开 PDF</Button>}</div></div>)}</div></Card><Card size="small"><Text type="secondary">运行 ID：<span className="numeric">{runId}</span>。网页、JSON 与 HTML 使用同一套已保存事实、计算和判断说明。</Text></Card></div>;

  return <div className="page results-page"><div className="page-heading result-heading"><div><Text type="secondary">分析结果 · {company}</Text><Title level={2}>财务质量核验</Title><Space wrap><Button type="link" className="back-link" onClick={() => navigate("/history")}>← 返回历史记录</Button>{reviewId && <Button type="link" className="back-link" onClick={() => navigate("/review/" + reviewId)}>查看核验数据</Button>}</Space></div><Space wrap><Button href={`/analysis/runs/${runId}`} download>下载 JSON</Button><Button type="primary" href={result.report_url} target="_blank">打开 HTML 报告</Button></Space></div>
    <Tabs className="result-tabs" items={[{ key: "overview", label: "概览", children: overview }, { key: "process", label: "分析过程", children: process }, { key: "signals", label: `异常信号 ${counts.triggered > 0 ? `(${counts.triggered})` : ""}`, children: signals }, { key: "evidence", label: "原文证据", children: evidence }]} />
    <Drawer title="输入事实与原文证据" width={560} open={focus.length > 0} onClose={() => setFocus([])}>{focus.map((fact) => <Card size="small" className="evidence-card" key={fact.fact_id}><Descriptions size="small" column={1} items={[{ key: "name", label: "指标", children: `${fact.report_period} · ${fact.metric_name}` }, { key: "value", label: "已核验金额", children: formatMoney(fact.value, fact.unit) }, { key: "source", label: "出处", children: `${fact.source_file} · PDF 第 ${fact.page_number} 页` }]} /><blockquote>{fact.source_text}</blockquote>{fact.revisions.map((revision, index) => <p key={index}>修改：{revision.previous_value ?? "暂缺"} → {revision.new_value ?? "暂缺"}；{revision.reason}</p>)}{!fact.report_id.startsWith("demo-") && <Button href={`/reports/${fact.report_id}/file#page=${fact.page_number}`} target="_blank">打开原始 PDF</Button>}</Card>)}</Drawer>
  </div>;
}
