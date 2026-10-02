# Confluence 项目周审工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 SmartTest Common Tools 中交付可手动触发的全量 A 级开发中项目 Confluence 上一自然周混合审查。

**Architecture:** `support/confluence_integration` 封装 Confluence Server API；`support/confluence_audit` 负责静态规则、最小化脱敏 AI、历史与导出；PySide6 bridge 异步运行并向 QML 暴露结果。首版不实现定时调度。

**Tech Stack:** Python 3.10、atlassian-python-api、PySide6/QML、现有 `support/ai`、pytest、openpyxl。

## Global Constraints

- 仅审查 `Support Mode = A` 且 `Current Stage = 2 IN DEVELOPMENT`。
- 周期是上一自然周周一 `00:00:00` 至周日 `23:59:59`，`Asia/Shanghai`。
- 用户不输入 Confluence URL、不选择项目；一次触发覆盖全部目标项目。
- 静态可判定规则禁止调用 AI；模糊文字或必要图片才走可替换 AI 接口。
- 公网 AI 输入必须最小化并移除人员、账号、邮箱和无关 URL 参数。
- 复用 `AuthBridge` LDAP 凭据、`support/ai`、`openpyxl` 和现有 Common Tools 模式。
- 不实现周一 09:00 调度，不保存 LDAP 密码或 AI Key，不记录完整内部正文。
- 所有生产行为按 RED-GREEN-REFACTOR 开发，保留 durable behavior tests。

---

### Task 1: Confluence 正式集成层

**Files:**
- Create: `support/confluence_integration/__init__.py`
- Create: `support/confluence_integration/models.py`
- Create: `support/confluence_integration/client.py`
- Create: `testing/self_tests/support/test_confluence_client.py`
- Modify: `support/scripts/script-init-venv.py`
- Modify: `support/packaging/pyinstaller/main.spec`

**Interfaces:**
- Produces: `ConfluenceClientConfig(base_url)`, `ConfluencePage`, `ConfluenceVersion`, `ConfluenceAttachment` 与 `ConfluenceClient.search_pages/get_page/get_page_versions/get_page_at_version/get_children/get_attachments`。
- Authentication: constructor receives LDAP `username` and `password`; third-party client remains private.

- [ ] 写失败测试：用完整的 Confluence Server 返回夹具验证 CQL 分页、page body/version/title、历史版本、子页和附件规范化；验证密码不出现在异常字符串中。
- [ ] 运行 `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_client.py -q`，确认因模块不存在而 RED。
- [ ] 最小实现模型与 client wrapper；底层复用 `atlassian.Confluence`，不得复制 HTTP transport。
- [ ] 将 `atlassian-python-api` 固定版本加入开发安装链，并在 PyInstaller spec 中声明所需 hidden imports。
- [ ] 重跑聚焦测试确认 GREEN，再执行 `git diff --check`。

### Task 2: 项目发现、周期与静态审查

**Files:**
- Create: `support/confluence_audit/__init__.py`
- Create: `support/confluence_audit/models.py`
- Create: `support/confluence_audit/period.py`
- Create: `support/confluence_audit/discovery.py`
- Create: `support/confluence_audit/rules.py`
- Create: `support/confluence_audit/html.py`
- Create: `testing/self_tests/support/test_confluence_audit_rules.py`

**Interfaces:**
- Consumes: Task 1 client models.
- Produces: `previous_business_week(now, tz) -> AuditPeriod`、`discover_projects(client) -> list[ProjectCandidate]`、`StaticAuditService.audit(project, pages, period) -> list[AuditFinding]`。
- Status enum values: `passed/risk/failed/not_applicable/unknown`。

- [ ] 写失败测试：上一自然周边界（含周一 00:00 与周末）、标签候选、A+开发中筛选、缺失关系、模板占位、QA 任务到期、链接、数字关系、报告附件周期及结项经验 N/A。
- [ ] 运行聚焦测试，确认每组因缺少行为而 RED。
- [ ] 用 HTML parser 和集中标题别名实现确定性提取；规则 ID 稳定，证据保留原页面 URL。
- [ ] 逐组实现最小规则并在每组 GREEN 后重构公共解析，禁止把业务关系放入 QML。
- [ ] 运行 Task 1+2 测试和 `git diff --check`。

