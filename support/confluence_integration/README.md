# Confluence 项目周审集成

本目录是 SmartTest 对 Confluence Server 的唯一只读集成层，复用
`atlassian-python-api`，提供 CQL 分页、页面正文与版本、历史版本、子页面和附件读取。

周审入口位于 Common Tools 的“Confluence 项目周审”。首版由用户点击后全量审查
`Support Mode = A` 且 `Current Stage = 2 IN DEVELOPMENT` 的项目；用户不输入 URL，
也不选择项目。审查周期固定为当前周的上一自然周（Asia/Shanghai）。

Project Status Report 中的 `Status Summary` 与 `Key Target and Completeness`
不属于本工具审查规则；该页仅用于项目范围筛选，以及 Highlights、Impact issues
与 milestone 变更原因检查。

认证复用 SmartTest 当前 LDAP 登录的瞬时凭据。密码不会写入配置、历史、模型或日志。
公网 AI 只接收完成语义判断所需的最小脱敏片段；确定性规则不会调用 AI。AI 不可用时，
静态结果仍会保存，语义项标记为无法判断。

环境变量：

- `SMARTTEST_CONFLUENCE_BASE_URL`：可选，默认 `https://confluence.amlogic.com`。
- AI 模型和 API Key 沿用 `support/ai` 当前选择与现有安全配置；切换模型不需要修改周审代码。

本模块禁止 Confluence 写操作。周一 09:00 调度不在首版范围内。
