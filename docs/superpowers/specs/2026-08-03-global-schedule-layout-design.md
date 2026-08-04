# Tool 全局计划区设计

## 目标

Tool 页面采用上下布局。顶部 `Schedule` 只展示本机当前已启用的 SmartTest Windows 计划任务；下部保持工具导航和工作区。业务工具负责计划参数配置与创建，全局 Schedule 负责统一管理和查阅。

## 归属与数据流

- Windows Task Scheduler 与各业务计划存储仍由对应业务 owner 管理。
- 新增统一的 UI Schedule 聚合 owner，消费业务 Bridge 暴露的标准计划行，不直接重复读取业务存储或 Windows Scheduler。
- 标准计划行至少包含稳定的 provider、plan id、业务标题、计划标题、启用状态、注册状态、下次/上次运行时间、最近结果、目标工具 id。
- 聚合 owner 只输出已启用的计划；没有已启用计划时输出空列表。
- 启停、刷新和打开业务工具等动作由聚合 owner 路由回注册的业务 provider，不复制业务逻辑。

## Confluence 接入

- `Project Weekly Audit` 返回 `Common Tools`，只作为项目审查业务入口。
- Project 页面保留筛选、项目选择和启用周计划所需配置。
- Project 页面删除已启用计划的列表、运行状态和停用操作；启用后由顶部 Schedule 展示与管理。
- Confluence Bridge 继续拥有计划创建、存储、Windows Scheduler 对账和启停。

## UI

- 顶部 Schedule 区横向展示已启用计划卡片，提供标题、关键状态和管理动作。
- 空状态显示：`No SmartTest Windows schedules are currently enabled.`
- 点击计划进入对应业务工具；停用后该计划从顶部区域消失，可回业务页面重新配置或启用。
- 下部左栏恢复 `Common Tools` 中的 Jira Format Audit 与 Project Weekly Audit，Custom Tools 保持不变。

## 扩展约束

- 后续 Jira、Redmine 等计划通过同一 provider 契约注册，不修改 Schedule QML 的业务分支。
- QML 不直接读取计划文件、Windows Task Scheduler 或拼接业务专用状态。
- 不保留静态 `schedule` 工具组、Confluence 专用顶部按钮或第二套计划缓存。

## 验收

- 无启用计划时顶部只有空状态描述。
- 启用 Confluence 周计划后顶部出现一条计划，Project 页面不显示重复管理行。
- 顶部计划可进入 Project Weekly Audit 并可停用；停用后顶部恢复空状态。
- Tool 分组、Confluence Bridge、QML 离屏交互、双语翻译与 QRC 验证通过。
