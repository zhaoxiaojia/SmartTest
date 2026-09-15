# Dashboard 团队 Jira Bug 概览卡片设计

## 1. 目标

在 Dashboard 增加一个面向管理人员的团队 Jira Bug 概览卡片，并加入系统默认布局。卡片统计当前登录账号有权限查看的全部 Jira 项目中的全部 Bug，按当前 Assignee 展示人员维度的工作量与质量指标。

本阶段只实现 Dashboard 卡片，不实现 Jira 页面的数据分布图、周期对比图，也不设计 Jira/Confluence 定时 Sync 机制。

## 2. 统计口径

- 数据范围：当前登录账号有权限查看的全部 Jira 项目。
- Bug：`Issue Type.name == "Bug"`。
- 人员归属：Issue 当前 `Assignee`。
- 未分配：REST 数据中的空 Assignee；前端显示为 `Unassigned`，作为普通统计行参与排序。
- 个人 Bug 总数：该 Assignee 名下的 Bug 数量。
- 团队占比：个人 Bug 总数 / 团队全部 Bug 总数。
- Resolved Bug：`Resolution.name == "Resolved"`；占比为该数量 / 个人 Bug 总数。
- P0 Bug：`Priority.name == "P0"`；占比为该数量 / 个人 Bug 总数。
- Invalid Bug：`Resolution.name == "Invalid"`；占比为该数量 / 个人 Bug 总数。
- 所有名称按 Jira 返回字段值匹配，不通过 Status、Status Category 或其他字段推断。
- 人员默认按 Bug 总数倒序；数量相同时按展示名稳定排序。`Unassigned` 不特殊置底。

## 3. 数据所有权与流程

### 3.1 Core Jira

Core Jira 是查询与统计口径的唯一业务 owner：

1. 使用当前登录账号的 Jira 凭据查询该账号可见的全部 Bug。
2. JQL 只约束 `issuetype = Bug`，不复用 Projects 或 Jira 页面过滤器。
3. 搜索只请求统计所需的 Issue 标识、Assignee、Priority、Resolution 与 Issue Type 字段。
4. 复用既有 JiraGateway 的并发分页搜索机制，不增加 Web 分页请求。
5. 将人员统计投影为稳定 DTO：人员标识、展示名、四项数量及其比例、团队总数和快照状态。

### 3.2 SQLite

SQLite 是账号级 Dashboard Jira 快照的持久 owner：

- 快照按 Jira 账号隔离，不按浏览器会话共享权威选择。
- 写入期间保留上一个有效快照；完整写入后再原子切换。
- 页面只读取最后一个有效快照，不能从进程内存或前端缓存恢复权威统计。
- 异步任务与进度保存在 Web 进程内存，服务重启后允许消失。
- 登录账号凭据失效或账号退出全部会话时，清除该账号对应的可复用 Dashboard Jira 快照。

### 3.3 首次加载

- 有有效账号快照：立即返回并展示，不自动访问 Jira。
- 没有账号快照：首次进入 Dashboard 时自动启动一次异步 Jira 查询。
- 查询过程中卡片展示加载状态和进度，不阻塞 Dashboard 其他组件。
- 查询成功后原位展示统计结果。
- 查询失败时展示明确错误；不静默返回空数据，也不自动重试。
- 本阶段不提供 Refresh 按钮，也不增加定时刷新或过期刷新。后续统一 Sync 机制负责更新。

## 4. Web 接口

Web 后端只负责当前登录会话解析、调用 Core owner、SQLite 快照读取以及异步任务状态转发：

- 获取当前账号的团队 Bug 概览状态与最后有效统计。
- 在无快照时幂等启动首次同步；同一账号已有运行任务时返回同一任务状态，不重复查询 Jira。
- 返回聚合 DTO，不向浏览器返回全部 Issue。
- 页面轮询已有任务状态；完成后重新读取聚合结果。

## 5. Dashboard 卡片

- 新卡片独立封装，不把 Jira 业务逻辑写入 DashboardGrid。
- 注册到既有 WidgetRegistry，并加入 `DEFAULT_DASHBOARD_LAYOUT`。
- 保持现有 Dashboard 编辑、添加、移除、拖动、保存和取消机制。
- 卡片尺寸是注册表中的固定布局属性，不支持缩放。
- 使用人员排行表展示；每行包含人员名、Bug 总数与团队占比、Resolved、P0、Invalid 的数量和个人占比。
- 人员较多时只保留卡片内容区域的一层纵向滚动，不给卡片外壳增加第二层滚动。
- 百分比由 Core 返回，前端只格式化显示，不重新计算业务口径。
- 空快照、加载中、失败、无 Bug 四种状态分别展示。

## 6. 不在本次范围

- Jira 页面的过滤结果数据分布图。
- Jira 页面的固定周期对比图。
- 手动 Refresh 控件。
- Jira/Confluence 定时 Sync、过期策略和调度管理。
- 按 Reporter、Creator、Project 或历史 Assignee 统计。
- 对 Jira 字段名称增加别名、模糊匹配或业务兜底。

## 7. 验收标准

1. 默认 Dashboard 同时包含现有 Role workload 和团队 Jira Bug 概览卡片。
2. 卡片统计当前账号可查看范围内所有 `Issue Type.name == "Bug"` 的 Issue。
3. 每个 Assignee 与 `Unassigned` 的四项数量、分母和比例符合第 2 节定义。
4. 人员按 Bug 总数倒序，`Unassigned` 按数量正常参与排序。
5. 账号之间的快照、任务和结果相互隔离。
6. 有快照时进入 Dashboard 不访问 Jira；无快照时只启动一个异步首次查询。
7. 大量 Issue 不进入浏览器，前端只接收聚合数据。
8. 查询失败不会覆盖最后有效快照，也不会显示为零数据。
9. 卡片不提供 Refresh，不实现定时刷新。
10. 卡片可以在 Dashboard 编辑模式中添加、移除、拖动，并通过保存/取消保持现有行为。
11. Core、Web 后端、前端组件与 Dashboard 注册具有覆盖关键口径和状态转换的持久测试。
