# Web Jira 与 Confluence 两层数据存储设计

## 1. 背景与目标

Web 端需要把 Jira `Issue` 与 Confluence `Project` 的业务数据保存到 SQLite。系统采用“两层结构”：当前态缓存服务现有业务，历史态用于未来的项目历史查询。

当前仍处于调试阶段，既有缓存尚未上线，可以直接失效和重建。本阶段以简化并完成当前业务为主，不迁移或兼容旧缓存数据。

本阶段目标：

- 为 Jira `Issue` 建立当前态缓存。
- 重构 Confluence `Project` 当前态缓存，使其与新领域模型一致。
- 保存基础字段和按需加载的 `DetailSection`。
- 保持 Jira 与 Confluence 的业务边界独立。
- 预留历史仓储接口，但不实现历史存储或调用链路。

## 2. 范围边界

### 2.1 本阶段实现

- Jira 与 Confluence 独立的 Cache Service 和 Repository。
- 当前态 SQLite 表、索引、外键和 Schema 生命周期。
- 基础对象与懒加载详情的持久化和还原。
- 按需读取、刷新、失效及事务写入。
- Web Jira/Confluence 查询路径接入当前态缓存。
- 历史仓储接口声明。

### 2.2 本阶段不实现

- 历史表、历史写入、版本查询、比较或恢复。
- 定时同步、后台任务队列、自动重试和 TTL 策略。
- 旧缓存数据迁移或兼容读取。
- Redmine 数据缓存。
- Jira/Redmine 通用 `Issue`，或 Jira/Confluence 通用业务 Repository。

## 3. 总体架构

```text
Web Service
│
├── JiraIssueCacheService
│   ├── JiraGateway
│   ├── JiraIssueRepository
│   └── IssueHistoryRepository       仅声明，不注入、不调用
│
├── ConfluenceProjectCacheService
│   ├── ConfluenceGateway
│   ├── ConfluenceProjectRepository
│   └── ProjectHistoryRepository     仅声明，不注入、不调用
│
└── WebDatabase
    ├── SQLite 连接与事务
    └── Schema 创建与组件版本管理
```

职责约束：

- `core` 领域对象不依赖 SQLite。
- Gateway 只负责第三方网络访问，不直接写数据库。
- Mapper 负责第三方对象向领域对象转换。
- Repository 负责领域对象与当前态数据库记录互转。
- Cache Service 编排缓存读取、远端刷新、写入和失效。
- Web API 只负责参数和响应转换，不直接执行 SQL。
- Jira 与 Confluence 只共享数据库连接、事务和 Schema 基础设施。

建议目录：

```text
web/backend/smarttest_web/
├── database.py
├── schema.py
├── jira/
│   ├── cache_service.py
│   ├── issue_repository.py
│   ├── history_repository.py
│   └── schema.py
└── confluence/
    ├── cache_service.py
    ├── project_repository.py
    ├── history_repository.py
    └── schema.py
```

现有 `confluence_repository.py` 由上述结构替代，不继续混合建表、SQL、映射和同步编排。

## 4. 历史层预留

仅声明以下边界：

```text
IssueHistoryRepository
└── append(issue: Issue) -> None

ProjectHistoryRepository
└── append(project: Project) -> None
```

本阶段不提供 SQLite 实现，不创建快照表，不向 Cache Service 注入接口，不在任何同步路径调用，也不提供 NoOp 实现。后续根据明确的历史需求决定快照粒度、保存时机、查询方式和清理策略。

## 5. Jira 当前态表

### 5.1 核心表

`jira_issues`：

- `issue_id`，主键。
- `issue_key`，唯一。
- `web_url`、`summary`。
- `project_id`、`project_key`、`project_name`。
- `status_id`、`status_name`。
- `issue_type_id`、`issue_type_name`。
- `priority_id`、`priority_name`。
- `assignee_identity`、`assignee_account`、`assignee_display_name`。
- `reporter_identity`、`reporter_account`、`reporter_display_name`。
- `created_at`、`updated_at`。
- `source_revision`、`cached_at`。

`jira_issue_labels`：

- `issue_id`，外键指向 `jira_issues`。
- `label`。
- 联合主键：`(issue_id, label)`。

### 5.2 明细状态

`jira_issue_detail_states`：

