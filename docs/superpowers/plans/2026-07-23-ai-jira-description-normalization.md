# AI 规范化 Jira Description 实施计划

> Status: Deferred. `support/ai` remains a reusable transport/config layer, but the current Redmine-to-Jira clone flow uses a deterministic Notes-only description template and has no AI business wiring.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用公司 OpenAI-compatible LLM 解析第三方 Issue，并生成格式固定、可人工审查的 Jira Description。

**Architecture:** `support/ai` 提供无业务含义的安全 LLM 客户端；`support/jira_integration` 提供第三方 Bug 结构化解析和 Jira 模板渲染；Redmine Clone 仅提交源数据并消费最终文本。AI 失败使用确定性模板降级，不阻塞 Clone。

**Tech Stack:** Python 3、urllib、Windows DPAPI、OpenAI-compatible `chat/completions`、dataclass、pytest、现有 PySide6 Bridge 异步 worker。

## Global Constraints

- 不恢复历史 AI 页面、会话存储、MCP 聊天业务或源码内置 API Key。
- API Key 只来自 `SMARTTEST_AI_API_KEY` 或 `%LOCALAPPDATA%\Amlogic\SmartTest\AI\secret_store.json` 的 DPAPI 密文。
- AI 只分类原文，不能翻译、补充或猜测事实。
- 正文允许中文或英文；全英文规则暂不启用。
- 固定模板严格使用 `jira规范.md` 中的标题、顺序、`HW info`、`SW info` 和 `Comparision` 拼写。
- 任何 AI 故障都不得阻塞 Clone，完整源信息必须进入降级模板。
- QML 不增加 AI 或 Jira 格式业务。

---

### Task 1: 通用 AI 客户端与安全配置

**Files:**
- Create: `support/ai/core.py`
- Create: `support/ai/config.py`
- Create: `support/ai/client.py`
- Create: `support/ai/__init__.py`
- Create: `testing/self_tests/support/ai/test_client.py`
- Create: `testing/self_tests/support/ai/test_config.py`

**Interfaces:**
- Produces: `AIClientConfig`、`AIChatMessage`、`AIChatResponse`、`AIError`。
- Produces: `AIChatClient.chat_completion(messages, *, response_format=None, temperature=0) -> AIChatResponse`。
- Produces: `AIKeyResolver.resolve() -> str`，仅支持环境变量和 DPAPI store。

- [ ] 写失败测试：验证 OpenAI-compatible payload、结构化 response format、超时/HTTP/JSON 错误归一化，且异常不包含 Authorization 或完整响应。
- [ ] 运行 `python -m pytest testing/self_tests/support/ai -q`，确认因模块不存在而失败。
- [ ] 从历史提交 `1b4cde6` 只迁移 transport、model、DPAPI 的必要思想，删除默认密钥 factory、`print` trace、UI/jsonTool 依赖和会话能力。
- [ ] 实现原子 JSON 存储与 Windows DPAPI；非 Windows 或无 Key 明确抛出 `AIConfigurationError`。
- [ ] 再运行该目录测试，预期全部通过。

### Task 2: Jira Description 结构解析与确定性模板

**Files:**
- Create: `support/jira_integration/core/description.py`
- Create: `support/jira_integration/services/description_service.py`
- Modify: `support/jira_integration/README.md`
- Create: `testing/self_tests/support/test_jira_description_service.py`

**Interfaces:**
- Produces: `ThirdPartyDescriptionSource(system, issue_id, title, description, attributes, comments, source_url)`。
- Produces: `JiraDescriptionParts(steps_to_reproduce, actual_results, expected_results, reproducibility_rate, comparison, hw_info, sw_info, unclassified_notes)`。
- Deferred interface: a future AI parser may consume `ThirdPartyDescriptionSource`; no parser service is present in the current clone flow.

- [ ] 写失败测试：固定标题顺序、步骤编号、中文内容保留、来源写入 Notes、`Comparision` 原拼写、空字段仍保留标题。
- [ ] 写失败测试：合法 fenced/unfenced JSON 可解析；缺字段补空；错误类型、超长字段和非 JSON 触发降级。
- [ ] 写失败测试：无 Key、超时和请求错误都保留完整 description/comments，且 `prepare()` 不抛出。
- [ ] 实现固定 system prompt 与 JSON schema；注释记录“全英文校验暂不启用”，不得把模板控制交给模型。
- [ ] 实现纯函数 `render_description(parts, source)` 和 `render_fallback(source)`。
- [ ] 运行 `python -m pytest testing/self_tests/support/test_jira_description_service.py -q`，预期全部通过。

### Task 3: Redmine Clone 接入通用 Jira Description

**Files:**
- Modify: `tool/SmartHome/redmine/clone_draft.py`
- Modify: `ui/example/bridge/RedmineBridge.py`
- Modify: `testing/self_tests/tool/smarthome/redmine/test_clone_draft.py`
- Modify: `testing/self_tests/ui/test_redmine_bridge.py`

**Interfaces:**
- Current behavior: Redmine consumes only the deterministic Notes-only Jira renderer; future AI parsing remains deferred.
- Changes: `RedmineCloneDraftService.build(..., prepared_description: str)` 只接收已准备文本，不调用 AI。

- [ ] 写失败测试：Redmine Draft 使用传入的规范化 Description，不再调用 `_source_description`。
- [ ] 写失败测试：Bridge 把 detail 的 description、attributes、comments 和 URL 转成 `ThirdPartyDescriptionSource`，AI 成功与失败都完成草稿准备。
- [ ] 在现有 `prepareCloneDrafts()` 异步 operation 中创建/注入 Jira Description service；每条 Issue 在 build draft 前完成 prepare。
- [ ] 删除 Redmine 自有 Description 拼接函数和重复来源文本；Attachment links 逻辑保持不变。
- [ ] 运行 `python -m pytest testing/self_tests/tool/smarthome/redmine/test_clone_draft.py testing/self_tests/ui/test_redmine_bridge.py -q`。

### Task 4: 集成清理与验证

**Files:**
- Review: `support/ai/**`
- Review: `support/jira_integration/**`
- Review: `tool/SmartHome/redmine/clone_draft.py`
- Review: `ui/example/bridge/RedmineBridge.py`

**Interfaces:**
- 验证一个 AI transport owner、一个 Jira Description owner、一个 Redmine orchestration owner。

- [ ] 运行 `python -m pytest testing/self_tests/support/ai testing/self_tests/support/test_jira_description_service.py testing/self_tests/support/test_jira_create_schema_service.py testing/self_tests/tool/smarthome/redmine/test_clone_draft.py testing/self_tests/ui/test_redmine_bridge.py testing/self_tests/ui/test_redmine_clone_create_ui.py -q`。
- [ ] 运行 `python -m compileall -q support/ai support/jira_integration tool/SmartHome/redmine ui/example/bridge`。
- [ ] 运行 `rg -n \"print\\(|console\\.log|DEFAULT.*KEY|decode_default|Authorization.*log|TODO|FIXME\" support/ai support/jira_integration tool/SmartHome/redmine ui/example/bridge`，新增范围不得包含密钥、临时打印或占位实现。
- [ ] 运行 `git diff --check` 并检查 scoped diff；不打包、不提交，等待 Coco 内网功能验收。
