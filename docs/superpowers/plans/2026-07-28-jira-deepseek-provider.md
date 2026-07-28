# Jira DeepSeek Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 仅将 Jira AI 复核供应商从 Kimi 替换为 DeepSeek 官方非思考 JSON 接口。

**Architecture:** 沿用现有 OpenAI SDK 和全部审查协调逻辑，仅修改默认配置与单次请求参数。密钥从 `DEEPSEEK_API_KEY` 读取，缺失时继续使用既有降级路径。

**Tech Stack:** Python、OpenAI SDK、DeepSeek OpenAI-compatible Chat Completions、unittest。

## Global Constraints

- 不修改字符初筛、模糊规则、并发、进度条、超时、合并和 Excel 输出。
- 不把 DeepSeek API Key 写入代码、测试、文档或日志。
- 删除全部 Kimi 专用配置和参数。
- 不运行真实 Jira 或收费 API 请求。

---

### Task 1: DeepSeek 请求契约

**Files:**
- Modify: `jira_handler.py`
- Modify: `test_jira_handler_ai.py`

**Interfaces:**
- Preserve: `_review_issue_with_ai(candidate, *, client, model)`
- Preserve: `_review_results_if_configured(...)`

- [ ] **Step 1: Write failing tests**

扩展 fake client 保存请求参数，断言：

```python
self.assertEqual(call["model"], "deepseek-v4-flash")
self.assertEqual(call["response_format"], {"type": "json_object"})
self.assertEqual(call["extra_body"], {"thinking": {"type": "disabled"}})
self.assertNotIn("chat_template_kwargs", json.dumps(call))
```

同时断言默认配置从 `DEEPSEEK_API_KEY` 读取，且不包含内部 Kimi 地址。

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m unittest test_jira_handler_ai -v
```

Expected: provider contract assertions fail against Kimi configuration.

- [ ] **Step 3: Implement minimal replacement**

在 `JIRA_CONFIG["ai_review"]` 中设置：

```python
"base_url": "https://api.deepseek.com"
"api_key": os.getenv("DEEPSEEK_API_KEY", "")
"model": "deepseek-v4-flash"
```

请求改为：

```python
response_format={"type": "json_object"},
extra_body={"thinking": {"type": "disabled"}},
```

删除 Kimi 地址、模型、密钥及 `chat_template_kwargs`，其余参数不变。

- [ ] **Step 4: Verify GREEN and cleanup**

Run:

```powershell
python -m unittest test_jira_handler_ai -v
python -m py_compile jira_handler.py test_jira_handler_ai.py
git diff --check -- test_jira_handler_ai.py
```

Expected: all scoped commands exit 0. Review changed sections and confirm no Kimi remnants or embedded DeepSeek key.
