# Daily Report 后端设计

## 目标与范围

在 `tool/common/daily_report/` 实现项目日报闭环，并在 Common Tools 分类提供配置与执行前端。每个项目拥有独立计划、JQL、收件人与抄送人；独立查询 Jira、生成长日报、附加完整 Issue Excel，并通过 Outlook 独立发送。计划可立即单次发送，也可注册每日或每周 Windows 任务。

本轮实现 Common Tool 前端、后端计划模型、查询编排、快照与趋势、确定性分析、已确认的 HTML 邮件布局、折线图、Excel、Outlook 投递、每日/每周调度和后台命令。不实现 AI 文案、Canva、真实外部服务验证或项目合并邮件。

## 所有权与依赖

`tool/common/daily_report/` 是日报唯一业务 owner：

- `models.py`：日报 Issue、快照、指标、风险、行动项和分析结果；
- `plans.py`：每项目计划及原子 JSON 存储；
- `snapshots.py`：每日查询快照及趋势历史；
- `analyzer.py`：昨日对比、分布、风险、管理判断和行动建议；
- `report.py`：把分析结果组织为报告区块、HTML、趋势图和 Excel；
- `scheduler.py`：把日报计划映射为 `support.scheduling` 的每日任务；
- `service.py`：串联 Jira、分析、报告与 Outlook；
- `command.py`：后台计划执行与退出码。

依赖边界：

- `support.jira_integration` 只按 JQL 和字段要求返回 `IssueRecord`，不理解日报；
- `support.report` 提供通用报告区块 HTML 渲染、折线图和 Excel；
- `support.outlook` 构建并发送 HTML、CID 图片和附件；
- `support.scheduling` 注册、启停和查询每日任务；
- `main.py` 只路由 `--daily-report-plan <plan-id>` 到日报命令。

## 日报计划

`DailyReportPlan` 至少包含：

- `plan_id`、`project_name`、`jql`；
- `to`、`cc`、可选 `bcc`；
- `sender_name`；
- `cadence`：`manual`、`daily` 或 `weekly`；
- `send_hour`、`send_minute`，以及 weekly 使用的 `weekday`；
- `trend_days`，默认 14；
- `enabled`、`credential_ref`、`task_name`；
- 创建、更新时间及最近运行结果。

计划不保存 Jira 密码。认证引用 `WindowsCredentialStore`。计划 ID 只允许字母、数字、下划线和连字符；JQL、项目名、收件人、cadence、时间、weekday 及趋势窗口在保存前校验。前端通过 Bridge 调用业务 store 保存计划，后台命令只执行已存在计划。

## Common Tool 前端与权限

Daily Report 作为第三个 Common Tool，工具 ID 为 `daily_report`。`ToolBridge` 的可见性规则为：人员职级以 `M` 开头，或拥有 `developer` 系统角色。`chao.li` 已是 developer，因此继承全部 Common Tool 权限，不添加账号特例。其他职级不显示且不能通过 Bridge 执行 Daily Report。

`DailyReportWorkspace.qml` 只负责布局和交互，固定文本进入中英文翻译文件。`DailyReportBridge` 负责把表单映射为 `DailyReportPlan`、异步校验 JQL、保存计划、立即发送、注册/更新调度、启停计划和展示执行状态；QML 不导入 Jira、report、outlook 或 scheduling。

前端包含：

- 项目名称、JQL 多行输入；
- To、Cc、可选 Bcc 邮箱列表，支持逗号、分号或换行输入并在 Bridge 规范化；
- 发件人显示名称；
- 发送方式：立即发送、每日、每周；
- 每日/每周时间；每周额外选择星期；
- 保存配置、测试 JQL、立即发送、启用/禁用计划；
- 已保存计划列表及最近状态、下次运行时间和最后报告路径。

JQL、邮件列表和调度计划属于 Daily Report 业务配置，由 `DailyReportPlanStore` 持久化，不进入 `FrontendStateStore`。密码只使用当前登录的瞬时凭据，并在创建计划任务时写入 `WindowsCredentialStore`；不得进入 QML、FrontendStateStore、计划 JSON、日志或报告。

## Jira 数据与快照

日报向 `JiraIssueService.search_records` 请求：`key`、`summary`、`status`、`assignee`、`priority`、`labels`、`components`、`created`、`updated`；业务需要时显式请求 changelog，不把日报规则放进 integration。

主 JQL 的当前结果定义为“当前未关闭工作集”。每日成功查询后保存一个项目快照：日期、查询时间、Issue key 集合、总数及展示/分析所需字段。当天重复执行原子覆盖同日快照，不产生重复趋势点。

昨日对比使用当前日期之前最近一个成功快照，并显示其真实日期。没有基线时，报告显示“暂无昨日对比”。进入集合的 key 视为新增/重新进入，离开集合的 key 只标记为“离开当前筛选”；没有 Jira 证据时不得擅自称为 Closed。

快照按 `trend_days` 提供折线数据，并保留至少 90 天用于后续调整；报告只显示配置窗口。

