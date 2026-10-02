# Dashboard 团队 Jira Bug 概览卡片设计

## 1. 目标

在 Dashboard 增加一个面向管理人员的团队 Jira Bug 概览卡片，并加入系统默认布局。卡片统计当前登录账号有权限查看的全部 Jira 项目中的全部 Bug，按当前 Assignee 展示人员维度的工作量与质量指标。

本阶段只实现 Dashboard 卡片，不实现 Jira 页面的数据分布图、周期对比图，也不设计 Jira/Confluence 定时 Sync 机制。

## 2. 统计口径

- 数据范围：当前登录账号有权限查看的全部 Jira 项目，但 Assignee 只允许 `core/config/personnel.json` 中 `amlogic.departments.FAE-QA.employees` 的在职账号。
- Bug：`Issue Type.name == "Bug"`。
- 人员归属：Issue 当前 `Assignee`。
- QA 名单：只读取 `active != false` 且 `account` 非空的 `FAE-QA` 人员；该配置是唯一名单 owner。
- 未分配：不属于 QA 账号集合，不纳入查询或展示。
- 个人 Bug 总数：该 Assignee 名下的 Bug 数量。
- 团队占比：个人 Bug 总数 / 团队全部 Bug 总数。
- Resolved Bug：`Resolution.name == "Resolved"`；占比为该数量 / 个人 Bug 总数。
- P0 Bug：`Priority.name == "P0"`；占比为该数量 / 个人 Bug 总数。
- Invalid Bug：`Resolution.name == "Invalid"`；占比为该数量 / 个人 Bug 总数。
- 所有名称按 Jira 返回字段值匹配，不通过 Status、Status Category 或其他字段推断。
- 人员默认按 Bug 总数倒序；数量相同时按展示名稳定排序。零 Bug 人员不展示。
- 内部、配置、SQLite、API 与前端统一使用五个 canonical 产品线名称。Jira Project key 与 Confluence space/业务标签仅在 `core.product_lines` 映射 owner 定义；`FQ` 暂时排除。

## 3. 数据所有权与流程

### 3.1 Core Jira

Core Jira 是查询与统计口径的唯一业务 owner：

1. 使用当前登录账号的 Jira 凭据查询该账号可见且 Assignee 属于当前在职 `FAE-QA` 名单的 Bug。
2. JQL 同时约束 `issuetype = Bug`、QA Assignee account 集合和 `project IN (IPTV, SH, TV, OTT)`，不复用 Projects 或 Jira 页面过滤器。
3. 搜索只请求统计所需的 Issue 标识、Assignee、Priority、Resolution 与 Issue Type 字段。
4. 复用既有 JiraGateway 的并发分页搜索机制，不增加 Web 分页请求。
5. 将人员统计投影为稳定 DTO：人员标识、展示名、四项数量及其比例、团队总数和快照状态。

### 3.2 SQLite

SQLite 是账号级 Dashboard Jira 快照的持久 owner：

- 快照按 Jira 账号隔离，不按浏览器会话共享权威选择。
- 快照记录由有序 QA account 集合生成的名单指纹；配置名单变化时旧快照失效，并在下次进入 Dashboard 时自动启动一次新查询。
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
- 展示结构复用 Role workload：左侧为四个完整业务名称的产品线切换，右侧为 `Bugs`、`Resolved`、`P0`、`Invalid` 指标切换，主体为横向人员排行图。
- 图表按所选产品线与指标的数量倒序，同数时按人员展示名稳定排序；人员较多时只保留图表区域的一层纵向滚动。
- 删除原人员明细表渲染及表格专用 CSS；公共分段控件和横向 Chart.js 配置从 Role workload 提取复用，不复制第二套。
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
3. 每个有 Bug 的在职 `FAE-QA` Assignee 的四项数量、分母和比例符合第 2 节定义；其他人员、`Unassigned` 和零 Bug QA 不展示。
4. 人员按 Bug 总数倒序，同数时按展示名稳定排序。
5. 账号之间的快照、任务和结果相互隔离。
6. 有快照时进入 Dashboard 不访问 Jira；无快照时只启动一个异步首次查询。
7. 大量 Issue 不进入浏览器，前端只接收聚合数据。
8. 查询失败不会覆盖最后有效快照，也不会显示为零数据。
9. 卡片不提供 Refresh，不实现定时刷新。
10. 卡片可以在 Dashboard 编辑模式中添加、移除、拖动，并通过保存/取消保持现有行为。
11. Core、Web 后端、前端组件与 Dashboard 注册具有覆盖关键口径和状态转换的持久测试。
12. 四个产品线只统计映射 Jira Project 中的 Bug；`FQ` 不进入任何产品线。
13. Team Jira bugs 使用与 Role workload 一致的产品线/指标分段切换和横向人员排行图，不保留明细表。

## 8. 实施检查项

### 8.1 Core 聚合 owner

- [x] 在 `core/jira/services/` 新增团队 Bug 概览服务与不可变结果 DTO；输入为 Issue 集合，输出为团队总数、人员标识、展示名、四项数量及比例。
- [x] 先在 `core/testing/self_tests/shared/` 增加失败测试，覆盖 Bug 类型过滤、四项精确名称匹配、空 Assignee、百分比分母、数量倒序与同数稳定排序。
- [x] 扩展 `JiraGateway.search_all_payloads()` 的字段选择入口或复用其既有字段参数，使首次同步只获取 `id/key/issuetype/assignee/priority/resolution`，不得新增第二套分页客户端。
- [x] 运行 Core 聚焦测试并确认通过。

