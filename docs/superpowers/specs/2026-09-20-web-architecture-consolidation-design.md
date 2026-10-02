# Web 架构收口与代码精简设计

## 背景与目标

近期 Web 开发持续扩展 Jira、Confluence、异步任务、SQLite 快照、缓存、Dashboard 和页面绘制。功能边界已经形成，但部分公共机制建立后，旧的局部 owner 仍被保留，导致任务状态、取消、数据库初始化、轮询和展示工具重复存在；`app.py` 与全局 CSS 也持续承担新增业务。

本轮只重构既有实现，不新增业务功能。四个并列目标在所有阶段持续有效：

1. **合并复用**：跨 Jira、Confluence、异步、数据库、缓存和前端绘制复用已有公共 owner。
2. **移除冗余**：删除重复状态机、取消令牌、任务映射、轮询、迁移入口、DOM helper、CSS 和失效兼容代码。
3. **降低耦合**：让组合根、业务服务、数据库 owner、任务 owner、快照 owner 和页面展示各自只承担本层职责。
4. **精简实现**：生产代码净减少至少 400 行；不以万能基类、薄包装、过度拆文件或测试膨胀换取表面整洁。

基线为 2026-09-20 当前主分支。改造保持外部 API、认证生命周期、缓存与查询快照语义、授权隔离、页面功能和用户可见行为不变。

## 非目标

- 不新增 Jira、Confluence、Dashboard、审查或邮件业务能力。
- 不改变筛选条件、JQL、固定卡片边界、审查规则或结果口径。
- 不改变登录、凭据保存、失效、logout 和 session 恢复规则。
- 不把 Jira 与 Confluence 的领域模型、repository 或 cache service 合成参数化万能实现。
- 不引入前端框架、ORM、迁移框架或新的运行时依赖。
- 不借重构增加回退、兜底、推断、校验或隐藏错误。
- 不重做页面视觉设计；CSS 只做所有权拆分、重复合并和确认无用代码删除。

## 总体方案

采用三个可独立验收的阶段，按依赖顺序执行。每阶段都先固定行为测试，再迁移 owner，随后删除旧实现并统计生产代码净变化。阶段之间不保留永久兼容层。

### 阶段一：异步任务唯一 owner

`core.async_tasks.AsyncTaskManager` 是进程内任务状态、进度、取消和父子关系的唯一 owner。Web 层只保留授权索引，把 `(session/account/card/business scope)` 映射到 `task_id`，不复制任务状态。

收口范围：

- `ManualAuditRegistry` 删除私有 `CancellationToken`、Future、状态机和重复进度字段；审查上下文、结果和下载 ID 仍由审查业务 owner 保存。
- `BackgroundFactsRefresh` 删除 `_jobs` 中的任务状态副本；只保存当前 scope 的 task ID 以及业务执行所需的最小非权威上下文。
- `JiraAnalyticsTasks` 与其他 scope-task 映射复用一个窄的 Web 授权索引；索引不成为第二个任务 manager。
- `ConfluenceProjectSyncCoordinator` 使用根任务和 child task 表达详情同步；并发约束进入 manager 的资源配额，不再手工维护 Future 滑动窗口。
- Release Dashboard 和 Jira release 的显式 Sync 进入同一任务协议。GET 继续只重放 SQLite；POST 只启动任务并返回安全快照，不在请求线程串行访问远端。
- Web lifespan 创建和关闭 manager；关闭后不接受新任务，有限等待现有任务并释放工作者。

必须保留：

- 任务仍按真实 session 和业务 scope 授权，其他 session 不得读取或取消。
- 普通 logout/session expiry 不删除账号持久结果；只取消对应运行时任务。
- 明确 `invalid_credentials` 才触发既有凭据失效入口。
- 根进度尺度稳定，慢 child 只作为一行子状态显示。
- 服务重启后运行时任务可丢失，SQLite 事实和有效快照仍可重放。

### 阶段二：数据库迁移唯一 owner与 API 组合根

应用启动迁移 owner 负责 SQLite schema。Repository 构造函数只接收已准备好的数据库，不再隐式建表或升级。

迁移边界：

- 迁移按组件与版本顺序执行，全部在明确事务内完成。
- 远端可重建缓存与持久业务数据采用不同升级策略。
- 账号偏好、查询快照、审查历史、测试套件和有效 Jira 卡片结果不得因普通版本升级被整表删除。
- 现有逐列 `PRAGMA table_info + ALTER TABLE` 迁入具名增量 migration；升级必须幂等。
- 启动失败如实暴露 migration 错误，不静默清库或回退旧 schema。

`app.py` 收缩为组合根：创建数据库、session、任务、repository/service，注册 router，管理 lifespan。路由按现有业务边界拆分为认证、测试套件、Jira、Confluence、Release、审查/下载、偏好与 Wi-Fi 数据。业务规则进入对应 application service 或既有 owner，router 只处理 HTTP 输入输出、依赖和错误映射。

不创建 router 基类、service locator 或通用 repository。目标是让 `app.py` 降至约 250～400 行；若为保持清晰略有浮动，以职责边界优先。

### 阶段三：前端公共机制与样式所有权

前端只合并稳定机制，业务渲染保持在业务组件内。

- 一个 task polling/controller 统一 generation、disposed、防旧响应覆盖、轮询间隔、终态判断和取消。
- `createAsyncFeedback` 是任务反馈唯一组件；页面不再各自实现同构的 busy/progress state。
- 一个极小 DOM 工具提供安全文本/属性转义和元素创建；不建立模板框架。
- Jira、Confluence、Release、邮件各自保留业务文案、结果绘制和业务动作。
- `smarttest-theme.css` 按 token、base、shell、shared components 和业务页面拆分；只把实际共享规则放入公共文件。
- `ranking-card.css` 等真正组件私有样式继续随组件维护，不并回全局 CSS。
- 删除 CSS 前必须有静态引用检查和页面测试证据；动态 class、第三方署名与深浅主题规则不得误删。

