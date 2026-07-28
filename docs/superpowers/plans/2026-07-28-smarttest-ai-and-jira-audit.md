# SmartTest 统一 AI 模型与 Jira 审查实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 SmartTest 的 AI 模型、LLM 调用和加密凭据入口，并让 Common Tools 的 Jira 审查完成字符初审、AI 模糊边界复核、确认和导出。

**Architecture:** `support/ai` 统一拥有内置模型模板、DPAPI 凭据和 OpenAI-compatible LLM；`support/jira_integration/audit` 只拥有 Jira 规则、候选分流和结果合并。Settings 通过专用桥接保存秘密，Jira Bridge 只编排后台任务和前端状态。

**Tech Stack:** Python 3.10、PySide6/QML、Windows DPAPI、Python 标准库 HTTP、pytest、openpyxl。

## Global Constraints

- 根目录 `jira_handler.py` 保持独立，不修改、不导入、不依赖。
- 首版内置公司内网 Kimi、公司内网 DeepSeek、公网 DeepSeek 三个模板，地址和模型 ID 不允许用户修改。
- API Key 不得进入 QSettings、QML 状态、日志、异常、报告、QRC、翻译文件或安装包明文。
- 复用现有 OpenAI-compatible 客户端和 `openpyxl`，不得复制 HTTP、JSON 或 XLSX/XML 实现。
- AI 只复核明确声明的模糊候选；失败时保留字符初审结果。
- 不修改 Redmine 和其他业务逻辑。
- 只保留长期保护业务契约与高风险边界的测试。

---

### Task 1: 统一 AI 模型、凭据与 LLM 接口

**Files:**
- Modify: `support/ai/core.py`
- Modify: `support/ai/config.py`
- Modify: `support/ai/client.py`
- Modify: `support/ai/__init__.py`
- Modify: `testing/self_tests/support/ai/test_config.py`
- Modify: `testing/self_tests/support/ai/test_client.py`

**Interfaces:**
- Produces: `AIModelTemplate`、`available_models()`、`model_by_id(model_id)`、`selected_model_id()`、`select_model(model_id)`。
- Produces: `AIKeyResolver.resolve(credential_id)`、`store(credential_id, key)`、`clear(credential_id)`、`is_configured(credential_id)`。
- Produces: `create_chat_client(model_id=None)`，返回现有 `AIChatClient`。
- Consumes: 当前旧版 DPAPI 单 Key 文件，并将其迁移到公司内网 Kimi 凭据。

- [ ] **Step 1: 编写模型注册、凭据隔离和旧 Key 迁移的失败测试**

覆盖三个稳定模板 ID、无效模板拒绝、两个凭据互不覆盖、清除单个凭据、旧 `api_key_dpapi` 只迁移到公司内网 Kimi。

- [ ] **Step 2: 运行 AI 配置测试并确认因新接口不存在而失败**

Run: `python -m pytest testing/self_tests/support/ai/test_config.py -q`

Expected: FAIL，失败点为模型注册或按凭据存取接口尚未实现。

- [ ] **Step 3: 最小化改造模型和凭据实现**

使用不可变数据类声明模板；将模板请求差异保存在模板配置中。保留现有 DPAPI 原语和原子替换写入，密文文件改为按凭据 ID 存储。迁移过程只在内存中解密旧值，不创建明文文件。

- [ ] **Step 4: 编写统一客户端模板解析和请求选项测试**

验证客户端从模板获取 `base_url`、`model_id`、凭据及 JSON/思考模式选项；验证 HTTP 与响应异常不包含 Key。

- [ ] **Step 5: 复用现有客户端完成统一 LLM 入口**

客户端继续负责一次 OpenAI-compatible `/chat/completions` 请求；模型差异只合并到请求 payload。删除旧单模型常量和重复加载路径，`__init__.py` 只导出稳定公共接口。

- [ ] **Step 6: 运行 AI 测试**

Run: `python -m pytest testing/self_tests/support/ai -q`

Expected: PASS。