- `issue_id`，外键指向 `jira_issues`。
- `section_name`：`description`、`comments`、`attachments`、`links`、`custom_fields`。
- `state`：`unloaded`、`loaded`、`stale`、`failed`。
- `source_revision`、`error_code`、`cached_at`。
- 联合主键：`(issue_id, section_name)`。

### 5.3 明细数据

- `jira_issue_descriptions(issue_id, content_json)`，`issue_id` 为主键和外键。
- `jira_issue_comments`：以 `(issue_id, comment_id)` 为主键，保存 `body_json`、作者及创建/更新时间。
- `jira_issue_attachments`：以 `(issue_id, attachment_id)` 为主键，保存文件名、URL、大小和作者。
- `jira_issue_links`：以 `(issue_id, link_id)` 为主键，保存链接类型、方向及目标 `IssueRef`。
- `jira_issue_custom_fields`：以 `(issue_id, field_key)` 为主键，保存 `value_json`。

富文本、评论正文和自定义字段采用 JSON，是因为第三方结构不稳定；常用筛选字段保持关系型列。

## 6. Confluence 当前态表

### 6.1 核心表

`confluence_projects`：

- `confluence_id`，主键。
- `project_id`，唯一。
- `name`。
- `product_space_key`、`product_space_name`、`product_space_url`。
- `catalog_page_id`、`catalog_page_title`、`catalog_page_url`、`catalog_page_version`。
- `status_id`、`status_name`。
- `stage_id`、`stage_name`。
- `support_mode_id`、`support_mode_name`。
- `customer_summary`。
- `source_revision`、`cached_at`。

`confluence_project_owners` 保存 `owner_summary`，以项目标识与人员标识组成联合主键。

### 6.2 明细状态

`confluence_project_detail_states`：

- `confluence_id`，外键指向 `confluence_projects`。
- `section_name`：`roles`、`milestones`、`hardware`、`software`、`facts`、`evidence`。
- `state`、`source_revision`、`error_code`、`cached_at`。
- 联合主键：`(confluence_id, section_name)`。

### 6.3 明细数据

- `confluence_project_roles`：保存角色标识和名称。
- `confluence_project_role_people`：保存角色下人员，并外键关联角色。
- `confluence_project_milestones`：以 `(confluence_id, milestone_key)` 为主键。
- `confluence_project_fields`：统一保存 `hardware`、`software`、`facts` 的字段，主键为 `(confluence_id, section_name, field_key)`，值为 `value_json`。
- `confluence_project_evidence`：以 `(confluence_id, source, page_id)` 为主键，保存来源页引用。

## 7. 同步辅助表

同步状态独立于领域对象：

- `jira_sync_state(scope_key, cursor, last_synced_at, last_error)`。
- `confluence_sync_state(scope_key, cursor, last_synced_at, last_error)`。

`scope_key` 为主键。当前只保存实际使用的游标、时间和错误，不提前设计任务队列、重试次数或历史日志。

## 8. Repository 接口

### 8.1 JiraIssueRepository

```text
get(issue_key, details) -> Issue | None
list(query, page, page_size) -> IssuePage
save_core(issues) -> None
replace_description(issue_key, section) -> None
replace_comments(issue_key, section) -> None
replace_attachments(issue_key, section) -> None
replace_links(issue_key, section) -> None
replace_custom_fields(issue_key, section) -> None
mark_details_stale(issue_key, sections) -> None
delete(issue_key) -> None
clear() -> None
```

### 8.2 ConfluenceProjectRepository

```text
get(project_id, details) -> Project | None
list(query, page, page_size) -> ProjectPage
save_core(projects) -> None
replace_roles(project_id, section) -> None
replace_milestones(project_id, section) -> None
replace_hardware(project_id, section) -> None
replace_software(project_id, section) -> None
replace_facts(project_id, section) -> None
replace_evidence(project_id, section) -> None
mark_details_stale(project_id, sections) -> None
delete(project_id) -> None
clear() -> None
```

Repository 使用明确的领域类型，不暴露 SQLite 行、字典或通用 `replace_section(name, Any)` 接口。

## 9. Cache Service 接口

