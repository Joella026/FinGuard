# 协作指南

1. 不直接向 `main` 推送代码。
2. 每个功能从 Issue 开始，分支命名为 `feat/<module>`、`fix/<issue>` 或 `docs/<topic>`。
3. PR 必须说明：改动目的、测试结果、是否改变数据合同、是否增加第三方依赖。
4. 涉及计算公式和异常阈值的 PR 必须由财务规则负责人审核。
5. 涉及 API、数据模型和日志格式的 PR 必须更新 `docs/data-dictionary.md`。
6. 禁止提交 API Key、原始报告、含个人信息的材料和生成的 `runs/` 文件。

推荐首批 Issue：

- PDF 表格抽取增强
- 财务事实人工核验工作流
- 会计口径标准化
- 三表勾稽规则
- Streamlit 视觉优化
- MCP 服务封装

