# SmartTest Jira 集成

`jira_tool` 是 SmartTest 内部 Jira 集成层。目标是在 Jira Server / Data Center 环境中提供可预测的 REST 行为、明确的字段投影、快速分页浏览和按需分析，而不是为单个 Jira SDK 再包一层。

## 所有权与依赖方向

依赖方向固定为：

```text
Jira QML
  -> JiraBridge
  -> JiraWorkspaceService
  -> JiraBrowseService / JiraAnalysisService
  -> JiraIssueService
  -> JiraClient
  -> Jira Server
```

- `JiraBridge`：只拥有 Qt 属性、信号、槽、页面状态和异步调用适配；不构建 JQL，不访问 Jira 字段、缓存或 REST。
- `JiraWorkspaceService`：Bridge 使用的稳定兼容门面；把显式参数收拢为不可变请求合同并委托业务服务。
- `JiraBrowseService`：拥有收藏筛选器规范化、分页浏览和 Issue 详情用例。
- `JiraAnalysisService`：拥有 AI/MCP 分析、自然语言搜索、JQL 放宽重试和分析辅助算法。
- `JiraIssueService`：拥有字段抓取计划、分页记录投影、Issue hydration、本地查询与收藏筛选器传输边界。
- `JiraClient`：唯一 Jira REST 出口；拥有认证、HTTP、分页、JSON 编解码和传输错误。
- `jira_tool/fields/`：字段规格、元数据注册、嵌套值提取和 `jira_fields`/`expand` 计划的唯一所有者。
- `jira_tool/cache/`：元数据缓存、Issue store、搜索缓存和同步状态的唯一持久化所有者。

QML 不直接调用 `jira_tool`，Service 不依赖 Qt，Bridge 不组装 auth、transport、字段注册表或缓存。

## 当前运行假设

- 当前实例按 Jira Server / Data Center 处理，REST 路径为 `.../rest/api/2/...`。
- 应用复用 LDAP 凭据访问 Jira。
- 浏览路径只取轻量字段并分页返回；分析路径仅在用户明确要求时扩大字段或结果范围。
- 字段元数据通过 `/field` 获取并带 TTL 缓存；自定义字段不得依赖硬编码显示名。

## REST 与字段规则

1. 搜索必须显式传入 `fields`、`startAt`、`maxResults`，仅在需要时传入 `expand`。
2. `GET /search` 与 `POST /search` 参数需分别规范化；当前 Jira 的 POST JSON 要求布尔型 `validateQuery`。
3. `/field` 返回 field id、显示名、clause names 与 schema；注册表据此推断 `.value`、`.name`、`.displayName` 或数组路径，并处理别名冲突。
4. `python-jira` 仅作为接口参考；性能敏感路径继续使用直接 REST JSON、字段投影、本地缓存和延迟 hydration。
5. changelog、comments、worklog 等重字段默认延迟，只有明确用例才请求。

## 性能与排障

- 页面打开或筛选变化时，不全量抓取、不默认执行 AI；先返回第一页，再按需 load more。
- 本地 Issue store 用于复用原始 JSON、本地常用维度查询和增量同步，不意味着页面打开时全量同步。
- 排障时分别确认 Bridge/runtime、认证/transport、JQL/search 与字段映射，不把 QML 或 Python 导入错误误判为 Jira API 错误。
- 所有 Jira 请求必须经过 `JiraClient`；禁止静默回退到第二条 HTTP 路径。

## 后续扩展边界

Create Jira 必须通过独立的 `CreateIssueService` 扩展。Bug Clone 只能把外部数据映射为 `CreateIssueRequest`，再交给 `CreateIssueService`，不能直接调用 Jira REST。

新增字段时，先检查 `/field` 元数据，再改进元数据到路径的推断；只有真正通用或特殊的字段才增加手写默认规格。新增 UI 浏览能力时，优先减少字段、分页查询、复用缓存原始数据和按选择 hydration。新增分析能力时，输入必须是定义明确的结果集和字段规格，AI 层不得决定底层传输行为。

## 官方参考

- Jira Server / Data Center REST 概览：https://developer.atlassian.com/server/jira/platform/about-the-jira-server-rest-apis/
- Jira Server / Data Center Basic Auth：https://developer.atlassian.com/server/jira/platform/basic-authentication/
- Jira REST 7.1.9：https://docs.atlassian.com/software/jira/docs/api/REST/7.1.9/
- Jira REST 8.2.6：https://docs.atlassian.com/software/jira/docs/api/REST/8.2.6/
- `python-jira` API：https://jira.readthedocs.io/en/latest/api.html
- `python-jira` client 源码：https://jira.readthedocs.io/_modules/jira/client.html
- `python-jira` 示例：https://jira.readthedocs.io/examples.html
