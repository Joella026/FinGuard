import { useEffect, useState } from "react";
import { ArrowRightOutlined, FileSearchOutlined, HistoryOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Space, Spin, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { HistoryItem } from "../types";

const { Title, Text, Paragraph } = Typography;

export default function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = () => {
    setLoading(true);
    setError("");
    api.history().then(setItems).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  };
  useEffect(refresh, []);

  return <div className="page history-page">
    <div className="page-heading">
      <div><Text type="secondary">全部工作记录</Text><Title level={2}>历史记录</Title><Paragraph type="secondary">继续待处理的核验，或回看每次分析及其原始证据。</Paragraph></div>
      <Space><Button icon={<ReloadOutlined />} onClick={refresh}>刷新</Button><Button type="primary" onClick={() => navigate("/")}>新建分析</Button></Space>
    </div>
    {loading ? <div className="center-state"><Spin size="large" /></div> : error ?
      <Alert type="error" showIcon message="历史记录读取失败" description={error} action={<Button onClick={refresh}>重试</Button>} /> :
      items.length === 0 ? <Card><Empty description="还没有核验记录，先选择或上传一份财报开始吧。"><Button type="primary" onClick={() => navigate("/")}>新建分析</Button></Empty></Card> :
      <div className="history-list">{items.map((item) => {
        const completed = item.kind === "analysis";
        const label = completed ? "已完成" : item.status === "ready" ? "待分析" : "核验中";
        return <Card key={`${item.kind}-${item.id}`} className="history-card" hoverable onClick={() => navigate(completed ? `/analysis/${item.run_id}` : `/review/${item.extraction_id}`)}>
          <div className="history-card-main">
            <div className="history-icon">{completed ? <FileSearchOutlined /> : <HistoryOutlined />}</div>
            <div className="history-copy">
              <Space><strong>{item.company_name || item.company_code}</strong><Tag className={`history-status ${item.status}`}>{label}</Tag></Space>
              <p>{item.company_code} · {item.years.join(" / ")} · 财报核验</p>
              <Text type="secondary">更新于 {new Date(item.updated_at).toLocaleString("zh-CN")}</Text>
            </div>
            <Button type="text" className="history-open">{completed ? "查看分析" : "继续核验"} <ArrowRightOutlined /></Button>
          </div>
        </Card>;
      })}</div>}
  </div>;
}