```text
JiraIssueCacheService
├── list_issues(...)
├── get_issue(issue_key, details)
├── refresh_issues(scope)
├── refresh_issue(issue_key, details)
├── invalidate_issue(issue_key)
└── clear()

ConfluenceProjectCacheService
├── list_projects(...)
├── get_project(project_id, details)
├── refresh_projects(scope)
├── refresh_project(project_id, details)
├── invalidate_project(project_id)
└── clear()
```

列表只查询基础对象。详情调用方必须通过 `IssueDetails` 或 `ProjectDetails` 明确请求 section，不因一个详情请求加载其他详情。

## 10. 数据流程

### 10.1 列表

缓存存在时，Repository 直接分页读取当前态。缓存不存在或调用方主动刷新时，Gateway 获取基础数据，Mapper 转换，Repository 在事务内写入核心表，之后再执行分页查询。列表流程不加载大体量明细。

### 10.2 单条详情

Cache Service 检查调用方请求的各个 section：

- `LOADED` 且 revision 有效：直接使用缓存。
- `STALE`：返回旧值并保留过期状态。
- `FAILED`：返回失败状态以及可能存在的旧值。
- `UNLOADED` 或主动刷新：仅请求该 section，并在事务中替换数据和状态。

### 10.3 基础对象刷新

- `source_revision` 未变化：仅更新 `cached_at`。
- `source_revision` 变化：更新核心字段，并把已加载详情标记为 `STALE`，不立即拉取全部详情。
- 第三方没有可靠 revision 时使用 `updated_at`；两者都没有时，仅主动刷新覆盖当前态。

### 10.4 明细事务

集合明细在单个事务中删除旧行、插入新行并更新 section 状态。任一步失败则完整回滚。单值 description 使用同一事务 upsert 数据和状态。

## 11. 失败处理

- 第三方请求失败不删除已有缓存。
- 有旧数据时保留旧值，section 标记为 `FAILED`。
- 无旧数据时只记录 `FAILED` 与稳定错误码。
- 数据库失败时回滚并向 Web API 暴露错误。
- 单个详情失败不影响核心对象和其他详情。
- 列表同步中单个对象转换失败时，其余对象仍可入库，同步结果必须返回失败项，不静默忽略。

稳定错误码包括：

```text
authentication_failed
permission_denied
not_found
rate_limited
remote_unavailable
mapping_failed
database_failed
```

数据库不保存第三方原始异常对象。

## 12. 失效与删除

```text
invalidate_issue(issue_key)
invalidate_project(project_id)
clear_jira_cache()
clear_confluence_cache()
```

- 删除核心行时通过外键级联删除其当前明细。
- 清理操作仅影响对应业务缓存和同步状态。
- Jira 与 Confluence 的清理互不影响。
- 不自动清理凭证、Web Session 或用户偏好。
- 不触及未来的历史 Repository。

## 13. Schema 生命周期

`smarttest_schema(component, version)` 以 `component` 为主键，独立记录：

```text
jira_cache        -> version 1
confluence_cache  -> version 1
```

规则：

1. 无组件版本时创建新表。
2. 版本一致时正常使用。
3. 版本不一致时只删除并重建该组件缓存表。
4. 重建 Jira 不影响 Confluence，反之亦然。
5. 缓存重建不影响 `web_sessions`、`user_preferences` 和 `web_credentials`。
6. 旧 Confluence 缓存直接失效，不迁移数据。
7. 每个连接启用 `PRAGMA foreign_keys = ON`。
8. 建表和组件版本写入位于同一事务。

## 14. 验收标准

1. 新数据库能够完整建表，重复初始化无错误。
2. 旧 Confluence Schema 能按组件直接失效重建。
3. 核心 `Issue`、`Project` 数据库往返后字段不丢失。
4. 每种 `DetailSection` 状态都能正确还原。
5. 只请求指定详情，不触发其他第三方请求。
6. revision 变化只将已经加载的详情标记为 `STALE`。
7. 明细替换失败时事务完整回滚。
8. 远端失败时保留旧值并标记 `FAILED`。
9. 删除对象能够级联删除当前明细。
10. 清理 Jira 不影响 Confluence，反之亦然。
11. Schema 重建不影响 Session、凭证和用户偏好。
12. Web API 的分页、筛选和详情返回保持可用。
13. 自动化测试不访问真实 Jira 或 Confluence。
14. 不创建历史表，不调用历史接口。

## 15. 实施检查清单

