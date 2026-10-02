# AI 规范化 Jira Description 设计

> Status: Deferred. The current Redmine-to-Jira clone flow does not call AI; it preserves only the original Redmine description in the deterministic Jira `[Notes]` section.

## 目标

所有第三方 Clone 到 Jira 的问题都先由通用 AI 服务把原始描述解析为结构化字段，再由 Jira 集成层生成符合 `jira规范.md` 的固定 Description。具体内容允许中文或英文；固定标题、顺序和 `HW info`、`SW info` 必须严格使用规范文本。

## 职责边界

- `support/ai`：拥有 OpenAI-compatible transport、API Key 安全解析、结构化响应解析与错误类型；不依赖 Jira、Redmine、Qt。
- `support/jira_integration`：拥有 Jira Description 的字段模型、AI 提示词、结构校验、固定模板渲染与非阻塞降级。
- 第三方集成（当前为 Redmine）：只提供原始标题、描述、属性、评论和来源身份；不维护 Jira 模板或 AI 提示词。
- QML：只展示 Jira 草稿的最终可编辑 Description；不调用 AI、不解析模板。

## AI 输入与输出

输入包含第三方系统名、Issue ID、标题、原始描述、已抓取属性、评论和来源 URL。输出只能是以下结构：

- `steps_to_reproduce: list[str]`
- `actual_results: str`
- `expected_results: str`
- `reproducibility_rate: str`
- `comparison: str`
- `hw_info: str`
- `sw_info: str`
- `unclassified_notes: str`

AI 不翻译、不补充事实、不猜测缺失值。无法可靠分类的原文放入 `unclassified_notes`。服务端对 JSON、字段类型、条目数量和文本长度进行确定性校验。

## 固定 Jira 模板

Jira 集成层始终按以下顺序渲染：

```text
[Steps to reproduce]:

[Actual results]:

[Expected results]:

[Reproducibility rate]:

[Comparision]:

[Notes]:
HW info:
SW info:
```

保留规范原文中的 `Comparision`。来源系统、来源 ID、来源 URL 和未分类内容写入 `[Notes]`。当前不强制正文为英文；该要求以未启用策略注释记录。

## 失败与安全

- 无 API Key、请求超时、HTTP 错误、非 JSON、字段不合法或模型拒绝时，不阻止 Clone。
- 降级结果仍使用固定模板，并把完整原始描述及评论放入 `[Notes]`，保证信息不丢失。
- API Key 优先读取 `SMARTTEST_AI_API_KEY`，其次读取 Windows DPAPI 加密的本地存储；源码、配置和安装包不得内置默认密钥。
- 默认公司服务为 `https://llm.amlogic.com/8d1b5b4c`，模型为 `Amlogic_Local/Kimi-K2.7-Code`；服务调整时可通过 `SMARTTEST_AI_BASE_URL` 和 `SMARTTEST_AI_MODEL` 覆盖。
- 默认请求超时为 120 秒、输出上限为 2048 tokens；可通过 `SMARTTEST_AI_TIMEOUT` 和 `SMARTTEST_AI_MAX_TOKENS` 覆盖。
- 日志只能记录阶段、耗时和错误类型，不记录 API Key、完整提示词、第三方描述或模型原始响应。

## Clone 流程

Redmine 批量准备草稿时，在已有异步 operation 内逐条调用 Description 规范化服务。AI 结果或降级模板作为 Description 初始值进入现有 Jira Create QML。用户可继续修改；只有点击批量创建后才提交 Jira。

## 验收

- AI 成功时，混合中英文原文被正确放入固定段落。
- 固定标题和顺序不能被模型改变。
- 未识别内容和来源信息不丢失。
- 无 Key、超时、错误 JSON 均生成合规降级模板并继续准备草稿。
- API Key 不进入仓库、日志或 Jira 内容。
- Redmine 不再拥有 Description 模板拼接逻辑。