### Task 2: Settings 安全配置入口

**Files:**
- Create: `ui/example/bridge/AISettingsBridge.py`
- Modify: `ui/example/main.py`
- Modify: `ui/example/imports/example/qml/page/T_Settings.qml`
- Modify: `ui/example/example_zh_CN.ts`
- Modify: `ui/example/example_en_US.ts`
- Test: `testing/self_tests/ui/test_ai_settings_bridge.py`
- Modify: `testing/self_tests/ui/test_owned_ui_translations.py`

**Interfaces:**
- Consumes: Task 1 的模型查询、选择和凭据 API。
- Produces: `AISettingsBridge.state()`，仅返回模型元数据、当前模型 ID 和 `configured` 布尔值。
- Produces: `AISettingsBridge.selectModel(model_id)`、`saveApiKey(model_id, key)`、`clearApiKey(model_id)`。

- [ ] **Step 1: 编写 Bridge 不回传 Key 的失败测试**

验证状态只含模板 ID、名称、当前选择和配置布尔值；保存后原 Key 不出现在返回对象、异常文本或日志参数中。

- [ ] **Step 2: 运行 Bridge 测试并确认失败**

Run: `python -m pytest testing/self_tests/ui/test_ai_settings_bridge.py -q`

Expected: FAIL，原因是 Bridge 尚不存在。

- [ ] **Step 3: 实现最小 Settings Bridge 并注册到 QML**

Bridge 直接调用 `support/ai`；拒绝空 Key 和未知模板；所有面向用户的错误为不含秘密的稳定文本。不得通过 `SettingsHelper.saveString` 保存 API Key。

- [ ] **Step 4: 在 Settings 增加 AI 模型配置区域**

加入模型下拉框、密码输入、已配置状态、保存和清除按钮。切换模型刷新状态但不回填 Key；保存成功立即清空输入框。

- [ ] **Step 5: 更新双语文本并运行 UI 相关测试**

