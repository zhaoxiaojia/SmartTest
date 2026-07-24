# Jira 规范审查 Common Tool 实施计划

> **供智能体开发者使用：** 必须使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按任务实施；所有生产代码遵循 `superpowers:test-driven-development`，先看到聚焦测试因缺少行为而失败，再写最小实现。

**目标：** 在 Common Tools 中交付独立、异步、受权限控制的 Jira 规范审查、结果展示、XLSX 导出和文件定位功能。

**架构：** `support/jira_integration/audit/` 作为唯一业务所有者，复用 `JiraClient` 传输但不依赖 `jira_handler.py`；`JiraAuditBridge` 负责线程边界和前端状态；QML 只展示 Bridge 模型。权限继续由 `ToolBridge` 从 `config/personnel.json` 计算。

**技术栈：** Python 3、PySide6/QML、现有 FluentUI、pytest、标准库 ZIP/XML XLSX 生成、Windows Explorer。

## 全局约束

- 所有设计、实施和交付文档使用中文；代码标识符、路径、命令和 API 名保留原文。
- 不修改、不导入、不执行、运行时不读取根目录 `jira_handler.py`。
- 不修改任何 Redmine 文件或行为。
- 审查业务只放在现有正确目录 `support/jira_integration`。
- 复用 `AuthBridge.transientCredential()`、`JiraBasicAuth` 和 `JiraClient`；不得新增或持久化凭据。
- 只有 FAE-QA 且 `career.grade` 以 `M` 开头的用户，或拥有忽略大小写 `developer` 角色的用户可获得入口。
- `chao.li` 通过现有 developer 角色拥有权限。
- QML 不实现规则、解析 Jira 数据、生成 XLSX 或访问凭据。
- 固定前端文本同时更新 `example_zh_CN.ts` 和 `example_en_US.ts`，无 fallback、unfinished 或乱码。
- 不构建安装包；验证目标为仓库源码运行。

---

### 任务 1：独立规则模型与单问题审查器

**文件：**

- 新建：`support/jira_integration/audit/__init__.py`
- 新建：`support/jira_integration/audit/models.py`
- 新建：`support/jira_integration/audit/rules.py`
- 新建：`support/jira_integration/audit/validator.py`
- 新建：`testing/self_tests/support/test_jira_format_audit_rules.py`

**接口：**

- 产出：`active_rules() -> tuple[AuditRule, ...]`
- 产出：`normalize_issue(issue: dict[str, Any], base_url: str) -> AuditIssue`
- 产出：`audit_issue(issue: dict[str, Any], *, base_url: str, rules: Sequence[AuditRule] | None = None) -> IssueAuditResult`
- `AuditRule` 字段：`rule_id, section, field, requirement, guidance`
- `AuditViolation` 字段：`rule_id, section, field, observed, reason, guidance`
- `IssueAuditResult` 字段：`key, url, summary, reporter, passed, violations`

- [ ] **步骤 1：编写规则失败测试**

覆盖通过样本以及 Summary 结构、英文、CHIP 大写、模块、概率、Description 章节、Regression 证据、附件 10 MiB 上限和 Label 条件。断言稳定规则编号及结构化违规字段；断言模块导入不加载 `jira_handler`。

