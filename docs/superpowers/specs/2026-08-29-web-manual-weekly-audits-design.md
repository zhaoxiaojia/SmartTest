# Web Jira 与 Confluence 手动周审查设计

## 1. 目标

将 Jira 周审查和 Confluence 项目周审查迁移到 Web，用两条真实手动审查链路验收新 `Issue`、`Project` 领域模型以及 SQLite 当前态缓存的读取、写入、更新和失效逻辑。

业务规则、审查流程和 XLSX 输出尽量归属 Core；Web 只负责 Session、凭证、当前态存储与缓存适配、任务运行状态、FastAPI 传输和页面展示。

本任务分两个实施阶段：

1. 阶段一完成手动确定性审查全链路。
2. 阶段二在阶段一验收后接入 Jira AI Review 与 Confluence 语义审查。

本文档当前授权实施阶段一。

## 2. 阶段一范围

### 2.1 实现

- Jira JQL、Issue URL、Filter URL 输入与验证。
- Jira Issue 分页获取、当前态缓存写入、按需详情加载、确定性规则和成功后自动 XLSX 导出。
- Confluence 项目筛选展示与周审查分层交互。
- Confluence 手动时间窗口、当前态缓存写入、按需页面材料、八个确定性更新点和按产品线 XLSX 导出。
- 统一进程内审查任务机制。
- 统一后端下载出口和公共前端下载按钮。

### 2.2 不实现

- 定时任务、Weekly Plan 或 Windows Task Scheduler。
- 历史审查结果、历史表或任务跨重启恢复。
- Jira AI Review 与 Confluence 语义模型审查。
- PDF 报告。
- 修改 Jira、Confluence 或 Redmine 远端数据。
- Redmine 审查。

## 3. 总体架构

```text
Web Frontend
   │
   ▼
Web Audit API / Runtime Registry
   │
   ├── WebJiraAuditIssueSource ─────── JiraIssueCacheService
   └── WebConfluenceAuditProjectSource ─ ConfluenceProjectCacheService
   │
   ▼
Core Manual Audit Use Cases
   ├── Jira input / rules / report / exporter
   └── Confluence period / rules / report / exporter
```

Core 不依赖 Web、FastAPI、SQLite、Session 或浏览器。Web Adapter 不解析审查规则，不生成业务报告格式。

### 3.1 Core 所有者

```text
core/jira/audit/
├── input.py
├── models.py
├── rules.py
├── service.py
├── use_case.py
└── exporter.py

core/confluence/audit/
├── input.py
├── models.py
├── period.py
├── rules.py
├── service.py
├── use_case.py
└── exporter.py
```

实际实施不为目录形式强制拆薄文件；按明确职责合并，避免包装层和文件膨胀。

### 3.2 Web 所有者

```text
web/backend/smarttest_web/audit/
├── registry.py
├── jira_adapter.py
├── confluence_adapter.py
└── api_models.py
```

Web 只管理凭证、Session、内存任务状态、缓存 Adapter、API 和下载传输。

## 4. Core 数据端口

```text
JiraAuditIssueSource
├── resolve_input(text) -> JiraAuditScope
├── list_issues(scope) -> tuple[Issue, ...]
└── load_details(issue, IssueDetails) -> Issue

ConfluenceAuditProjectSource
├── refresh_projects(scope) -> tuple[Project, ...]
├── load_project_details(project_id, ProjectDetails) -> Project
├── load_current_page(page_id) -> ConfluencePageDocument
└── load_page_versions(page_id, AuditPeriod) -> tuple[ConfluencePageDocument, ...]
```

Core Use Case 只依赖这些 Protocol。Web Adapter 使用现有 Gateway、Mapper 和 Cache Service 实现端口。

取消使用 Core 可识别的 `CancellationToken.raise_if_cancelled()`。Core 在批量对象、页面和规则边界检查取消；Web 只设置 token。

## 5. Jira Issue 扩展

确定性规则需要 `creator` 与 `components`，因此扩展 Jira 专属 `Issue`：

```text
Issue
├── creator: PersonRef | None
└── components: tuple[NamedValue, ...]
```

SQLite 增加：

```text
jira_issues
├── creator_identity
├── creator_account
└── creator_display_name

jira_issue_components
├── issue_id
├── component_id
└── component_name
```

