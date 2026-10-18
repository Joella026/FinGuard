# 模型、数据与许可证说明

## 模型

- 名称：OpenAI GPT（默认配置 `gpt-5.5`）
- 用途：任务理解、已验证结果的审慎叙述、报告语言组织
- 调用方式：后端通过 OpenAI Python SDK 的 Responses API 调用
- 限制：模型不得直接负责数值计算、证据定位或异常规则判定

## 第三方依赖

| 名称 | 用途 | 许可证 |
|---|---|---|
| FastAPI | 后端 API | MIT |
| Pydantic | 数据合同验证 | MIT |
| pypdf | PDF 文本解析 | BSD-3-Clause |
| Streamlit | 驾驶舱 | Apache-2.0 |
| OpenAI Python SDK | GPT 调用 | Apache-2.0 |

参赛前须补充实际使用的数据来源、版本、获取日期、许可证及使用范围。

