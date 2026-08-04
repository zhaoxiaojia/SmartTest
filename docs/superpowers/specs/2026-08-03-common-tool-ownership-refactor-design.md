# Common Tool 业务归位与公共调度重构设计

## 目标

修正 Common Tool 只有前端分组、业务代码却散落在 `support/` 的所有权问题。建立根目录 `tool/common/`，将 Jira Format Audit 与 Project Weekly Audit 的业务代码归位；同时从项目周审查中抽取唯一的 Windows Task Scheduler 公共实现到 `support/scheduling/`，并将 `support/jira_integration/` 收敛为纯 Jira 数据访问能力。

本轮不实现 Daily Report、日报布局、日报分析规则或前端配置，只为后续 `tool/common/daily_report/` 建立清晰基础。

## 最终目录与所有权

```text
tool/
├── common/
│   ├── jira_format_audit/
│   └── project_weekly_audit/
└── SmartHome/
    └── redmine/

support/
├── jira_integration/
├── confluence_integration/
├── scheduling/
├── report/
└── outlook/
```

`tool/common/jira_format_audit/` 拥有格式审查模型、规则、服务和导出。`tool/common/project_weekly_audit/` 拥有项目发现条件、审查周期、业务模型、规则、计划、命令、服务和报告。QML 与 Bridge 仍位于 `ui/`，Bridge 只调用对应业务工具。

`support/` 只拥有可被多个业务复用的机制，不拥有 Common Tool 的业务规则、业务报告或业务计划。

## Jira Integration 边界

`support/jira_integration/` 输入 JQL、字段列表、分页参数以及是否加载 changelog，输出 Jira 原始或标准化数据。它负责认证、请求、分页、字段映射、错误和传输，不判断数据将用于日报、格式审查或其他业务。

现有 `support/jira_integration/audit/` 整体迁移到 `tool/common/jira_format_audit/`。迁移完成后删除旧目录；不保留兼容转发模块。`JiraAuditBridge` 和测试改为直接导入新 owner。

本轮不为未来日报预先增加尚未确认的 Jira 字段或 changelog API；只确保现有通用查询边界不依赖格式审查业务。

## Project Weekly Audit 边界

现有 `support/confluence_audit/` 中的项目周审查业务迁移到 `tool/common/project_weekly_audit/`，包括命令、发现、HTML、业务模型、周期、计划、项目集合、报告、规则和服务。

Confluence 连接与数据访问继续由 `support/confluence_integration/` 持有。`ConfluenceAuditBridge`、后台入口和测试直接导入 `tool.common.project_weekly_audit`。迁移完成后删除旧 `support/confluence_audit/` 业务目录。

## Scheduling 公共机制

将现有 `support/confluence_audit/scheduler.py` 拆分为：

- `support/scheduling/models.py`：任务定义、每日/每周触发定义和注册状态；
- `support/scheduling/windows.py`：Windows Task Scheduler COM 适配器、注册/更新、启停和查询；
- `support/scheduling/launch.py`：源码与打包环境的启动命令解析和 Windows 参数序列化；
- `support/scheduling/__init__.py`：稳定公共接口。

公共 scheduler 不认识 Confluence、Jira 或 Daily Report。调用方提供稳定任务 ID、显示说明、启动参数、触发定义和 enabled 状态。

`tool/common/project_weekly_audit/scheduler.py` 只负责把每周五 00:05 的项目审查计划映射为公共 `ScheduleDefinition`，并把公共注册状态映射回项目审查状态。现有行为、任务名前缀和已注册任务的识别保持兼容，避免在用户机器上创建重复任务。

迁移后删除项目周审查中的 COM、命令行序列化、路径比较和通用任务读写实现，不允许复制到新旧两个位置。

## UI 与后台入口

`ToolBridge` 仍将 `jira_audit` 和 `confluence_audit` 列在 Common Tools。`JiraAuditBridge`、`ConfluenceAuditBridge` 与 `ScheduleBridge` 的对外 QML 契约保持不变，本轮不修改页面布局和交互。

后台命令参数及已存在的 Project Weekly Audit 计划保持可用。只更新内部导入路径和 owner，不改变用户可见名称、计划 ID、Windows 任务名称、运行时间或报告行为。

## 迁移与删除策略

- 使用 `git mv` 或等价的可追踪移动表达所有权变化；现有用户改动必须保留。
- 先移动业务代码与测试导入，再抽取 scheduler，最后删除旧目录中的冗余。
- 不保留过渡 re-export；仓库内调用一次性迁移到新路径。
- 不修改无关 SmartHome Redmine、Daily Report、Outlook、报告布局或 UI 视觉。
- 不重建桌面安装包；只进行源码验证。

## 测试与验收

功能验收：

- Jira Format Audit 原有聚焦测试全部通过；
- Project Weekly Audit 原有模型、规则、服务、报告、计划、命令和调度测试全部通过；
- 通用 scheduling 新增离线 fake COM/adapter 测试，覆盖每日/每周触发、注册、启停、查询、参数序列化和状态校验；
- Common Tool Bridge/QML 聚焦测试通过，两个工具仍可发现和加载；
- 后台 Project Weekly Audit 命令解析和启动路径保持兼容；
- 测试不访问真实 Jira、Confluence 或 Windows Task Scheduler。

代码质量验收：

- `tool/common/` 成为两个 Common Tool 的唯一业务 owner；
- `support/jira_integration/` 不再包含格式审查规则、报告或业务服务；
- `support/scheduling/` 不包含任何 Confluence/Jira/Daily Report 名称或业务规则；
- 项目周审查目录不再拥有 COM 调度实现；
- 不存在旧路径 re-export、重复 scheduler、临时诊断或无关改动；
- `git diff --check` 通过。

## 明确排除

- Daily Report 业务与页面；
- 日报报告区块和布局实现；
- 新 Jira changelog/字段需求；
- Canva 或其他模板插件；
- 更改现有 Common Tool UI；
- 真实外部服务与 Windows Task Scheduler 写入验证；
- 桌面包和安装包重建。
