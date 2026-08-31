# SmartTest `support` 移除与代码边界重构设计

- 日期：2026-08-27
- 状态：Coco 已确认；迁移实施与 Atlas 验收完成，等待 Coco 功能确认
- 范围：根目录 `support/` 的业务、工具、打包资源和文档归位
- 配额基线：85%；达到 88% 时报告，达到 90% 或 30 分钟内增加 5 个百分点时暂停并请 Coco 确认

## 1. 目标

1. 完整移除根目录 `support/`，且不保留转发包、兼容导入或同名替代目录。
2. 根目录的代码相关目录只保留 `client/`、`web/`、`mobile/`、`core/`。
3. `docs/`、`dist/`、`build/` 等非代码目录可以保留。
4. 将 Jira、Confluence、Redmine、报告、调度、浏览器自动化等共享业务收敛到唯一 Core owner。
5. Client 和 Web 只保留各自入口及适配职责，不重复封装共享业务。
6. Client 与 Web 可以独立启动；检查和打包同时支持单产品与 `all`。

## 2. 非目标

- 不改变现有产品业务规则、数据含义、授权范围或用户界面行为。
- 不新增 Jira、Confluence、Redmine 功能。
- 不借本次迁移重写无关模块。
- 不增加历史路径兼容层；调用方与 owner 在同一迁移阶段原子更新。
- 不重建普通调试不需要的安装包。

## 3. 当前问题

当前 `support/` 同时承担运行时业务、基础设施、开发脚本、打包资源和文档职责，边界不清晰。Client、Core、Web 均直接导入其中的运行时代码；同时 `core/jira/` 与 `support/jira_integration/` 存在分散封装，导致共享业务没有唯一 owner。

本次重构以“行为只有一个 owner”为判断标准：第三方系统访问、缓存、字段模型、过滤、报告和审查业务归 Core；产品层仅负责交互协议与呈现适配。

## 4. 最终依赖方向

```text
client ─┐
web ────┼──> core
mobile ─┘

core 不导入 client、web 或 mobile。
产品层之间不直接互相导入业务实现。
```

### 4.1 产品层职责

- `client/`：QML UI、Bridge signals/slots、Core 结果到桌面 UI 的转换、Windows 桌面生命周期、Client 专属状态。
- `web/`：FastAPI 路由、HTTP session/cookie、Web 授权入口、HTTP 序列化、前端资源。
- `mobile/`：Android UI、设备端生命周期、移动端适配和构建入口。
- `core/`：共享领域模型、第三方系统访问、缓存、查询、审查、报告及跨产品业务。

Client 和 Web 不持有 Jira、Confluence 或 Redmine 的第二套 transport、service、cache、filter、audit 或 report 实现。

## 5. 运行时代码归位

| 当前 owner | 最终 owner | 最终职责 |
|---|---|---|
| `support/jira_integration/` 与现有 `core/jira/` | `core/jira/` | Jira 认证、transport、字段、registry/cache、查询与创建服务、JQL、浏览、分析、审查和 workspace |
| `support/jira_integration/` 中的平台无关模型 | `core/issues/` | Issue、Attachment、字段值等 Jira/Redmine 共用的中立契约 |
| `core/tools/SmartHome/redmine/` 对 Jira support 模型的依赖 | `core/tools/SmartHome/redmine/` + `core/issues/` | Redmine 业务保留原 owner，只依赖中立 issue 契约 |
| `support/confluence_integration/` | `core/confluence/` | Confluence client、认证配置、页面模型与基础访问能力 |
| 已有 Project Space / 周报审查业务 | `core/tools/common/project_weekly_audit/` | 项目发现、过滤、facts、审查和报告业务 |
| `support/report/` | `core/reporting/` | 共享报告模型、生成与导出能力 |
| `support/scheduling/` | `core/scheduling/` | 共享调度能力 |
| `support/browser_automation/` | `core/browser_automation/` | 浏览器自动化共享能力 |
| `support/outlook/`、`support/personal_outlook/` | `core/email/` | 邮件与 Outlook 集成 |
| `support/windows_credentials.py` | `core/credentials/windows.py` | Windows 凭据访问 |
| `support/ai/` | `core/ai/` | 共享 AI 能力 |
| `support/mcp/` | `core/mcp/` | MCP 集成 |
| `support/account_dynamic_source.py`、`support/account_snapshot_cache.py` | `core/accounts/` | 账户动态来源与快照缓存 |
| `support/param_conversion.py` | `core/config/value_conversion.py` | 配置值转换 |

### 5.1 Jira 与通用 Issue 契约

Jira 专属对象必须留在 `core/jira/`；只有确实被多个问题平台使用、且不含 Jira 语义的模型进入 `core/issues/`。Redmine 不应为了复用中立模型而依赖 `core/jira/`。迁移时删除重复 service 或薄转发层，调用方直接依赖最终 owner。

### 5.2 Confluence 业务边界

`core/confluence/` 只负责 Confluence 平台访问及通用页面能力。Project Space、项目职责关系、筛选项、项目 facts、Stage 1/2/3 审查和报告仍由 `core/tools/common/project_weekly_audit/` 负责。Client 和 Web 只转换输入输出，不复制这些规则。

## 6. 开发、检查与打包归位

| 当前内容 | 最终位置 |
|---|---|
| `support/smarttest.py` | `core/devtools/smarttest.py` |
| `support/ci/` | `core/devtools/ci/` |
| 共享环境初始化、统一 manifest 等脚本 | `core/devtools/scripts/` |
| 共享测试目录脚本 | `core/testing/scripts/` |
| Client 启动、翻译、QRC、Python runtime、PyInstaller、Nuitka、安装器、portable、zip | `client/scripts/`、`client/packaging/` |
| Web 启动、检查、构建脚本 | `web/scripts/` |
| APK 构建、安装、签名 | `mobile/scripts/`、`mobile/packaging/` |
| 全局版本定义 | `core/release/version.json` |
| Client 打包资源 | `client/packaging/assets/` |
| `support/doc/` | `docs/client-ui/` |

