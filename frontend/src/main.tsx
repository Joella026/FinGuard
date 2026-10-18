import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#a86745", colorSuccess: "#577962", colorWarning: "#b7833e", colorError: "#b65349", colorText: "#3b302a", colorBgBase: "#fffdf9", colorBorder: "#e5d8c7", borderRadius: 10, fontFamily: "PingFang SC, Microsoft YaHei, sans-serif" } }}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