### Task 3: 脱敏 AI、批次存储与导出

**Files:**
- Create: `support/confluence_audit/redaction.py`
- Create: `support/confluence_audit/ai_review.py`
- Create: `support/confluence_audit/service.py`
- Create: `support/confluence_audit/store.py`
- Create: `support/confluence_audit/exporter.py`
- Create: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Consumes: Task 1 client、Task 2 findings、`support.ai.config.create_chat_client()`。
- Produces: `redact_for_public_ai(text)`, `ConfluenceAIReviewer.review(request)`, `ConfluenceAuditService.run(period, progress) -> AuditBatch`, `AuditHistoryStore`, `export_audit_xlsx(batch, downloads_dir)`。

- [ ] 写失败测试：姓名/邮箱/账号/URL 参数脱敏、最小上下文、仅 ambiguous 规则调用 AI、AI 未配置/失败降级、内容哈希缓存、单页面失败继续、JSON 历史轮换与 XLSX 结果。
- [ ] 运行聚焦测试确认 RED；测试断言真实输出，不断言 mock 是否被调用。
- [ ] 实现严格 JSON AI 响应协议，未知或无效响应映射 `unknown`，静态失败不得被 AI 覆盖。
- [ ] 实现版本化历史 JSON 与 XLSX；敏感凭据只存在调用栈，不进入模型、存储或日志。
- [ ] 运行全部 Confluence support 测试和 `git diff --check`。

### Task 4: Bridge 与 Common Tools 前端

**Files:**
- Create: `ui/example/bridge/ConfluenceAuditBridge.py`
- Create: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify: `ui/example/main.py`
- Modify: `ui/example/bridge/ToolBridge.py`
- Modify: `ui/example/imports/example/qml/page/T_Tool.qml`
- Modify: `ui/example/imports/resource.qrc`
- Modify: `ui/example/example_zh_CN.ts`
- Modify: `ui/example/example_en_US.ts`
- Create: `testing/self_tests/ui/test_confluence_audit_bridge.py`
- Modify: `testing/self_tests/ui/test_tool_page.py`
- Modify: `testing/self_tests/ui/test_owned_ui_translations.py`
- Modify: `testing/self_tests/ui/test_frontend_persistence_contract.py`

**Interfaces:**
- Consumes: `AuthBridge.transientCredential()` 与 Task 3 service/store/exporter。
- Produces: QML context `ConfluenceAuditBridge`，`viewState` 包含 state、period、progress、summary、projects、selectedProject、findings、history、AI 状态、exportPath 与 canStart/canExport。

- [ ] 写 bridge 失败测试：无登录拒绝、全量启动、后台进度、旧 generation 丢弃、登录变化、历史选择、导出和错误降级。
- [ ] 写 QML 行为测试：Common Tools 可见工具、无 URL/勾选输入、启动按钮、汇总、项目选择、证据链接、历史批次和运行态禁用。
- [ ] 运行聚焦 UI 测试确认 RED。
- [ ] 实现 bridge worker 与页面；QML 仅渲染 bridge 模型，固定文字全部 `qsTr/self.tr` 且双语同步。
- [ ] 重建 `resource_rc.py`，运行 UI 聚焦测试与翻译 owner 测试。

### Task 5: 真实环境只读自测与交付清理

**Files:**
- Create: `support/confluence_integration/README.md`
- Modify only if evidence requires: files from Tasks 1-4.

**Interfaces:**
- Uses current environment and LDAP sign-in; performs no Confluence writes.

- [ ] 使用真实 Confluence 只读执行项目发现，验证能定位示例 Muffin314 Status Report、项目主页和六类目标页。
- [ ] 使用固定时间或审查期运行一轮受控全量审查，记录候选数、目标项目数、页面读取数和静态/AI 降级状态，不输出内部正文。
- [ ] 运行 `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_client.py testing/self_tests/support/test_confluence_audit_rules.py testing/self_tests/support/test_confluence_audit_service.py testing/self_tests/ui/test_confluence_audit_bridge.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q`。
- [ ] 从仓库根目录执行源码启动边界检查；确认资源文件新于 QML，未构建桌面安装包。
- [ ] 检查 `git status --short`、scoped diff、`git diff --stat`、`git diff --check`；移除调试输出、探索性测试、完整正文日志和无关变更。