- [ ] **步骤 2：运行并确认 RED**

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_jira_format_audit_rules.py -q
```

预期：因 `support.jira_integration.audit` 尚不存在而失败。

- [ ] **步骤 3：实现最小规则模型和审查器**

将 `jira_handler.py` 中已支持的规范行为独立重写为聚焦的小函数；规则说明使用正常 UTF-8 中文。不得复制其中的配置、凭据、全局运行状态或网络/导出代码。

- [ ] **步骤 4：运行并确认 GREEN**

运行同一步骤 2；预期全部通过。

### 任务 2：输入解析、分页编排与 XLSX 导出

**文件：**

- 新建：`support/jira_integration/audit/input_resolver.py`
- 新建：`support/jira_integration/audit/service.py`
- 新建：`support/jira_integration/audit/exporter.py`
- 修改：`support/jira_integration/transport/client.py`
- 新建：`testing/self_tests/support/test_jira_format_audit_service.py`
- 新建：`testing/self_tests/support/test_jira_format_audit_exporter.py`

**接口：**

- 产出：`resolve_audit_input(text: str, *, base_url: str, client: JiraClient) -> ResolvedAuditInput`
- `ResolvedAuditInput` 字段：`source_kind, original, jql`
- 产出：`JiraAuditService.run(resolved, progress: Callable[[str, int, int], None]) -> AuditReport`
- 产出：`export_audit_xlsx(report: AuditReport, *, downloads_dir: Path | None = None, now: datetime | None = None) -> Path`
- 扩展：`JiraClient.fetch_filter(filter_id: str) -> dict[str, Any]`

- [ ] **步骤 1：编写输入、服务和导出失败测试**

覆盖空输入、原始 JQL、browse URL、filter URL、URL 中 JQL、外部主机、错误 URL、无 JQL filter、Jira 校验失败；分页进度和逐问题审查进度；空结果；唯一下载文件名、不覆盖、工作簿四类内容和超链接。

- [ ] **步骤 2：运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_jira_format_audit_service.py testing\self_tests\support\test_jira_format_audit_exporter.py -q
```

预期：因解析器、服务、导出器和 `fetch_filter` 缺失而失败。

- [ ] **步骤 3：实现输入解析和客户端窄扩展**

URL 只允许 `http/https` 且规范化 host 必须与 `base_url` 相同；browse key 使用 Jira Key 格式；filter 通过 `fetch_filter` 读取 `jql`；其他文本作为 JQL。服务通过 `search_page` 明确分页，以便每页反馈 `fetching` 进度，然后逐问题反馈 `auditing`。

- [ ] **步骤 4：实现标准库 XLSX 导出**

生成 Summary、Rules、Issues、Violations 四张表；文件写入传入目录或 Windows Downloads Known Folder，名称为 `jira_format_audit_YYYYMMDD_HHMMSS.xlsx`，冲突时增加数字后缀；先写临时文件再原子替换到最终路径。

- [ ] **步骤 5：运行并确认 GREEN**

运行同一步骤 2；预期全部通过，并再次运行任务 1 测试确认规则未回归。

### 任务 3：权限与异步 JiraAuditBridge

**文件：**

- 新建：`ui/example/bridge/JiraAuditBridge.py`
- 修改：`ui/example/bridge/ToolBridge.py`
- 修改：`ui/example/main.py`
- 修改：`testing/self_tests/ui/test_tool_page.py`
- 新建：`testing/self_tests/ui/test_jira_audit_bridge.py`

**接口：**

- 注册上下文名：`JiraAuditBridge`
- 属性：`state, statusText, inputError, progressValue, processedCount, totalCount, ruleRows, resultSummary, violationRows, exportPath, canStart, canExport`
- Slot：`startAudit(str)`, `exportReport()`, `revealExport()`
- Signal：一个统一状态变更 Signal，或按现有 Bridge 风格拆分的窄 Signal。

- [ ] **步骤 1：编写权限和 Bridge 失败测试**

权限矩阵覆盖 FAE-QA M1/M5、FAE-QA I2、其他部门 M3、developer 大小写、未知账号和 `chao.li`。Bridge 覆盖空输入不启动、临时凭据复用、状态转换、后台执行不阻塞、过期 generation 不覆盖、成功导出和不存在文件的定位错误。

