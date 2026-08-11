# Outlook 个人邮箱发送闭环 Demo 设计

## 目标

在仓库根目录新增 `demo_outlook.py`，复用本机 Outlook 已登录账号，向 `chao.li@amlogic.com` 发送一封带唯一时间戳主题的测试邮件，并在 Outlook“已发送邮件”中确认同主题邮件存在，证明发送闭环可用。

## 方案与边界

本轮采用 Windows Outlook COM 自动化。脚本通过 `pywin32` 连接传统 Outlook 桌面客户端，不保存或读取邮箱密码、应用密码、Cookie、Token 或浏览器会话。脚本必须选择 SMTP 地址等于 `chao.li@amlogic.com` 的 Outlook 账户，不能在多账户环境中静默使用默认账户。

本轮只新增根目录 `demo_outlook.py`，不修改 `support/outlook`、Daily Report 或 UI，不实现附件、HTML 模板、批量收件人、定时任务、Graph 应用注册或 SMTP 回退。尤其不得读取或复用 `chao_outlook.py` 中的明文凭据。

## 执行流程

1. 连接本机 Outlook COM，并枚举当前配置文件中的账户。
2. 精确匹配发件账户 `chao.li@amlogic.com`；未找到时立即失败并列出非敏感诊断信息。
3. 创建邮件，收件人为 `chao.li@amlogic.com`，主题包含固定前缀和 UTC 时间戳，正文说明这是 SmartTest 本地闭环测试。
4. 设置 `SendUsingAccount` 后调用 `Send()`。
5. 在限定时间内轮询该账户的“已发送邮件”，按唯一主题查找邮件；找到后输出成功结果及发送时间。
6. 超时或 COM 不可用时返回非零退出码和可操作错误，不尝试 SMTP 或浏览器自动发送。

## 安全与错误处理

- 源码和输出不得包含密码、Token 或浏览器认证数据。
- 实际发送目标固定为 Coco 已批准的 `chao.li@amlogic.com`。
- 仅在找到精确发件账户后发送，避免误用其他 Outlook 账户。
- COM 初始化、账户匹配、发送调用和已发送邮件确认分别报告明确错误。
- 新版 Outlook 不支持传统 COM 时，脚本明确提示改用经典 Outlook 或另行配置 Microsoft Graph；不把“已调用 Send”误报为闭环成功。

## 验收标准

- `python demo_outlook.py` 不需要命令行密码或源码内凭据。
- 邮件由 `chao.li@amlogic.com` 发往 `chao.li@amlogic.com`，主题具有唯一标识。
- 脚本在“已发送邮件”中找到同主题邮件后以退出码 0 结束。
- COM 不可用、账户不存在或确认超时时以非零退出码结束，并输出清晰原因。
- 静态检查与 `git diff --check` 通过，且不包含无关改动。

## 后续方案

若本机只有新版 Outlook、企业策略阻止 COM，后续单独设计 Microsoft Graph OAuth 方案；该方案需要企业 Entra 应用的 `client_id`、委托 `Mail.Send` 权限以及租户策略许可，不属于本轮自动回退范围。
