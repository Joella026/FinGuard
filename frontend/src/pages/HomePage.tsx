import { useState } from "react";
import { AuditOutlined, BarChartOutlined, CloudUploadOutlined, DatabaseOutlined, SearchOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Checkbox, Col, Empty, Flex, Form, Input, InputNumber, Radio, Row, Segmented, Select, Space, Tag, Typography, Upload, message } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Disclosure, DisclosureSearch, ExtractionBatch } from "../types";

const { Title, Text, Paragraph } = Typography;

function latestAnnualPair(items: Disclosure[]): Disclosure[] {
  const annual = items.filter((item) => item.kind === "annual" && !item.is_summary && !item.is_correction && !/英文版|摘要/.test(item.title));
  const years = [...new Set(annual.map((item) => item.report_year))].sort((a, b) => b - a);
  const newer = years.find((year) => years.includes(year - 1));
  if (!newer) return [];
  const pick = (year: number) => annual.filter((item) => item.report_year === year).sort((a, b) => Number(a.announcement_id.startsWith("local:")) - Number(b.announcement_id.startsWith("local:")) || b.published_at.localeCompare(a.published_at))[0];
  return [pick(newer - 1), pick(newer)];
}

export default function HomePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<DisclosureSearch | null>(null);
  const [searchCode, setSearchCode] = useState("");
  const [yearFrom, setYearFrom] = useState(new Date().getFullYear() - 2);
  const [yearTo, setYearTo] = useState(new Date().getFullYear());
  const [kindFilter, setKindFilter] = useState("all");
  const [entryMode, setEntryMode] = useState<"search" | "upload">("search");
  const [selected, setSelected] = useState<string[]>([]);
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  const remember = (batch: ExtractionBatch) => {
    navigate("/review/" + batch.extraction_id);
  };

  const search = async () => {
    setSearching(true);
    setSelected([]);
    setSearchResult(null);
    try {
      setSearchResult(await api.searchDisclosures(searchCode, yearFrom, yearTo));
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setSearching(false);
    }
  };

  const importOne = async (item: Disclosure) => {
    setLoading(true);
    try {
      const report = await api.importDisclosure(item.company_code, item.announcement_id, item.report_year);
      setSearchResult((previous) => previous ? { ...previous, items: previous.items.map((entry) => entry.announcement_id === item.announcement_id ? { ...entry, local_report_id: report.report_id } : entry) } : previous);
      messageApi.success("报告已保存到本地");
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const startReview = async (items: Disclosure[]) => {
    if (items.length < 1 || items.length > 2 || items.some((item) => item.is_summary || item.is_correction) || (items.length === 2 && (items.some((item) => item.kind !== "annual") || items[0].company_code !== items[1].company_code || Math.abs(items[0].report_year - items[1].report_year) !== 1))) {
      messageApi.warning("请选择一份完整报告，或同一公司连续两份完整年报");
      return;
    }
    setLoading(true);
    try {
      const reports = await Promise.all(items.map((item) => api.importDisclosure(item.company_code, item.announcement_id, item.report_year)));
      remember(await api.createExtraction(reports.map((item) => item.report_id)));
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const analyzeSelected = () => startReview(searchResult?.items.filter((item) => selected.includes(item.announcement_id)) || []);
  const visible = searchResult?.items.filter((item) => kindFilter === "all" || item.kind === kindFilter) || [];
  const recommended = latestAnnualPair(searchResult?.items || []);
  const selectedReports = searchResult?.items.filter((item) => selected.includes(item.announcement_id)) || [];
  const validSelection = selectedReports.length === 1 || (selectedReports.length === 2 && selectedReports.every((item) => item.kind === "annual") && Math.abs(selectedReports[0].report_year - selectedReports[1].report_year) === 1);

  const submitUpload = async () => {
    if (!fileA) {
      messageApi.warning("请至少上传一份财报");
      return;
    }
    const values = await form.validateFields();
    if (fileB && (values.period !== "FY" || values.yearB !== values.yearA + 1)) {
      messageApi.warning("两份报告对比仅支持连续两个年度的完整年报");
      return;
    }
    setLoading(true);
    try {
      const reports = await Promise.all([
        api.uploadReport(fileA, values.companyCode, values.companyName, values.yearA, values.period, values.currency),
        ...(fileB ? [api.uploadReport(fileB, values.companyCode, values.companyName, values.yearB, "FY", values.currency)] : [])
      ]);
      remember(await api.createExtraction(reports.map((item) => item.report_id)));
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page home-page">
      {contextHolder}
      <section className="hero-panel">
        <div>
          <Tag>FINANCIAL EVIDENCE WORKSPACE</Tag>
          <Title>让每一个数字有出处，<br />每一个结论可验证</Title>
          <Paragraph>{entryMode === "search" ? "按 A 股代码查找并核验定期报告，也可选择连续两年年报做对比。" : "上传任意公司的 PDF 财务报告，核验关键数据后查看可复算的分析结果。"}</Paragraph>
          <Space><Tag>本地运行</Tag><Tag>人工核验</Tag><Tag>程序计算</Tag><Tag>完整留痕</Tag></Space>
        </div>
        <div className="hero-graphic">
          <div className="graphic-node"><DatabaseOutlined /> 财务事实</div>
          <div className="graphic-line" />
          <div className="graphic-node active"><AuditOutlined /> 人工核验</div>
          <div className="graphic-line" />
          <div className="graphic-node"><BarChartOutlined /> 异常信号</div>
        </div>
      </section>

      <div className="entry-switch"><Segmented size="large" block value={entryMode} onChange={(value) => setEntryMode(value as "search" | "upload")} options={[{ label: "股票查询并核验", value: "search" }, { label: "手动上传财报", value: "upload" }]} /></div>

      {entryMode === "search" && <Card className="disclosure-search-card" title={<Space><SearchOutlined />股票查询并核验</Space>}>
        <Flex gap={12} wrap="wrap" align="end" className="disclosure-search-form">
          <div className="search-field stock"><Text type="secondary">A 股股票代码</Text><Input value={searchCode} onChange={(event) => setSearchCode(event.target.value)} onPressEnter={search} placeholder="例如 000333 或 600519" maxLength={9} /></div>
          <div className="search-field year"><Text type="secondary">起始年度</Text><InputNumber min={1990} max={2100} value={yearFrom} onChange={(value) => setYearFrom(value || 2024)} className="full-width" /></div>
          <div className="search-field year"><Text type="secondary">截止年度</Text><InputNumber min={1990} max={2100} value={yearTo} onChange={(value) => setYearTo(value || 2026)} className="full-width" /></div>
          <Button type="primary" icon={<SearchOutlined />} loading={searching} onClick={search}>搜索财报</Button>
        </Flex>
        <Paragraph type="secondary" className="search-hint">搜索结果中可直接选择任意一份完整报告核验；连续两份完整年报可进行同比分析。来源为巨潮资讯公开公告。</Paragraph>
        {searchResult && <>
          {searchResult.warning && <Alert type="warning" showIcon message={searchResult.warning} className="search-warning" />}
          {recommended.length === 2 && <div className="review-shortcut">
            <div><strong>{recommended[1].company_name} · {recommended[0].report_year}—{recommended[1].report_year} 年报</strong><p>系统已找到连续两份完整年报，点击后自动获取 PDF 并进入财务事实核验。</p></div>
            <Button type="primary" size="large" loading={loading} onClick={() => startReview(recommended)}>核验最近两年年报</Button>
          </div>}
          <Flex justify="space-between" align="center" wrap="wrap" gap={12} className="disclosure-toolbar">
            <Radio.Group value={kindFilter} onChange={(event) => setKindFilter(event.target.value)} optionType="button" buttonStyle="solid" options={[{ label: "全部", value: "all" }, { label: "年报", value: "annual" }, { label: "半年报", value: "semiannual" }, { label: "一季报", value: "q1" }, { label: "三季报", value: "q3" }]} />
            <Button disabled={!validSelection} loading={loading} onClick={analyzeSelected}>{selectedReports.length === 1 ? "核验选中的报告" : "对比核验选中的两份年报"}</Button>
          </Flex>
          {visible.length === 0 ? <Empty description="该范围内没有可显示的报告" /> : <div className="disclosure-list">{visible.map((item) => {
            const selectable = !item.is_summary && !item.is_correction;
            const source = item.local_report_id ? `/reports/${item.local_report_id}/file` : item.pdf_url;
            return <div className="disclosure-row" key={item.announcement_id}>
              <Checkbox disabled={!selectable} checked={selected.includes(item.announcement_id)} onChange={(event) => setSelected((previous) => event.target.checked ? [...previous, item.announcement_id].slice(-2) : previous.filter((id) => id !== item.announcement_id))} aria-label={`选择 ${item.title}`} />
              <div className="disclosure-main"><strong>{item.title}</strong><div><Text type="secondary">{item.company_name} · {item.report_year} 年 · {item.announcement_id.startsWith("local:") ? "本地登记" : item.published_at.slice(0, 10)}</Text></div></div>
              <Tag color={item.kind === "annual" ? "green" : "gold"}>{item.kind_label}</Tag>
              {item.is_summary && <Tag>摘要</Tag>}{item.is_correction && <Tag>修订</Tag>}{item.local_report_id && <Tag color="green">已保存</Tag>}
              <Space><a href={source || "#"} target="_blank" rel="noopener noreferrer" aria-disabled={!source}>查看原文</a>{selectable && <Button size="small" type="primary" ghost loading={loading} onClick={() => startReview([item])}>核验这份</Button>}{!item.local_report_id && selectable && <Button size="small" loading={loading} onClick={() => importOne(item)}>保存到本地</Button>}</Space>
            </div>;
          })}</div>}
        </>}
      </Card>}

      {entryMode === "upload" && <Card className="entry-card upload-card" title={<Space><CloudUploadOutlined />手动上传财报</Space>}>
            <Paragraph type="secondary">无需证券代码，可上传任意公司的 PDF 财务报告。填写报告主体、币种与期间后进入人工核验；当前自动识别主要针对中文财报的六项指标，其他版式可手动补充，缺失项不会被当作零。</Paragraph>
            <Form form={form} layout="vertical" initialValues={{ yearA: 2024, yearB: 2025, period: "FY", currency: "CNY" }}>
              <Row gutter={12}>
                <Col span={12}><Form.Item name="companyName" label="公司名称" rules={[{ required: true }]}><Input placeholder="例如：某某股份有限公司" /></Form.Item></Col>
                <Col span={12}><Form.Item name="companyCode" label="股票代码或主体标识（可选）" rules={[{ pattern: /^[A-Za-z0-9][A-Za-z0-9._-]*$/, message: "仅支持字母、数字、点、横线和下划线" }, { max: 40 }]}><Input placeholder="没有股票代码可留空" /></Form.Item></Col>
                <Col span={12}><Form.Item name="currency" label="报告币种" rules={[{ required: true }, { pattern: /^[A-Za-z]{3}$/, message: "填写三位币种代码，如 CNY、HKD、USD" }]}><Input placeholder="CNY / HKD / USD" maxLength={3} /></Form.Item></Col>
                <Col span={12}><Form.Item name="yearA" label="报告年度" rules={[{ required: true }]}><InputNumber min={2000} max={2100} className="full-width" /></Form.Item></Col>
                <Col span={12}><Form.Item name="period" label="报告类型" rules={[{ required: true }]}><Select options={[{ value: "FY", label: "年度报告" }, { value: "H1", label: "半年度报告" }, { value: "Q1", label: "第一季度报告" }, { value: "Q2", label: "第二季度报告" }, { value: "Q3", label: "第三季度报告" }, { value: "Q4", label: "第四季度报告" }]} /></Form.Item></Col>
                <Col span={12}><Upload.Dragger accept=".pdf" maxCount={1} beforeUpload={(file) => { setFileA(file); return false; }} onRemove={() => setFileA(null)}><p className="ant-upload-drag-icon"><CloudUploadOutlined /></p><p>上传要核验的 PDF</p></Upload.Dragger></Col>
                <Col span={12}><Upload.Dragger accept=".pdf" maxCount={1} beforeUpload={(file) => { setFileB(file); return false; }} onRemove={() => setFileB(null)}><p className="ant-upload-drag-icon"><CloudUploadOutlined /></p><p>可选：上传下一年度年报</p></Upload.Dragger></Col>
                {fileB && <Col span={12}><Form.Item name="yearB" label="第二份报告年度" rules={[{ required: true }]}><InputNumber min={2000} max={2100} className="full-width" /></Form.Item></Col>}
              </Row>
              <Button type="primary" size="large" block className="submit-button" loading={loading} onClick={submitUpload}>上传并进入核验</Button>
            </Form>
      </Card>}
    </div>
  );
}