Run: `python -m pytest testing/self_tests/ui/test_ai_settings_bridge.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: PASS。

### Task 3: Jira 字符初审与 AI 模糊复核

**Files:**
- Modify: `support/jira_integration/audit/models.py`
- Modify: `support/jira_integration/audit/rules.py`
- Modify: `support/jira_integration/audit/service.py`
- Modify: `support/jira_integration/audit/__init__.py`
- Modify: `testing/self_tests/support/test_jira_format_audit_rules.py`
- Modify: `testing/self_tests/support/test_jira_format_audit_service.py`

**Interfaces:**
- Consumes: Task 1 的 `create_chat_client()` 和统一 `chat_completion()`。
- Produces: 明确违规与 AI 候选的规则结果。
- Produces: `JiraAuditService.run(..., progress=...)` 的稳定阶段事件和包含 AI 复核状态的 `AuditReport`。

- [ ] **Step 1: 从当前根目录规则建立必要的行为测试**

只提取长期行为：允许 AI 复核的规则 ID、候选条件、同一 Jira 候选合并一次请求、AI `PASS/FAIL` 合并、无配置/超时/无效 JSON 降级、无候选不调用 AI。

- [ ] **Step 2: 运行 Jira 规则和服务测试并确认新增行为失败**

Run: `python -m pytest testing/self_tests/support/test_jira_format_audit_rules.py testing/self_tests/support/test_jira_format_audit_service.py -q`

Expected: FAIL，失败点为候选/AI 复核尚未接入。

- [ ] **Step 3: 对齐确定性规则并添加候选分流**

复用当前 SmartTest 规则模型，按根目录最新业务行为补齐字符匹配。规则负责产出明确违规和有限候选，不包含 LLM 客户端、线程或 UI 状态。

- [ ] **Step 4: 实现结构化 AI 裁决与结果合并**

每个 Jira 一次请求，要求完整 JSON 裁决；严格校验 Issue Key、规则集合、唯一性和 `PASS/FAIL`。失败时保留原违规并标记未复核，不暴露底层秘密或响应原文。

- [ ] **Step 5: 调整服务阶段并运行测试**

阶段顺序固定为 resolving、fetching、rule_auditing、ai_reviewing、finalizing、awaiting_confirmation。运行 Task 3 两个测试文件，Expected: PASS。

### Task 4: Common Tools Jira 审查交互、确认和导出

**Files:**
- Modify: `ui/example/bridge/JiraAuditBridge.py`
- Modify: `ui/example/imports/example/qml/component/jiraaudit/JiraAuditWorkspace.qml`
- Modify: `ui/example/example_zh_CN.ts`
- Modify: `ui/example/example_en_US.ts`
- Modify: `testing/self_tests/ui/test_jira_audit_bridge.py`
- Modify: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- Consumes: Task 3 的报告与进度阶段。
- Produces: `startAudit(input)`、`confirmAudit()`、`exportReport()` 和只读视图状态。

- [ ] **Step 1: 编写完整状态流失败测试**

验证空输入和非法 URL/JQL 提示、运行阶段映射、AI 未配置降级提示、完成后必须确认、确认后允许导出、重新审查清除旧确认与导出路径。

- [ ] **Step 2: 运行 Bridge 测试并确认失败**

Run: `python -m pytest testing/self_tests/ui/test_jira_audit_bridge.py testing/self_tests/ui/test_tool_page.py -q`

Expected: FAIL，失败点为新阶段或确认门禁尚未实现。

- [ ] **Step 3: 收敛 Bridge 状态机**

Bridge 只编排现有 Jira Client、审查服务、后台线程和下载目录；不承载规则或 AI 配置。并发代次保护继续防止旧任务覆盖新状态。

- [ ] **Step 4: 调整 QML 审查流程**

保持一个“开始审查”按钮；展示规则明细、分阶段进度、最终问题列表、确认按钮、确认后导出按钮和定位文件按钮。输入为空或格式错误时不启动后台任务。

- [ ] **Step 5: 更新双语文本并运行 UI 测试**

Run: `python -m pytest testing/self_tests/ui/test_jira_audit_bridge.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: PASS。

### Task 5: 依赖、清理和交付验证

**Files:**
- Modify only if required: `support/scripts/script-init-venv.py`
- Modify only if required: `support/packaging/**`
- Review: all files changed by Tasks 1-4

**Interfaces:**
- Consumes: Tasks 1-4 的完整功能。
- Produces: 可从源码和桌面打包环境运行的最终交付。

- [ ] **Step 1: 检查依赖与打包资源**

确认只使用项目已有依赖；若统一客户端继续使用标准库，不新增 OpenAI SDK。确认新增 Bridge/QML Python 文件会被现有打包与 QRC 机制收集。

- [ ] **Step 2: 删除开发残留**

删除本任务产生的临时脚本、缓存、重复测试、源码形状测试、调试打印和废弃入口；不得删除用户已有的未跟踪文件或现有工作区改动。

- [ ] **Step 3: 运行 scoped tests**

Run: `python -m pytest testing/self_tests/support/ai testing/self_tests/support/test_jira_format_audit_rules.py testing/self_tests/support/test_jira_format_audit_service.py testing/self_tests/ui/test_ai_settings_bridge.py testing/self_tests/ui/test_jira_audit_bridge.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: PASS。

- [ ] **Step 4: 运行静态和启动验证**

Run: `python -m compileall -q support/ai support/jira_integration/audit ui/example/bridge`

Run: `python -m pip check`

Run: 使用 `QT_QPA_PLATFORM=offscreen` 启动 SmartTest 并观察 Settings 与 Common Tools QML 无加载错误。

Expected: 全部 exit code 0；离屏进程稳定运行至验证超时。

- [ ] **Step 5: 复核最终差异**

Run: `git diff --stat`

Run: `git diff --check`

核对根目录 `jira_handler.py`、Redmine、用户既有未跟踪文件和无关改动均未被修改；净生产代码增长与复用决策符合设计。