实施遵循测试先行；每个任务先增加一个会因目标能力缺失而失败的行为测试，确认失败原因正确后再写最小实现。任务之间不提交临时版本，最终仅在 Coco 完成功能确认并下达交付指令后提交。

### 任务 1：共享数据库与组件化 Schema

目标文件：

- 修改 `web/backend/smarttest_web/database.py`，统一连接、事务和 `foreign_keys` 设置。
- 新建 `web/backend/smarttest_web/schema.py`，管理 `smarttest_schema(component, version)`。
- 新建 `web/backend/smarttest_web/jira/schema.py`。
- 新建 `web/backend/smarttest_web/confluence/schema.py`。
- 新建或扩展 `web/backend/tests/test_cache_schema.py`。

步骤：

- [ ] 写新库初始化、重复初始化、组件版本不一致重建和业务外表保留测试。
- [ ] 运行 `python -m pytest web/backend/tests/test_cache_schema.py -q`，确认测试因组件化 Schema 尚未实现而失败。
- [ ] 实现共享事务和两个业务组件的当前态表。
- [ ] 运行同一测试，确认建表、重建隔离和外键行为通过。

### 任务 2：Jira 当前态 Repository

目标文件：

- 新建 `web/backend/smarttest_web/jira/__init__.py`。
- 新建 `web/backend/smarttest_web/jira/issue_repository.py`。
- 新建 `web/backend/smarttest_web/jira/history_repository.py`，仅声明接口。
- 新建 `web/backend/tests/test_jira_issue_repository.py`。

步骤：

- [ ] 写 `Issue` 核心字段、标签及每种 `DetailSection` 的 SQLite 往返测试。
- [ ] 写 section 原子替换、失败回滚、级联删除和 clear 隔离测试。
- [ ] 运行 `python -m pytest web/backend/tests/test_jira_issue_repository.py -q`，确认测试因 Repository 缺失而失败。
- [ ] 实现明确类型的 Jira Repository 方法和行映射，不增加通用实体层。
- [ ] 声明 `IssueHistoryRepository.append(issue)`，不实现数据库类，不接入调用链。
- [ ] 运行同一测试并确认通过。

### 任务 3：Confluence 当前态 Repository 重构

目标文件：

- 新建 `web/backend/smarttest_web/confluence/__init__.py`。
- 新建 `web/backend/smarttest_web/confluence/project_repository.py`。
- 新建 `web/backend/smarttest_web/confluence/history_repository.py`，仅声明接口。
- 修改或删除被替代的 `web/backend/smarttest_web/confluence_repository.py`。
- 重构 `web/backend/tests/test_confluence_repository.py`。

步骤：

- [ ] 先把现有持久测试改为面向 `Project` 核心字段和六种详情的行为测试。
- [ ] 补充 section 原子替换、失败回滚、级联删除和与 Jira 清理隔离测试。
- [ ] 运行 `python -m pytest web/backend/tests/test_confluence_repository.py -q`，确认新契约因实现缺失而失败。
- [ ] 实现新 Project Repository，并删除旧表映射及旧兼容读取。
- [ ] 声明 `ProjectHistoryRepository.append(project)`，不实现数据库类，不接入调用链。
- [ ] 运行同一测试并确认通过。

### 任务 4：按需加载 Cache Service

目标文件：

- 新建 `web/backend/smarttest_web/jira/cache_service.py`。
- 新建 `web/backend/smarttest_web/confluence/cache_service.py`。
- 修改 `web/backend/smarttest_web/confluence_sync.py`，复用新服务而非直接操作旧 Repository。
- 新建 `web/backend/tests/test_jira_cache_service.py`。
- 新建 `web/backend/tests/test_confluence_cache_service.py`，并按新边界调整 `test_confluence_sync.py`。

步骤：

- [ ] 写列表不加载详情、只加载请求 section、revision 变化标记已加载详情为 `STALE` 的测试。
- [ ] 写远端失败保留旧值并标记 `FAILED`、单详情失败不影响其他详情的测试。
- [ ] 运行三个目标测试文件，确认因 Cache Service 尚未实现而失败。
- [ ] 用现有 Jira/Confluence Gateway 和 Mapper 实现最小编排，不复制第三方调用或领域映射。
- [ ] 保持历史接口完全旁路，不注入、不调用。
- [ ] 运行三个目标测试文件并确认通过。