`core/devtools/smarttest.py` 只负责统一参数、调用顺序和退出码汇总；具体产品脚本仍由产品目录持有，并通过 subprocess 被统一入口调用，避免复制构建逻辑。

## 7. 命令契约

### 7.1 独立开发启动

```powershell
./.venv/Scripts/python.exe client/scripts/dev.py
./.venv/Scripts/python.exe web/scripts/dev.py
```

不提供 `dev all`，避免将两个长期运行服务绑定为同一启动生命周期。

### 7.2 统一与单产品检查

```powershell
./.venv/Scripts/python.exe core/devtools/smarttest.py check all
./.venv/Scripts/python.exe core/devtools/smarttest.py check client
./.venv/Scripts/python.exe core/devtools/smarttest.py check web
./.venv/Scripts/python.exe core/devtools/smarttest.py check mobile
```

### 7.3 统一与单产品打包

```powershell
./.venv/Scripts/python.exe core/devtools/smarttest.py package all
./.venv/Scripts/python.exe core/devtools/smarttest.py package client
./.venv/Scripts/python.exe core/devtools/smarttest.py package web
./.venv/Scripts/python.exe core/devtools/smarttest.py package mobile
```

## 8. 迁移阶段与执行清单

### 阶段一：建立最终 owner 和行为基线（已完成）

- [x] 记录开始时的 `git status`，保护所有现有用户改动。
- [x] 针对 Jira、Confluence、通用 issue 契约和开发入口建立必要的行为测试。
- [x] 明确每个现有模块是迁移、合并还是删除，避免机械复制整个 `support/`。
- [x] 记录生产代码净增长；不接受由薄包装或重复抽象造成的增长。

### 阶段二：迁移共享运行时业务（已完成）

- [x] 建立 `core/issues/` 中立契约并迁移 Jira、Redmine 调用方。
- [x] 将 Jira 实现合并到 `core/jira/`，删除重复封装。
- [x] 将 Confluence 平台能力迁移到 `core/confluence/`，保持项目审查 owner 不变。
- [x] 依次迁移 reporting、scheduling、browser automation、email、credentials、AI、MCP、accounts 和配置转换。
- [x] 每个 owner 迁移时同步更新全部调用方，不保留旧导入转发。

### 阶段三：迁移工具、资源与产品脚本（已完成）

- [x] 建立 `core/devtools/` 的统一检查与打包入口。
- [x] 将 Client、Web、Mobile 专属启动、检查和打包脚本归入各产品目录。
- [x] 迁移版本文件、打包资源和 UI 文档。
- [x] 更新 README、开发文档、技能说明、CI 和打包 manifest 中的路径。

### 阶段四：删除与收口（实施完成，等待最终验收）

- [x] 删除根目录 `support/`。
- [x] 全仓检查并清除 `support.*`、`from support`、脚本路径和有效文档路径引用。
- [x] 验证根目录不存在第五个代码相关目录。
- [x] 清理迁移中的临时诊断、调试打印、废弃尝试和重复测试。
- [ ] Atlas 完成最终验收后按业务结果提交，不混入无关用户改动。

## 9. 验收标准

### 9.1 结构与依赖

- 根目录不存在 `support/`。
- 全仓不存在运行时或测试代码对 `support` 的导入。
- 不存在为旧路径提供转发的兼容包。
- Core 不导入 Client、Web 或 Mobile。
- Client 与 Web 不存在 Jira、Confluence、Redmine 共享业务的重复实现。
- Jira 和 Redmine 共用的中立模型由 `core/issues/` 唯一持有。

### 9.2 运行与工具

- Client 独立开发启动成功。
- Web 独立开发启动成功。
- `check client|web|mobile|all` 的路由及退出码正确。
- `package client|web|mobile|all` 的路由及退出码正确。
- `all` 复用单产品实现，不复制检查或打包逻辑。

### 9.3 业务回归

- Jira 登录、查询、创建、浏览、分析和审查行为保持不变。
- Confluence 项目发现、筛选、职责关系、facts 和 Stage 1/2/3 审查行为保持不变。
- Redmine 业务不再依赖 Jira 专属模型。
- 报告、调度、浏览器自动化、邮件、凭据和账户缓存行为保持不变。

### 9.4 交付质量

- 相关测试与最高可行环境验证通过。
- `git diff --check` 通过。
- 最终 diff 不含临时日志、调试代码、重复机制或无关修改。
- Coco 确认功能完整后，才执行最终清理、提交、合入主分支和推送。

## 10. 风险与回退

- 最大风险是导入路径迁移遗漏及现有重复实现行为不一致。处理方式是按 owner 分阶段迁移，每阶段运行定向测试和导入扫描。
- 不使用旧路径兼容层掩盖遗漏；遗漏必须直接修正到最终 owner。
- 每阶段保持原子提交边界，回退以 Git 提交为单位，不使用破坏性工作区命令。
- 若调查发现现有两个实现具有未经确认的业务差异，暂停该 owner 的合并，提交证据和差异给 Coco 确认，不自行选择行为。

## 11. 实施授权边界

本文件获得 Coco 书面确认后，授权开始上述范围内的拆分与合并。以下情况必须再次暂停确认：新增产品行为、改变已有业务规则、需要保留旧兼容层、发现无法安全合并的双 owner、执行破坏性操作，或范围扩展到本设计之外。