## 分析规则

确定性分析包含：

- 总量及相对上一快照的变化；
- 状态、组件/模块、优先级、负责人分布；
- 新进入、离开筛选、当天更新和长时间未更新；
- 阻塞、高优先级、无人负责、停滞风险；
- 按风险分数排序的关键 Issue；
- 从上述事实生成管理判断、建议决策和交付行动项。

风险规则集中在日报 analyzer，不进入 Jira integration 或通用 report。第一阶段采用固定可测试阈值：高优先级匹配 `Highest`/`High`，停滞为 7 天未更新，阻塞状态匹配 `Blocked`/`阻塞`，无人负责为空 assignee。后续改变阈值只修改一个规则配置。

## 报告布局与折线图

邮件采用已确认的长日报信息层级：

1. 数据全景指标卡；
2. 昨日对比；
3. 最近 N 天未关闭 Issue 趋势折线图；
4. 状态、模块、优先级与停滞分布；
5. 管理判断和建议决策；
6. 交付行动；
7. 高风险与关键变化 Issue；
8. 数据口径与附件说明。

趋势图必须调用 `support.report.render_line_chart` 与 `LineSeries`，不得另写 matplotlib 绘图。横轴为快照日期，唯一序列为“未关闭 Issue”，最新点高亮并显示 KPI；输出 PNG 后通过 HTML 本地图片引用交给 Outlook 转为 CID。

`support.report` 增加最小通用邮件报告区块模型与 Outlook 兼容 HTML renderer，覆盖指标、表格、分布、文字、行动和图片区块。Daily Report 只组装区块，不拥有第二套底层 HTML/CSS 机制。完整 Issue 通过现有 `write_xlsx_table` 输出并作为附件发送。

## 执行、调度与失败语义

`DailyReportService.run(plan)` 的顺序为：加载认证 → Jira 查询 → 保存/读取快照 → 分析 → 生成 HTML/PNG/XLSX → Outlook 发送 → 更新计划结果。

Jira 查询失败时不保存当天快照；报告或邮件失败时保留已成功查询的快照，使趋势不因投递故障丢失。临时 PNG/HTML 在发送完成后清理，持久化 Excel 到日报报告目录以供追踪。

`manual` 计划不注册 Windows 任务，由前端立即调用一次。`daily` 使用 `DailyTrigger`，每天采集快照并发送。`weekly` 为保证折线图仍有每日数据点，也注册每日采集任务：每天查询并保存快照，只在计划选定的星期生成报告并发送；其他日期以成功采集结束。任务均以 `SmartTest.DailyReport.<plan-id>` 注册，启动参数为 `--daily-report-plan <plan-id>`。一个项目失败不阻塞其他项目。后台命令使用稳定退出码区分配置、认证、查询、报告和发送失败，日志不包含密码、邮件正文或完整 Jira 数据。

## 测试与验收

### 日报预览与发送确认

手动操作调整为“生成日报预览 → 用户审阅 → 发送邮件”。生成预览只要求合法的 Plan ID、项目名、JQL 和当前 Jira 凭据，不要求填写 To/Cc/Bcc，也不得调用 Outlook。生成成功后，页面内嵌展示与邮件正文一致的 HTML，并保留本次生成的 PNG 与完整 Issue Excel。

发送按钮仅在当前预览有效时启用；发送时才校验 To/Cc/Bcc，短账号统一补全 `@amlogic.com`。若 Plan ID、项目名或 JQL 在预览后发生变化，当前预览立即失效，必须重新生成。发送必须复用用户刚审阅的 HTML、内嵌图片和 Excel，不重新查询 Jira，避免预览与邮件内容不一致。预览文件由 Daily Report 业务 owner 管理，不写入 `FrontendStateStore`，新预览替换旧预览；失败时保留明确阶段状态且不暴露凭据。

所有测试离线，使用 fake Jira、fake Outlook、fake scheduler 和临时目录：

- 计划校验、原子保存、读取、结果更新；
- 快照同日覆盖、历史排序、14 日窗口、无基线与前一快照对比；
- 指标、分布、风险、行动和无证据不判 Closed；
- 折线图确实调用 `support.report.render_line_chart`，日期与数量正确；
- HTML 顺序与已确认布局一致，图片为本地引用，Excel 包含完整 Issue；
- Outlook 接收独立项目标题、To/Cc/Bcc、HTML、CID 图和 Excel；
- Daily scheduler 保持独立任务 ID、时间、参数、启停和 reconciliation；
- weekly 后台每日采集，并只在前端选择的星期发送；manual 不创建系统任务；
- M 岗与 developer 可见并可执行，其他职级不可见且 Bridge 拒绝调用；
- 表单邮件列表规范化、JQL 校验、保存、立即发送、每日/每周启停和计划状态；
- QML/Bridge/翻译/QRC 聚焦测试通过，前端不直接拥有业务逻辑或敏感值；
- `main.py` 后台路由和退出码；
- 多项目计划不合并、不共享收件人或报告文件；
- 不访问真实 Jira、Outlook 或 Windows Task Scheduler。