### 任务 5：Web API 接入与旧代码清理

目标文件：

- 修改 `web/backend/smarttest_web/app.py`。
- 修改 `web/backend/smarttest_web/project_facts_api.py`。
- 按实际调用关系修改 `web/backend/smarttest_web/service.py`、`queries.py` 或相关依赖装配文件。
- 修改 `web/backend/tests/test_api.py`、`test_queries.py` 及相关现有 API 测试。
- 删除仅服务旧缓存、旧迁移或重复同步链路的代码和测试。

步骤：

- [ ] 先写或调整 Web 分页、筛选、详情选择和缓存失效的可观察行为测试。
- [ ] 运行相关 API 测试，确认因 Web 尚未接入新服务而失败。
- [ ] 将现有 Jira/Confluence Web 路径接到各自 Cache Service，不改变无关路由行为。
- [ ] 删除被新结构替代的旧缓存、旧兼容和旧迁移代码；保留 Session、凭证和用户偏好所有者。
- [ ] 运行 Web API、Repository、同步和既有 Session/凭证测试并确认通过。

### 任务 6：最终验收与清理

- [ ] 运行 Jira/Confluence Core 领域与 Gateway 相关测试，验证 Web 缓存未反向污染 `core`。
- [ ] 运行 `python -m pytest web/backend/tests -q`。
- [ ] 执行不联网的 Web 启动/import 冒烟检查。
- [ ] 扫描并确认没有历史表、历史接口调用、旧缓存兼容分支、临时日志和废弃尝试。
- [ ] 执行 `git diff --check`。
- [ ] 由 Atlas 按范围检查 `git status`、`git diff --stat` 和相关差异，分别给出 Functional Acceptance 与 Code Quality 结论。

## 2026-08-31 补充：共享缓存与账号权限映射

Coco 已确认：业务数据始终一份；Confluence 不同账号按权限读取、更新其中的资源。切换账号先按数据库内上次确认的权限映射读取缓存，再后台刷新一次动态列表和映射。不恢复周期刷新，不自动执行详情加载或审查。后续收紧范围：Jira 暂不维护账号权限映射，继续使用原共享数据库缓存路径。

### 实现边界

- 保留现有 Jira/Confluence 业务表；Web 为 Confluence 增加唯一资源权限映射 owner，记录账号、平台实例、资源标识、能力/范围和确认时间，不复制正文或业务对象。所有可复用缓存及权限映射持久化到数据库；仅请求暂存、取消信号和任务进度保留在内存。
- 可见映射来自当前账号实际成功取得的远端资源。目录可见不等于所有子页面或详情可见；受限详情/成员按实际来源范围读取，不能通过共享缓存绕过远端权限。
- Confluence 缓存列表、详情、审查选中项和缓存更新均经过相同权限边界。映射为空时不授予共享旧数据的访问权限；已有映射只是上次确认范围，不声称实时 ACL。不得给 Jira CacheService、Repository 或审查 adapter 增加权限映射依赖。
- 动态目录完整成功时更新该账号对应范围；403 移除该账号对应可见关系，不删除共享数据；401 终止远端任务并要求重新认证；失败或不完整结果不得当作完整空目录撤销所有映射。
- 共享数据和该次已确认权限在同一发布事务中更新；已注销/过期 Session 的迟到结果不得发布。其他合法 Session 不受影响，不能设置全局“当前账号”。
- 前端账号变化使旧请求、结果、下载和偏好内存失效；按新账号缓存重新初始化，再单次刷新动态目录。保留现有按账号存储的偏好，只恢复新取值范围内的有效选择。Jira 不新增当前不存在的旧动态控件。
- 复用现有 Gateway、Mapper、Repository、Session、任务及下载机制，不另建 transport、重试或历史机制。权限封装限定于现有缓存 API，不建设通用策略引擎。

### 执行与验收

- [ ] TDD 覆盖 Confluence A/B 共用一条业务记录但可见集合不同、无权读写、无映射旧库数据、403/401/合法空结果；Jira 原缓存及审查路径回归通过。
- [ ] 覆盖目录与具体详情权限分离、失败不破坏其他账号的共享正常缓存。
- [ ] 覆盖失效 Session 迟到结果拒绝发布、其他有效 Session 正常使用。
- [ ] 覆盖账号切换先授权缓存后单次刷新、旧响应不渲染、无详情自动获取和偏好隔离。
- [ ] 全套 backend/frontend、相关 core 回归、lint/build、compile/import、独立本轮差异与 `git diff --check`。