- [ ] **步骤 2：运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_tool_page.py testing\self_tests\ui\test_jira_audit_bridge.py -q
```

预期：新入口与 Bridge 尚不存在导致失败。

- [ ] **步骤 3：实现 ToolBridge 权限**

新增纯函数判定并仅为授权用户向 `common.tools` 添加 `{"id": "jira_audit"}`；developer 保持全权限语义。工具标题和说明在 QObject 中使用 `self.tr(...)`。

- [ ] **步骤 4：实现异步 Bridge 并注册**

Bridge 从 `AuthBridge` 获取用户名和临时密码，创建现有 `JiraClient`；后台任务使用 generation 隔离结果；所有 UI 状态只在主线程 Signal handler 中落地。`revealExport()` 在 Windows 使用 `explorer.exe /select,<absolute path>`，不得经 shell 拼接命令。

- [ ] **步骤 5：运行并确认 GREEN**

运行同一步骤 2；预期全部通过。

### 任务 4：Common Tools 工作区、翻译和资源

**文件：**

- 新建：`ui/example/imports/example/qml/component/jiraaudit/JiraAuditWorkspace.qml`
- 修改：`ui/example/imports/example/qml/page/T_Tool.qml`
- 修改：`ui/example/imports/example/qml/global/qmldir` 或对应 component `qmldir`（按现有资源组织）
- 修改：`ui/example/imports/resource.qrc`
- 修改：`ui/example/example_zh_CN.ts`
- 修改：`ui/example/example_en_US.ts`
- 修改：`testing/self_tests/ui/test_tool_page.py`
- 修改：`testing/self_tests/ui/test_owned_ui_translations.py`
- 生成：`ui/example/imports/resource_rc.py`

**接口：**

- `T_Tool.qml` 在 `selectedTool.id === "jira_audit"` 时加载 `JiraAuditWorkspace`。
- 工作区只绑定任务 3 的属性和 Slot，不建立第二份状态模型。

- [ ] **步骤 1：编写 QML、资源和翻译失败测试**

断言入口 Loader、Bridge 绑定、空值提示由 Bridge 提供、规则/进度/结果/导出/定位控件存在；固定文本在中英文 TS 中均完成且无乱码。

- [ ] **步骤 2：运行并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_tool_page.py testing\self_tests\ui\test_owned_ui_translations.py -q
```

预期：QML 工作区和翻译项缺失导致失败。

- [ ] **步骤 3：实现 FluentUI 工作区**

沿用 `T_Tool.qml` 和相邻组件风格，使用语义主题色；输入区、规则明细、进度、摘要、违规列表和导出路径在同一可滚动工作区内；长文本可换行，规则和违规列表不阻塞页面。

- [ ] **步骤 4：更新双语翻译并重建资源**

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

预期：退出码 0，生成资源时间晚于新增/修改 QML。

- [ ] **步骤 5：运行并确认 GREEN**

运行同一步骤 2；预期全部通过。

### 任务 5：整体清理与源码验收

**文件：**

- 仅修改前四个任务中已批准的文件，用于修复验收发现的问题。

- [ ] **步骤 1：运行完整聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\support\test_jira_format_audit_rules.py testing\self_tests\support\test_jira_format_audit_service.py testing\self_tests\support\test_jira_format_audit_exporter.py testing\self_tests\ui\test_jira_audit_bridge.py testing\self_tests\ui\test_tool_page.py testing\self_tests\ui\test_owned_ui_translations.py -q
```

预期：全部通过。

- [ ] **步骤 2：运行编译和资源检查**

```powershell
.\.venv\Scripts\python.exe -m compileall support\jira_integration\audit ui\example\bridge
git diff --check
```

预期：两个命令退出码均为 0；资源文件新于 QML 变更。

- [ ] **步骤 3：验证隔离边界**

```powershell
git diff --name-only
rg -n "jira_handler|tool\\.SmartHome\\.redmine|Redmine" support\jira_integration\audit ui\example\bridge\JiraAuditBridge.py ui\example\imports\example\qml\component\jiraaudit
```

预期：修改列表不含 `jira_handler.py` 和 Redmine 文件；新增审查生产代码不引用这些模块。

- [ ] **步骤 4：有界源码启动验证**

从仓库根目录运行 `.\.venv\Scripts\python.exe main.py`，确认主窗口加载、Common Tools 对授权账号显示入口、页面可打开且无 QML/Bridge 注册错误；完成有界检查后正常关闭，不构建安装包。

- [ ] **步骤 5：清理并报告**

删除临时诊断、临时导出和废弃尝试；报告修改文件、命令及退出码、功能验收、代码质量、相关 `git status`、限制和 Mason 任务身份。
