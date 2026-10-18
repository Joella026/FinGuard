import { useEffect, useState } from "react";
import { Badge, Layout, Menu, Typography } from "antd";
import { HistoryOutlined, PlusCircleOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import HomePage from "./pages/HomePage";
import HistoryPage from "./pages/HistoryPage";
import ReviewPage from "./pages/ReviewPage";
import ResultsPage from "./pages/ResultsPage";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

export default function Shell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [healthy, setHealthy] = useState(false);
  const [context, setContext] = useState("选择公司，开始一次核验");

  useEffect(() => {
    api.health().then(() => setHealthy(true)).catch(() => setHealthy(false));
    let active = true;
    const [, section, id] = location.pathname.split("/");
    if (section === "review" && id) {
      api.extraction(id).then((batch) => {
        if (active) setContext(`${batch.company_name || batch.company_code} · ${batch.years.join(" / ")}`);
      }).catch(() => { if (active) setContext("核验记录无法读取"); });
    } else if (section === "analysis" && id) {
      Promise.all([api.result(id), api.history()]).then(([result, items]) => {
        const years = [...new Set(result.facts.map((fact) => fact.report_year).filter(Boolean))].sort();
        const name = items.find((item) => item.run_id === id)?.company_name || result.run.company_code;
        if (active) setContext(`${name} · ${years.join(" / ")}`);
      }).catch(() => { if (active) setContext("分析记录无法读取"); });
    } else {
      setContext(section === "history" ? "过去的核验与分析" : "选择公司，开始一次核验");
    }
    return () => { active = false; };
  }, [location.pathname]);

  const selected = location.pathname.startsWith("/history") ? "history" : location.pathname === "/" ? "home" : "";
  return (
    <Layout className="app-shell">
      <Sider width={224} className="app-sider">
        <div className="brand">
          <div className="brand-mark"><SafetyCertificateOutlined /></div>
          <div><strong>FinGuard</strong><span>财报核验工作台</span></div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          items={[
            { key: "home", icon: <PlusCircleOutlined />, label: "新建分析" },
            { key: "history", icon: <HistoryOutlined />, label: "历史记录" }
          ]}
          onClick={({ key }) => navigate(key === "history" ? "/history" : "/")}
        />
        <div className="sider-note">
          <Text>工作流程</Text>
          <p>选择一份报告 → 核验数据</p>
          <p>连续两年年报 → 同比分析</p>
          <p>完成分析 → 回看证据</p>
        </div>
      </Sider>
      <Layout>
        <Header className="topbar">
          <div><Text className="topbar-company">{context}</Text><Text type="secondary">可审计财报分析平台</Text></div>
          <Badge status={healthy ? "success" : "error"} text={healthy ? "后端服务正常" : "后端连接失败"} />
        </Header>
        <Content className="main-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/review/:extractionId" element={<ReviewPage />} />
            <Route path="/analysis/:runId" element={<ResultsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