这些字段不放入 `custom_fields`。Schema 仍属于可废弃当前态缓存，版本变化直接重建 Jira 缓存组件。

## 6. Jira 手动审查

### 6.1 输入

Core 负责：

- 解析原始 JQL。
- 解析 Jira Issue URL。
- 解析带 JQL 的搜索 URL。
- 解析 Filter URL 或 Filter ID。
- 校验 URL host 必须匹配配置的 Jira host。
- 通过端口验证 JQL 和权限。

### 6.2 数据流

```text
输入 JQL / URL / Filter
→ Core 解析并验证
→ Gateway 分页查询最新基础 Issue
→ 每页 Mapper 转换并 upsert SQLite
→ Core 按 creator 判断审查资格
→ 只为符合资格的 Issue 请求 description
→ 有效 description 缓存直接复用
→ UNLOADED/STALE 时刷新并写 SQLite
→ Core 执行确定性规则
→ 进程内 AuditReport
→ 服务端一次调用 Core 导出 XLSX
→ 公共 DownloadButton 下载
```

每次手动审查都执行一次远端基础 JQL，以获得最新候选集合；不删除本次查询未返回的其他缓存 Issue。分页中途失败时，已完成页面保留在缓存，本次任务失败且不生成不完整报告。

### 6.3 确定性规则

- Summary 包含 4–6 个方括号分组。
- 最后四组依次表示客户、CHIP、系统版本和模块。
- 冒号后存在非空问题描述。
- 至少一个 Component。
- Description 包含 Steps to reproduce、Actual results、Expected results、Comparison 和 Notes。
- 复现概率为百分比、分数或明确文字次数。
- Notes 包含 HW info 和 SW info。
- 第二套 Description 表格每行测试信息非空。
- 保留现有中英文标题、全角符号和格式兼容规则。
- 按现有 `personnel.json` FAE-QA 活跃人员判断审查资格。

阶段一模型不保留无业务含义的 AI 状态字段。

### 6.4 Jira API

```text
POST /api/audits/jira
GET  /api/audits/jira/{audit_id}
POST /api/audits/jira/{audit_id}/cancel
POST /api/audits/jira/{audit_id}/export
```

创建请求只包含 `input`。审查成功后服务端自动生成一次 XLSX，任务进入 `completed` 后启用下载；`export` 只返回该任务已生成的统一下载物，不再次执行审查或导出。失败、取消不提供下载。

状态：`queued`、`running`、`completed`、`failed`、`cancelled`。

阶段：`resolving_input`、`fetching_issues`、`loading_details`、`rule_auditing`、`finalizing`、`exporting`。

### 6.5 Jira 页面

Jira 页面只保留 Web Jira Review：

- 卡片内全宽 JQL/URL 输入。
- 操作栏 Start、Cancel、公共 DownloadButton。
- 公共进度组件显示 stage、processed/total；准备阶段 total=0 时不定进度，成功/失败/取消统一终态。
- 不展示旧 Client Report Center、Results 卡、结果筛选、逐条结果或 Confirm。
- 保留原 Core Jira 报告格式、生成时间和规则。
- 不提供修改 Jira 的入口。

## 7. Confluence 页面职责与布局

Confluence 页面继承两个功能，共用项目过滤器：

1. 展示过滤后的项目、各 Owner 和后续扩展的项目详细信息。
2. 对已应用的项目范围执行每周项目更新审查。

页面顺序固定：

```text
Project Filters
├── 筛选器
└── Apply Filters / Reset

Weekly Review
├── Start Date / End Date
├── Review Filters
├── 简单进度或错误状态
└── 公共 DownloadButton

Project Information
├── 过滤后的项目
├── Major FAE QA / FAE QA / QA Reviewer 等 Owner
└── 后续项目详细信息
```

交互约束：

- Apply Filters 只刷新项目展示，不执行周审查，不使用时间窗口。
- Reset 只重置项目过滤器，不修改审查时间窗口。
- 时间窗口只响应 Review Filters，修改日期不刷新项目展示。
- Review Filters 使用最近一次 Apply Filters 已得到的项目集合，以及当前审查时间窗口。
- 未 Apply 的筛选器修改不参与本次 Review。
- Web 不展示 Weekly Review 的 Findings、统计或 Excel 预览。

## 8. Confluence 手动审查

