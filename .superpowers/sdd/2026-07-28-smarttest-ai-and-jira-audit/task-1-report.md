# Task 1 报告

- Files changed/deleted: `support/ai/core.py`、`support/ai/config.py`、`support/ai/client.py`、`support/ai/__init__.py`、`testing/self_tests/support/ai/test_config.py`、`testing/self_tests/support/ai/test_client.py`；新增本报告。
- Tests: `python -m pytest testing/self_tests/support/ai -q`，exit code 0，11 passed；`python -m compileall -q support/ai`，exit code 0；`git diff --check`，exit code 0。
- Acceptance / quality: 两个内置模板注册、非机密模型选择、凭据隔离/清理、两种旧 Kimi 密文迁移、环境变量回退、模板 payload 选项及无 Key 异常路径均有 durable tests。复用现有标准库 OpenAI-compatible `AIChatClient` 和 DPAPI 原子写入；未新增 SDK 或重复 HTTP/JSON 路径。
- Reuse decision: extend owner；在 `support/ai` 既有客户端和 DPAPI 存储之上扩展，不新增并行 owner。
- Relevant git status: 本任务仅改动上述 `support/ai/**` 与 `testing/self_tests/support/ai/**`；工作区另有 Coco 已存在的 `support/packaging/version.json`、两份 TS 文件及未跟踪文件，未修改、未暂存。
- Limitations or blockers: Coco 已确认首版仅保留公司内网 Kimi 与公网 DeepSeek，已移除公司内网 DeepSeek 模板及其占位值。此前对内网 `/models` 的只读探测未发出请求：本机旧 Kimi DPAPI 密文无法解密，且未输出凭据、请求头或响应。
- thread/task identity: `/root/mason_ai_foundation`（Mason）。

## Review round 1 修复

- 修复共享模板的嵌套 `request_options` 可变性；客户端构造 payload 时只使用防御性副本。
- 拒绝 `model`、`messages`、`temperature`、`max_tokens`、`response_format` 等客户端自有字段被模板选项覆盖。
- 配置测试统一清除所有兼容凭据环境变量，并新增两模板固定 URL、model、timeout、max_tokens 与请求选项断言。
- 验证：`python -m pytest testing/self_tests/support/ai -q`，18 passed；`python -m compileall -q support/ai` 与 `git diff --check` 均 exit code 0。
