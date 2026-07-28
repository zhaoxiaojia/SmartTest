# Jira AI 供应商替换设计

## 目标

将 `jira_handler.py` 的 AI 模糊边界复核从内部 Kimi 服务替换为 DeepSeek 官方接口。字符初筛、模糊规则范围、并发进度、超时降级、结果合并和 Excel 输出保持不变。

## 接口

- OpenAI 兼容地址：`https://api.deepseek.com`
- 模型：`deepseek-v4-flash`
- 密钥：仅从环境变量 `DEEPSEEK_API_KEY` 读取
- 思考模式：关闭，避免格式审查消耗不必要的推理时间
- 返回格式：启用 `json_object`，沿用现有结构化裁决协议

## 清理

删除 Kimi 地址、模型名、内置密钥和 `chat_template_kwargs`。不引入新的客户端抽象，不修改其他业务逻辑。

## 验收

- `jira_handler.py` 不再包含 Kimi 配置。
- 缺少 `DEEPSEEK_API_KEY` 时保留规则初筛结果并清楚提示。
- DeepSeek 请求使用非思考模式和 JSON Output。
- 现有离线分流、并发、进度和失败降级测试继续通过。
- 不执行真实 Jira 或收费 API 请求。