## 明确保留的封装

- Jira issue repository 与 Confluence project repository 保持独立。
- Jira 与 Confluence cache service 保持独立，仅复用已有通用错误分类或极小 helper。
- Jira filter snapshot 与 Confluence query snapshot 保持独立。
- `_QueryAccessSnapshot` 保留，用于一次查询期间固定授权视图。
- `ProjectReleaseQueryService` 保留为 Jira 与 Confluence SQLite 事实的只读组合视图 owner。
- Dashboard 与 Jira 页面继续挂载同一个 Jira Self-Test 卡片组件和同一持久结果 owner。

## 删除与新增约束

允许新增的抽象必须同时满足：至少两个现有调用方、单一职责、接口小于被替代重复机制、可独立测试。只服务一个调用方的薄包装不新增。

每阶段结束统计：

- 新增、删除、净生产代码行；
- 新增、删除、净测试代码行；
- 删除的 owner/兼容层；
- 新增公共抽象及其调用方；
- 尚未收口的已知重复。

总体验收目标为生产代码净减少至少 400 行。若阶段一、二因正规生命周期或 migration 增加必要代码，阶段三必须通过删除已确认冗余补足，但不得删除有业务价值的代码凑指标。

## 错误与兼容策略

- 公共任务 snapshot 使用机器状态；业务层负责既有错误码和用户文案。
- 旧任务不能覆盖新 scope 的 SQLite 快照或前端展示。
- 取消、失败、服务重启 interrupted 均为明确终态；不伪装成功。
- GET 不启动远端查询；Apply/Sync/Review 仍按既有数据库快照确定范围。
- 前端可丢弃展示缓存继续只用于首帧，业务动作不从中读取权威 ID。
- 不长期保留新旧路径双写、双读或 fallback；迁移完成即删除旧路径。

## 验证与验收

### 阶段一

- Core task manager：并发上限、资源配额、父子进度、取消传播、终态、关闭生命周期。
- Web：session/scope 授权、同 scope 新任务替换旧任务、跨 session 隔离、GET 不触发远端、重启 interrupted。
- Jira/Confluence/Release：缓存结果保持、明确凭据失效、取消和失败状态。
- 前端：一个主进度、慢 child 文本、旧响应不覆盖新请求。

### 阶段二

- 从当前真实 schema 副本执行升级，验证数据数量和关键快照内容不变。
- 空库初始化与重复启动幂等。
- 全部现有 API 契约、认证、偏好、快照、repository 和 release query 测试通过。
- `app.py` 不再包含领域查询、远端分页或业务状态机。

### 阶段三

- 前端单元测试、lint 和 Vite build 通过。
- Dashboard、Jira、Projects、Release、Review Email 的加载、Apply/Sync/Review、取消、失败与重进页面回显保持。
- 深浅主题、首次绘制、响应式布局和 reduced-motion 规则保持。
- CSS 删除项有引用检查证据。

### 总体交付门槛

- Functional Acceptance：所有阶段范围测试与最高实际环境验证通过，未弱化测试。
- Code Quality：唯一 owner 清晰，无平行状态/迁移/轮询流，无临时诊断、废弃尝试和无关改动，`git diff --check` 通过。
- 生产代码净减少至少 400 行，`app.py` 仅为组合根。
- 最终清理后由 Coco 确认功能完整，再按仓库规则提交、合并并推送。

## 分阶段执行清单

### 阶段一：异步任务

- [ ] 以行为测试固定现有 session/scope、进度、取消和缓存重放契约。
- [ ] 扩展既有 manager 所缺的资源配额与安全关闭能力，不建立第二套 manager。
- [ ] 统一 Web scope-task 授权索引。
- [ ] 迁移 Jira analytics、Confluence catalog/details、manual audit 和 release sync。
- [ ] 删除局部 token、Future、状态机和手工并发窗口。
- [ ] 执行后端、前端相关测试与源环境验证，统计净代码量。

### 阶段二：数据库与路由

- [ ] 以当前 schema 和空库测试固定升级及初始化行为。
- [ ] 建立启动 migration owner，迁入现有增量升级。
- [ ] 删除 repository/session/service 构造时的 schema 变更。
- [ ] 按业务 router/application service 拆分 `app.py`。
- [ ] 执行完整后端测试与启动验证，统计净代码量。

### 阶段三：前端与 CSS

- [ ] 固定现有轮询、取消、旧响应隔离和页面回显行为。
- [ ] 统一 task controller、feedback 和极小 DOM 工具。
- [ ] 删除页面局部重复机制。
- [ ] 拆分全局 CSS，执行引用审计并删除确认无用规则。
- [ ] 执行前端测试、lint、build 与主要页面源环境验证。
- [ ] 汇总全阶段生产/测试净代码量并完成残留审查。

## 风险与停止条件

- 发现需要改变业务结果、API、缓存/快照语义、凭据规则或页面交互时，立即停止并提交 Coco 决策。
- 发现现有测试与规则冲突时，先报告证据，不自行选择新行为。
- 数据迁移若无法证明无损，不执行破坏性升级。
- 任一阶段出现无法在既定重试轮次内稳定修复的根因，报告真实失败，不以兼容层掩盖。
- Mason weekly quota 基线为剩余 44%；剩余 41% 时报告，剩余 39% 或 30 分钟内下降 5 个百分点时暂停等待 Coco 确认。