### 8.2 SQLite 快照与异步首次同步

- [x] 扩展 `web/backend/smarttest_web/jira/schema.py`，增加账号级团队 Bug 快照、人员聚合行及活动快照指针；外键清理与现有 Jira 表保持一致。
- [x] 在 `web/backend/smarttest_web/jira/` 增加单一 Dashboard Jira owner，负责读取活动快照、幂等启动无快照账号的首次任务、批量写入并原子激活。
- [x] 先在 `web/backend/tests/` 增加失败测试，覆盖账号隔离、已有快照零远端调用、并发首次请求只生成一个任务、失败保留旧快照、退出全部会话清理账号快照。
- [x] 复用现有异步任务注册与当前 session 凭据解析；不得保存密码、Issue ID 选择集或前端计算输入。
- [x] 运行 Web 后端聚焦测试并确认通过。

### 8.3 Web API

- [x] 在 `web/backend/smarttest_web/app.py` 增加一个团队 Bug 概览状态接口；有快照直接返回聚合 DTO，无快照时返回同一账号的首次任务状态。
- [x] 接口只返回聚合结果、状态、进度与明确错误，不返回 Issue 列表。
- [x] 增加 API 测试，证明当前登录账号凭据被使用、未认证返回 401、账号结果不串用、失败不伪装为空数据。

### 8.4 Dashboard 业务组件

- [x] 在 `web/frontend/src/widgets/` 新增独立团队 Jira Bug 概览组件，渲染加载、失败、无 Bug 与人员排行四种状态；组件只格式化 Core 返回比例。
- [x] 在 `web/frontend/src/api.js` 增加团队概览读取方法，在 `dashboard-main.js` 注册组件并提供 API 配置。
- [x] 在 `web/frontend/src/dashboard/dashboard-grid.js` 的系统默认布局中加入新卡片，登记固定 `defaultW/defaultH`，保持 `noResize`、编辑增删、拖动、保存与取消机制。
- [x] 使用单层内容滚动；不得给卡片外壳或 Dashboard 增加第二层滚动，也不得增加 Refresh 控件。
- [x] 先增加组件、Dashboard 注册和默认布局失败测试，再实现最小代码并运行前端聚焦测试。

### 8.5 交付验收

- [x] 运行全部 Web 后端测试、全部前端测试、ESLint、Vite build、Core Jira 聚焦测试和 `git diff --check`。
- [ ] 用当前登录账号在 Chrome 验证：首次加载异步进度、最终人员排序、`Unassigned`、四项数量/比例、默认布局与单层滚动。
- [x] 审查净生产代码增长，删除临时诊断、探索测试、重复任务/缓存/聚合 owner 与无业务兜底。

### 8.6 QA 范围修正

- [x] 在 Core 中复用 `core/config/personnel.json`，生成在职 `FAE-QA` account 集合及稳定名单指纹；不得在 Web 或前端复制名单。
- [x] 将首次 Jira 查询缩小为 `issuetype = Bug AND assignee IN (...)`，并在聚合入口再次拒绝名单外 Assignee；不显示零 Bug QA 或 `Unassigned`。
- [x] 快照保存名单指纹；现有全量快照或名单变化导致指纹不匹配时失效并幂等启动一次新查询。
- [x] 修复 `.dashboard-widget-card` 覆盖 GridStack 上下 inset 的样式，恢复两个卡片之间的原生 `8px` 间距。
- [x] 增加 Core、Repository、API、Dashboard 样式回归测试并复跑完整验收。

### 8.7 产品线图表改造

- [x] `core.product_lines` 单一结构定义 canonical 名称及 Jira/Confluence 外部标识，正反索引均由结构派生；JQL 使用映射中的四个 Project key，`FQ` 排除。
- [x] Core 聚合 DTO 按产品线保存人员的 Bugs、Resolved、P0、Invalid 数量；快照版本/指纹包含 Project 映射，使旧单一总表快照自动失效。
- [x] 从 Role workload 提取共享的产品线分段与横向人员排行图表现机制，两个业务 widget 只准备各自数据和指标，不复制 Chart.js 配置。
- [x] Team Jira bugs 改为四个产品线和四个指标切换，删除明细表 DOM、百分比格式化及表格专用 CSS。
- [x] 增加 Project 隔离、`FQ` 排除、指标切换、倒序、共享图表生命周期和无数据状态测试，并复跑完整验收。

### 8.8 Project 与人员归属双条件分类

- [x] 原四分布同时要求 Issue Project 通过映射 owner 得到的 canonical 名称与 Assignee canonical personnel assignment 匹配。
- [x] 新增 `Wireless Connection`分布；具有该 assignment 的人员在 `IPTV/SH/TV/OTT` 中的 Issue 统一归入该分布，不再混入原四分布。
- [x] personnel assignment 纳入名单指纹，归属变化使旧快照失效；非四 Project、无匹配 assignment 和 `Unassigned` 均排除。
- [x] 前端复用现有分段排行 owner，顶部增加文字为 `Wireless Connection` 的分段，Bugs/Resolved/P0/Invalid 四指标不变。
- [x] `core.product_lines` 统一定义五个产品线 key/显示名；Python 生产消费者引用该 owner，Team Jira payload 按 Core 顺序携带 label，前端不再硬编码同套产品线常量。