该权限实现轮周配额基线剩余 99%，96% 报告、94% 暂停。该阶段未授权远端业务操作、清库或 Git 交付；后续清理交付授权以下文为准。

### 2026-08-31 前端会话生命周期定向修复

- 初始入口复用 `shellReady` 返回的已确认 Session，与 `session:ready` 事件共用幂等挂载，避免事件早于监听导致空白页面。
- 同一会话的重复确认不重建偏好 Store 或审查页面；Apply、Review 和目录响应保留筛选 DOM、选择、日期及当前 Review ID。
- 真正账号变化或 `session:changing`（包括同账号重新登录）仍立即销毁旧页面、下载与迟到响应，再按新会话初始化；不持久化历史任务，不改变 Vite 行为。
- 验证真实入口导入、重复确认时原 Review ID 继续轮询、真实切换失效、目录失败不清空已有筛选，以及全套前端测试、lint/build。本修复不继续尚未完成的后端权限接线。

### 2026-08-31 交付清理与目录契约补齐

- 本清理轮从 201 项未提交改动建立独立快照；保留此前业务重构、报告格式和时间戳。周配额基线为剩余 96%，93% 报告、91% 暂停；没有读数时不声称监控到用量。
- Coco 已批准补齐 Core 目录结果：完整成功（包括合法空表）和确定 403 返回实际完成空间范围，SQLite 仅替换当前账号映射，不删除共享项目。缺目录表或不完整业务行失败，不发布为完整空目录；401 继续要求重新认证。
- 删除无消费者旧目录解析器、`get_children` 别名、重复请求/目录/过滤器定位日志和专用汇总字段；保留统一安全 HTTP request 日志。并发目录测试以事件锁定远端执行窗口，不依赖固定 sleep。
- Jira 页面说明与后续已确认协议一致：无结果卡/筛选/Confirm，成功自动生成一次原格式 XLSX；Confluence ZIP 文件名保留时间戳。
- 完整交付门仍以整体结果为准。此前 Jira presenter/日报 components、resolution 和便携 Account 导航缺口已获 Coco 批准，于下述 Round2 定向修复。ignored 旧测试不批量纳入交付，不以旧导入/路径契约弱化正式回归。
- 已完成 backend 120 项、frontend 88 项、Core shared 与目录 209 项、凭证/翻译/边界测试 24 项；lint/build、compile/import、产品边界检查与 source 有界启动通过。桌面仅 source/offscreen 验证，不打包，不调用真实远端；整体最终验收和 Git 提交由 Atlas 执行。

### 2026-08-31 清理 Round2：正式字段与便携资源闭环

- Coco 已批准修复遗漏后交付，Atlas 负责最终验收及提交推送；Mason 不执行 Git 写操作。保留外部 `check_product_boundaries.py` 空行改动但排除提交，两份已调整的 ignored 本地旧测试不纳入提交。
- components 由正式 `Issue.components` 直接传给 presenter/日报；resolution 恢复标准 Jira `fields.resolution` 对应的可空 `NamedValue`。删除为这两个核心字段额外加载 custom_fields 的路径，以及日报无消费者的旧字段转换函数，不增加 customfield 兜底。
- resolution 加入当前态 SQLite 核心列，复用现有可失效组件 Schema 升版方式；不迁移、不清用户运行数据库。正式耐久测试覆盖远端字段选择→Mapper→展示/日报与数据库往返、清空。
- 便携 QRC 补齐 LoginWindow 已使用的公共 `AppLoadingIndicator` 和默认 Jira 页面使用的 `AppTaskProgress`，重建现有资源；实际 ToolApp source 导航回归覆盖默认 Jira 工作区实例化及 Account 打开可见登录窗口，不改登录行为。
- Web 独立 requirements 补齐与统一环境一致的 `atlassian-python-api==4.0.7`，复用现有 SDK 和依赖链。
- 整体重构与消费者接线互相依赖，建议通过最终验收后作为一个完整迁移原子提交，避免中间提交出现删除旧 owner 后 import 断链。最终测试和限制以本轮交付报告为准。
