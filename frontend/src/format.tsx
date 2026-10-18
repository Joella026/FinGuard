import { CheckCircleOutlined, WarningOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import type { FinancialFact } from "./types";

export function formatMoney(value?: number, currency = "CNY") {
  if (value === undefined || value === null) return "暂缺";
  const absolute = Math.abs(value);
  const suffix = currency === "CNY" ? "元" : ` ${currency}`;
  if (absolute >= 100_000_000) return (value / 100_000_000).toFixed(2) + (currency === "CNY" ? " 亿元" : ` 亿${suffix}`);
  if (absolute >= 10_000) return (value / 10_000).toFixed(2) + (currency === "CNY" ? " 万元" : ` 万${suffix}`);
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) + (currency === "CNY" ? " 元" : suffix);
}

export function formatPercent(value?: number) {
  return value === undefined || value === null ? "无法计算" : (value * 100).toFixed(2) + "%";
}

export function formatMultiple(value?: number) {
  return value === undefined || value === null ? "无法计算" : value.toFixed(2) + " 倍";
}

export function statusTag(status: FinancialFact["verification_status"]) {
  if (status === "verified") return <Tag color="success" icon={<CheckCircleOutlined />}>已核验</Tag>;
  if (status === "missing") return <Tag>暂缺</Tag>;
  return <Tag color="warning" icon={<WarningOutlined />}>待确认</Tag>;
}