### 8.1 当前态与临时材料

SQLite 保存：Project 基础字段、Owner/角色、当前来源页面引用、当前页面版本和当前提取字段。

一次审查临时使用：审查周期内页面版本列表、指定历史版本正文、页面区域变化和规则证据。临时材料不写 SQLite，任务结束后释放。

```text
ProjectAuditMaterial
├── project: Project
├── period: AuditPeriod
└── points: tuple[AuditPointMaterial, ...]

AuditPointMaterial
├── rule_id
├── page: ConfluencePageRef
├── current_region
├── period_versions
└── changed_regions
```

### 8.2 数据流

```text
最近一次已应用项目集合 + 时间窗口
→ 刷新命中项目的基础当前态并写 SQLite
→ 按需读取 roles/evidence
→ 缺失或过期时刷新并写 SQLite
→ Core 定位八个审查点来源页
→ 临时获取审查周期内必要页面版本
→ Core 提取区域并执行确定性规则
→ 进程内 AuditBatch
→ Core 按产品线生成 XLSX
→ Web 打包 ZIP 并提供统一下载
```

取消停止后续项目和页面请求；已写当前态保留，不输出不完整文件。

### 8.3 时间窗口

默认上一完整周：上周一 00:00 至本周一 00:00，时区 `Asia/Shanghai`，结束边界不包含。允许手工修改开始与结束日期，Core 校验开始必须早于结束并构造 `AuditPeriod`。不恢复 scheduled reporting window。

### 8.4 八个更新点

1. Phase Status。
2. Summary。
3. Task Arrangement of Important Test。
4. Blocking QA Testing Items。
5. Test Plan.Category。
6. Test Environment Setup and Precautions。
7. Summary of Experience and Typical Cases。
8. Test Report Store。

状态：`updated`、`not_updated`、`invalid_format`、`failed`、`unknown`。

同时恢复 Basic Information 定位，Major FAE QA、FAE QA、QA Reviewer 提取，多人展开与去重，缺少 QA 的明确结果，以及页面不存在、不可读、区域无法识别时的 Finding 和来源链接。

### 8.5 Confluence API

```text
POST /api/audits/confluence
GET  /api/audits/confluence/{audit_id}
POST /api/audits/confluence/{audit_id}/cancel
POST /api/audits/confluence/{audit_id}/export
```

创建请求包含最近一次已应用过滤范围、可选项目 ID，以及 startDate/endDate。`projectIds` 为空时审查全部已应用项目。

状态：`queued`、`running`、`completed`、`exported`、`failed`、`cancelled`。

阶段：`refreshing_projects`、`loading_details`、`locating_pages`、`loading_versions`、`rule_auditing`、`finalizing`。

### 8.6 Confluence 输出

Core 按产品线生成独立 XLSX；Web 将文件打包成单个 ZIP：

```text
Confluence_Weekly_Review_<start>_<end>_<timestamp>.zip
├── DOPL_<audit_id>.xlsx
├── TV_<audit_id>.xlsx
└── OOPL_<audit_id>.xlsx
```

Web 只展示进度、错误和一个 DownloadButton，不展示审查结果。

## 9. 进程内任务

```text
ManualAuditRegistry
├── create(source, session_id)
├── progress(audit_id)
├── complete(audit_id, result)
├── fail(audit_id, error_code)
├── cancel(audit_id)
└── get(audit_id, session_id)
```

每个 Session 同时最多运行一个 Jira 和一个 Confluence 任务，两者互不阻塞。任务和结果不写数据库，服务重启后允许丢失。Session 不得读取其他 Session 的任务。后台异常必须进入稳定终态，不能永久停留在 running。

## 10. 统一下载

全 Web 只有一个后端下载机制和一个公共前端按钮组件：

```text
Core Exporter
→ Web DownloadArtifactService
→ GET /api/downloads/{download_id}
→ frontend DownloadButton
```

```text
DownloadArtifact
├── id
├── session_id
├── file_path
├── file_name
└── media_type
```

规则：

- 下载出口统一检查 Session、归属、文件存在性、Content-Type 与 Content-Disposition。
- 同一任务重复导出复用已生成文件。
- Jira 下载单个 XLSX；Confluence 下载单个 ZIP。
- logout 删除该 Session 的临时下载物。
- 正常退出清理临时目录，异常退出遗留文件在下一次启动清理。
- 不建立下载历史表。