代码质量要求：Daily Report 业务只在 `tool/common/daily_report/`；Jira integration、report、outlook、scheduling 不包含项目特例；不重复折线图、Excel、SMTP 或 COM 机制；无临时诊断、旧路径转发和无关改动；`git diff --check` 通过。

## 实施顺序

1. 建立日报计划、业务模型和原子快照存储，包含 manual/daily/weekly，并完成同日覆盖、历史窗口和无基线测试。
2. 实现确定性分析器，覆盖昨日变化、分布、风险、管理判断和行动建议。
3. 为 `support.report` 增加本版式需要的最小邮件报告区块，复用现有折线图和 Excel。
4. 实现长日报 HTML、14 日未关闭趋势 PNG 和完整 Issue Excel。
5. 串联 Jira 查询、快照、报告与 Outlook，增加 `--daily-report-plan <plan-id>` 后台入口。
6. 使用 `DailyTrigger` 注册 daily/weekly 的每日采集任务，由 weekly 发送策略判断星期；manual 保持无系统任务。
7. 在 Common Tools 增加 Daily Report Workspace、Bridge、权限、翻译和资源，完成离线回归、源码启动、边界扫描和质量清理。

## 2026-08-06 日报展示调整

经 Coco 确认，本轮只调整日报正文展示，不改变 Jira 查询、趋势、邮件发送或完整 Excel 附件：

- 移除“昨日对比”和“今日关闭”卡片；不再展示或推断今日关闭数量。
- 将现有“优先级 / 停滞”卡片上移到第一排左侧，状态构成保留在第一排右侧。
- 第二排保留“模块分布 · Top 5”，右侧新增“问题内外部”空白卡片。当前没有可靠分类字段时不显示虚构的 0 值。
- Issue 明细按项目配置的优先级集合过滤，默认只展示 `P0`、`P1`；标题显示筛选后的条数。完整 Excel 仍包含当前 JQL 返回的全部唯一 Issue。
- 优先级配置由 Daily Report 的 `ProjectConfig` 单一拥有并持久化；本轮不新增 QML 配置控件，避免扩大交互范围。
- 日报头部不显示“vs 昨日”变化提示；状态构成饼图图例字号从 11 调整为 14。

执行清单：先增加布局、默认筛选和配置持久化回归测试并确认失败；再最小修改 `report.py` 与 `projects.py`；最后运行 Daily Report 自测试、编译检查、`git diff --check` 和 scoped diff 质量检查。

同日确认的 Workspace 与 KPI 收敛：顶部项目摘要、操作按钮、状态和进度条固定，项目编辑区、项目卡和自动选中的首个有效预览在下方统一滚动；移除项目卡的 `View preview` 入口及仅服务该入口的选择 slot，`Send now` 继续复用已生成且未过期的批次。数据全景 KPI 行删除与 hero 总数重复的“当前未关闭”卡，hero 总数保留。

计划发送时间表示邮件发送截止点。Daily Report 专用 Windows task 在该时间前 5 分钟启动（跨越零点时同步回退 weekly weekday），每次重新查询 Jira 并生成当次批次；准备完成后等待至配置发送时间再直接发送，不复用手动预览且不需人工确认。任一项目准备失败时当次不发送，继续返回现有稳定失败码 `1`。

Tool 页的 Schedule 区域根据 provider 已有的 `enabled`、`registered`、`reconciliation` 和 `nextRunAt` 显示状态及下次运行时间；Daily Report Workspace 内的计划配置表单仍是 cadence/time 的唯一配置入口。

计划日报入口使用 `smart_log` 持久记录任务入口、计划读取、凭据读取成功/失败、当次准备、发送 deadline、等待起止、发送结果和最终退出码。等待期间约每 60 秒记录剩余秒数，用最后一条 heartbeat 缩小外部强制终止的最后存活时间。日志不记录密码、邮件正文、完整 Jira 数据或收件人列表，该诊断不改变调度与发送行为。

Schedule 状态卡提供三类管理操作：`Stop / Enable` 由 Daily Report scheduler owner 同步更新 Windows task 和本地 `enabled`；`Run now` 在后台线程执行一次全新 unattended batch，跳过 deadline 等待但不改变 cadence/time/enabled，并在已有操作运行时拒绝重复启动；`Delete` 经明确确认后删除 Windows task、计划配置以及 Daily Report owner 写入的 `daily-report-batch` credential。所有操作异步执行，完成后刷新卡片状态。
调度准备提前量调整为 5 分钟：配置保存的时间仍是业务发送时间，Windows 任务触发时间仅由 Daily Report 调度 owner 换算为提前 5 分钟，周计划跨午夜时同步回退到前一天。工具页调度卡片继续显示状态、下次运行和管理操作，并补充任务类型、已启用项目名称和业务计划文本；项目内容不包含 Jira 查询或收件人信息。
