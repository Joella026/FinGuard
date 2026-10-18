import { useEffect, useState } from "react";
import { Alert, Button, Card, Descriptions, Divider, Drawer, Empty, Flex, Form, Input, InputNumber, Modal, Progress, Select, Space, Spin, Switch, Table, Typography, message } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { formatMoney, statusTag } from "../format";
import type { ExtractionBatch, FinancialFact } from "../types";

const { Title, Text } = Typography;

export default function ReviewPage() {
  const { extractionId = "" } = useParams();
  const navigate = useNavigate();
  const [batch, setBatch] = useState<ExtractionBatch>();
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedFact, setSelectedFact] = useState<FinancialFact>();
  const [editFact, setEditFact] = useState<FinancialFact>();
  const [editMode, setEditMode] = useState<"verify" | "missing">("verify");
  const [useGpt, setUseGpt] = useState(false);
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    api.extraction(extractionId).then(setBatch).catch((error: Error) => setLoadError(error.message)).finally(() => setLoading(false));
  }, [extractionId, messageApi]);

  const openEdit = (fact: FinancialFact, mode: "verify" | "missing") => {
    setEditFact(fact);
    setEditMode(mode);
    form.setFieldsValue({ value: fact.raw_value, rawUnit: fact.raw_unit, pageNumber: fact.page_number, sourceText: fact.source_text, reason: "" });
  };

  const saveReview = async () => {
    if (!editFact) return;
    const values = await form.validateFields();
    setSaving(true);
    try {
      const body = editMode === "missing"
        ? { action: "mark_missing", reason: values.reason }
        : { action: "verify", value: values.value, raw_unit: values.rawUnit, page_number: values.pageNumber, source_text: values.sourceText, reason: values.reason || undefined };
      setBatch(await api.reviewFact(extractionId, editFact.fact_id, body));
      setEditFact(undefined);
      messageApi.success(editMode === "missing" ? "已标记为暂缺" : "核验结果已保存");
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const quickVerify = async (fact: FinancialFact) => {
    try {
      setBatch(await api.reviewFact(extractionId, fact.fact_id, { action: "verify" }));
    } catch (error) {
      messageApi.error((error as Error).message);
    }
  };

  const run = async () => {
    setSaving(true);
    try {
      const result = await api.runAnalysis(extractionId, useGpt);
      navigate("/analysis/" + result.run.run_id);
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="center-state"><Spin size="large" /></div>;
  if (loadError) return <Alert type="error" showIcon message="核验记录读取失败" description={loadError} />;
  if (!batch) return <Empty description="未找到核验批次" />;
  const verifiedCount = batch.facts.filter((item) => ["verified", "missing"].includes(item.verification_status)).length;

  return (
    <div className="page">
      {contextHolder}
      <div className="page-heading">
        <div><Text type="secondary">第二步 · 数据核验</Text><Title level={2}>{batch.company_name || batch.company_code} 财务事实核验</Title><Button type="link" className="back-link" onClick={() => navigate("/history")}>← 返回历史记录</Button></div>
        <div className="review-progress"><Text>{verifiedCount} / {batch.facts.length} 已处理</Text><Progress percent={Math.round(verifiedCount / batch.facts.length * 100)} showInfo={false} /></div>
      </div>
      {batch.issues.map((issue) => <Alert key={issue} className="inline-alert" type="warning" showIcon message={issue} />)}
      {batch.report_ids.length === 1 && <Alert className="inline-alert" type="info" showIcon message="当前是单份报告核验" description="可以逐项确认原文和数值，并计算本期比率；跨年变化和依赖两年的异常规则会显示无法判断。" />}
      <Card className="data-card">
        <Table
          rowKey="fact_id"
          pagination={false}
          scroll={{ x: 1100 }}
          dataSource={batch.facts}
          columns={[
            { title: "年度", dataIndex: "report_year", width: 80, sorter: (a, b) => (a.report_year || 0) - (b.report_year || 0) },
            { title: "指标", dataIndex: "metric_name", width: 220, fixed: "left" },
            { title: "原始值", width: 150, render: (_, item) => item.raw_value === undefined || item.raw_value === null ? "—" : item.raw_value.toLocaleString() + " " + item.raw_unit },
            { title: "标准化金额", width: 145, render: (_, item) => <span className="numeric">{formatMoney(item.value, item.unit)}</span> },
            { title: "来源", width: 220, render: (_, item) => <Button type="link" className="evidence-link" onClick={() => setSelectedFact(item)}>{item.page_number ? item.source_file + " · P" + item.page_number : "查看缺失详情"}</Button> },
            { title: "状态", width: 100, render: (_, item) => statusTag(item.verification_status) },
            { title: "操作", width: 220, fixed: "right", render: (_, item) => <Space>
              {item.verification_status !== "verified" && item.raw_value !== undefined && item.raw_value !== null && <Button size="small" type="primary" ghost onClick={() => quickVerify(item)}>确认</Button>}
              <Button size="small" onClick={() => openEdit(item, "verify")}>{item.value === undefined || item.value === null ? "补充" : "编辑"}</Button>
              {item.verification_status !== "missing" && <Button size="small" onClick={() => openEdit(item, "missing")}>暂缺</Button>}
            </Space> }
          ]}
        />
      </Card>
      <Card className="action-bar">
        <Flex justify="space-between" align="center">
          <div><strong>核验完成后才能执行分析</strong><p>暂缺数据不会参与计算，相关规则将显示“无法判断”。</p></div>
          <Space size="large"><Space><Text>生成模型摘要</Text><Switch checked={useGpt} onChange={setUseGpt} /></Space><Button type="primary" size="large" disabled={batch.status !== "ready"} loading={saving} onClick={run}>开始可审计分析</Button></Space>
        </Flex>
      </Card>

      <Drawer title="原始证据" width={520} open={!!selectedFact} onClose={() => setSelectedFact(undefined)}>
        {selectedFact && <>
          <Descriptions column={1} bordered size="small" items={[
            { key: "metric", label: "指标", children: selectedFact.metric_name },
            { key: "period", label: "报告期", children: selectedFact.report_period },
            { key: "file", label: "来源文件", children: selectedFact.source_file },
            { key: "page", label: "页码", children: selectedFact.page_number || "未定位" },
            { key: "method", label: "抽取方式", children: selectedFact.extraction_method }
          ]} />
          <Divider orientation="left">原文摘录</Divider>
          <div className="evidence-quote">{selectedFact.source_text || "尚未定位到原文，需要人工补充或标记暂缺。"}</div>
          {!selectedFact.report_id.startsWith("demo-") && selectedFact.page_number > 0 && <Button type="primary" ghost href={"/reports/" + selectedFact.report_id + "/file#page=" + selectedFact.page_number} target="_blank">打开原始 PDF</Button>}
          {!!selectedFact.revisions.length && <><Divider orientation="left">修改记录</Divider>{selectedFact.revisions.map((item) => <p key={item.changed_at}>{item.reason} · {new Date(item.changed_at).toLocaleString("zh-CN")}</p>)}</>}
        </>}
      </Drawer>

      <Modal title={editMode === "missing" ? "标记数据暂缺" : "核验财务事实"} open={!!editFact} onCancel={() => setEditFact(undefined)} onOk={saveReview} confirmLoading={saving} okText="保存核验结果">
        <Form form={form} layout="vertical">
          {editMode === "verify" && <>
            <Form.Item name="value" label="原始数值" rules={[{ required: true, message: "请填写数值" }]}><InputNumber className="full-width" /></Form.Item>
            <Form.Item name="rawUnit" label={`原始单位（${editFact?.unit || "CNY"}）`} rules={[{ required: true }]}><Select options={[{ value: "元", label: "基本单位（1）" }, { value: "千元", label: "千单位（1,000）" }, { value: "万元", label: "万单位（10,000）" }, { value: "百万单位", label: "百万单位（1,000,000）" }, { value: "亿元", label: "亿单位（100,000,000）" }]} /></Form.Item>
            <Form.Item name="pageNumber" label="来源页码" rules={[{ required: true }, ...(editFact?.raw_value === null || editFact?.raw_value === undefined ? [{ type: "number" as const, min: 1, message: "手动补充时请填写 PDF 页码" }] : [])]}><InputNumber min={1} className="full-width" /></Form.Item>
            <Form.Item name="sourceText" label="原文摘录" rules={editFact?.raw_value === null || editFact?.raw_value === undefined ? [{ required: true, whitespace: true, message: "手动补充时请填写原文摘录" }] : []}><Input.TextArea rows={4} /></Form.Item>
          </>}
          <Form.Item name="reason" label={editMode === "missing" ? "暂缺原因" : "修改原因（未修改可不填）"} rules={editMode === "missing" ? [{ required: true }] : []}><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