公共 `DownloadButton` 统一中性文案 Download、样式、图标、loading、disabled、重复点击、错误与 Session 失效处理，接入 Jira 与 Confluence 周审查。页面不得自行拼下载 URL 或重复实现文件响应逻辑。现存报告下载 API 继续复用该下载服务，但不恢复 Jira 页旧报告中心。

## 11. 缓存一致性

Jira 每次 Review 远端执行一次 JQL并逐页 upsert 核心数据；revision 变化使已加载详情转为 STALE，只为符合资格的 Issue 加载 description。取消不删除已写缓存。

Confluence Review 只刷新最近一次 Apply 命中的项目；当前 Project、roles、evidence 缺失或过期时写入 SQLite。页面版本正文仅作临时输入，不入库。Apply 与 Review 始终分离。

## 12. 错误语义

稳定错误码：

```text
invalid_input
authentication_failed
permission_denied
not_found
rate_limited
remote_unavailable
mapping_failed
audit_failed
export_failed
cancelled
download_expired
```

- 输入错误不创建任务。
- Jira 单个 Issue 映射失败使任务失败，已写缓存保留。
- Confluence 单项目失败产生 failed Finding，其他项目继续。
- 认证或整体权限失败使任务失败。
- Jira 自动导出失败使任务失败，不提供下载；用户重新点击 Start 发起新任务。
- Confluence 导出失败保留任务结果供手动再次下载，不自动重试。
- 已失效下载返回 download_expired，不恢复旧 Session 下载物。
- 响应、日志和数据库不得包含密码、Cookie、Token 或完整第三方异常对象。

## 13. 验收标准

### 13.1 Jira

- JQL、Issue URL、Filter URL 可解析，错误输入不启动任务。
- Issue 分页逐页写入 SQLite。
- creator、components 正确持久化。
- 只有符合资格的 Issue 加载 description。
- 有效 description 缓存不重复访问 Jira，revision 变化刷新过期详情。
- 确定性结果与旧实现一致。
- 一次 Start 只执行一次审查和一次自动 XLSX 导出；成功后启用下载，失败/取消禁用。

### 13.2 Confluence

- Apply Filters 只刷新 Project Information。
- 时间窗口不影响项目筛选。
- Review Filters 使用最近一次已应用范围。
- Project、roles、evidence 正确写入缓存。
- 页面历史版本和正文不写入 SQLite。
- 八个更新点结果与旧实现一致。
- 单项目失败不终止整个批次。
- 页面不展示 Findings。
- 一个 DownloadButton 下载 ZIP，每个产品线一个 XLSX。

### 13.3 公共能力

- 同 Session 重复运行任务被拒绝。
- 不同 Session 任务和下载物隔离。
- 取消后不继续新网络请求，已写缓存不回滚。
- 下载按钮样式和行为统一。
- Jira/Confluence 复用唯一进度组件与 DownloadButton，不保留 Jira 结果/确认协议。
- 不存在定时任务、历史审查表、结果持久化或 AI 调用。
- 自动化测试不访问真实 Jira、Confluence 或 AI。

## 14. 实施检查清单

- [ ] 以测试先行扩展 Jira `Issue`、Mapper 和当前态 Schema 的 creator/components。
- [ ] 恢复并重构 Core Jira 确定性规则、输入解析、Use Case 和 XLSX Exporter。
- [ ] 建立 Web Jira Audit Adapter、任务 API 和页面交互。
- [ ] 恢复并重构 Core Confluence 周期、八个规则、Use Case 和 XLSX Exporter。
- [ ] 建立 Web Confluence Audit Adapter、任务 API、页面分层与 ZIP 导出。
- [ ] 建立统一 ManualAuditRegistry、DownloadArtifactService、下载 API 和公共 DownloadButton。
- [ ] Jira 页收敛为手动审查单一入口，成功后自动生成报告，复用公共进度和下载组件。
- [ ] 删除恢复过程中产生的旧 Client、调度、历史、重复网络或兼容代码。
- [ ] 完成 Core、Web backend、frontend 的行为测试和真实环境验收准备。
- [ ] 执行范围测试、前端测试、无联网导入检查、`git diff --check` 和最终差异审查。
