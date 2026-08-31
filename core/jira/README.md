# Jira 领域与集成

`Issue` 是 Jira 专属领域对象。Gateway 复用 Atlassian SDK，Mapper 与 Repository
提供核心字段和按需详情；命令、创建元数据和附件服务供 Redmine Clone 使用。
`audit` 保留确定性审查与原格式 XLSX，Web 持有当前态缓存和任务适配。

日报通过 `services.issue_service.JiraIssueService` 查询完整轻量结果；不加载旧字段注册表或详情。
独立 Client Jira 页面及其 workspace、自然语言分析和 MCP 链已删除。
跨 tracker 的中立创建契约仍由 `core.issues` 管理；各消费者直接导入实际 owner，无兼容 re-export。
