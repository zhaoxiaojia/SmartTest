# Outlook 邮件公共封装设计

## 目标

将根目录 `demo_outlook.py` 中 SMTP 发送、MIME 组装、Markdown/HTML 正文、内嵌图片和附件处理提取到 `support/outlook/`，形成可供其他 SmartTest 业务复用的邮件入口。根目录 demo 仅保留示例数据、报告内容和调用示例。

本阶段不接入 Canva 或其他模板插件，只提供稳定的模板选择边界，待基础封装验证后单独设计第三方模板能力。

## 公共接口

`support.outlook.send_email` 是业务侧默认入口：

```python
send_email(
    *,
    subject: str,
    body: str,
    to: Sequence[str],
    cc: Sequence[str] = (),
    bcc: Sequence[str] = (),
    sender_name: str = "SmartTest 自动化平台",
    body_format: Literal["markdown", "html"] = "markdown",
    attachments: Sequence[Path] = (),
    template: str | None = "technology",
) -> None
```

固定发件邮箱、SMTP 主机和端口由 `support/outlook/` 内部配置持有，业务调用方不能通过公共接口覆盖。`sender_name` 是邮件客户端展示的发件人名称，用于表达业务角色，不改变真实邮箱地址、认证身份或权限。

除直接发送入口外，内部邮件构建能力保持可独立调用和测试，使 demo 可以生成预览，测试也无需连接真实 SMTP 服务器。

## 正文与视觉呈现

- `body_format="markdown"` 时，使用成熟 Markdown 库将正文转换为 HTML，不自行实现 Markdown 解析器。
- `body_format="html"` 时，调用方可直接提供完整或片段 HTML。
- `template="technology"` 使用适合 Outlook 的表格布局和内联样式，提供卡片、强调色、指标区块等科技感视觉基础。
- `template=None` 仅包裹必要的 HTML 邮件骨架，不施加主题样式。
- 模板渲染与邮件发送分离。未来 Canva 或其他设计来源通过新增明确的渲染适配器接入，不改变 SMTP 投递和 MIME 组装职责。

## 图片和附件

Markdown 图片语法中的本地路径以及 HTML `<img>` 的本地路径均转换为 CID 内嵌 MIME 资源，正文引用改写为对应的 `cid:` 地址。图片不是普通附件，收件人打开邮件时直接显示。

网络图片本阶段不自动下载，避免邮件构建过程发生隐式外部网络访问。已有 `cid:` 或数据 URI 不重复处理。缺失或不可读取的本地图片在连接 SMTP 前报告明确错误。

`attachments` 接受本地文件路径，按文件类型生成 MIME 附件并保留文件名。附件与正文内嵌资源严格区分。

## 收件人与投递

- `to` 和 `cc` 写入邮件头并加入 SMTP 投递名单。
- `bcc` 只加入 SMTP 投递名单，不写入邮件头。
- 至少需要一个实际收件人。
- 在 SMTP 连接前验证空地址、明显无效的邮箱地址及不存在的资源文件。
- SMTP 投递失败保留底层原因，并包装为统一的 Outlook 发送异常。

真实 IT SMTP 服务器不在当前开发网段，因此本阶段不进行真实投递验证，也不将其作为验收条件。

## 代码边界

- `support/outlook/__init__.py`：只导出稳定公共接口和公共异常。
- 邮件模型/参数校验：规范化收件人、资源路径和正文格式。
- 正文渲染：Markdown 转 HTML、主题模板和本地图片引用识别。
- MIME 构建：生成纯文本回退、HTML alternative、CID 图片和附件。
- SMTP 发送：持有固定基础设施配置并完成投递。
- `demo_outlook.py`：保留示例报告业务，改用公共封装，不再拥有 SMTP/MIME 机制。

实现时依据仓库现有结构选择最少文件数；上述职责边界不要求为每项机械拆分独立文件。

## 错误处理

公共异常分为配置/输入错误与发送错误。输入、文件和渲染错误必须在 SMTP 连接前暴露；发送错误包含原始异常链，便于调用方记录和诊断。不得静默跳过收件人、图片或附件。

## 测试与验收

测试全部离线执行，覆盖：

- 默认和自定义 `sender_name` 与固定发件邮箱组合正确；
- `to`、`cc` 邮件头正确，`bcc` 不出现在邮件头但进入 SMTP 投递名单；
- Markdown 被渲染为 HTML，并保留纯文本回退；
- Markdown 与 HTML 中的本地图片形成 CID 内嵌资源；
- 附件具有正确文件名和 MIME 结构；
- 空收件人、无效地址、缺失图片和缺失附件在发送前失败；
- 模拟 SMTP 能收到固定发件地址和完整的 To/Cc/Bcc 投递名单；
- demo 的预览路径不连接 SMTP。

功能验收不连接真实 IT 邮件服务器。代码质量验收要求复用成熟 Markdown 依赖、无重复 SMTP/MIME 所有者、无临时诊断代码、无无关改动，并通过 `git diff --check`。

## 明确排除

- Canva API、Canva 登录或模板同步；
- 浏览器画布编辑器；
- 远程图片下载和缓存；
- 邮件队列、重试调度、投递回执；
- 修改 IT 分配的发件邮箱或 SMTP 基础设施配置。
