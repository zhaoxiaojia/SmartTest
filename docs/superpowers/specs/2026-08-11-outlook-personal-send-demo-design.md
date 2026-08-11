# 个人 Outlook 与 Daily Report 长图发送设计

## 目标

将已验证的新版 Outlook 个人邮箱发送机制封装到 `support/personal_outlook/`，并让 Daily Report 通过该机制发送完整日报长图。邮件继续使用计划中的收件人、抄送人和主题，不再发送 Excel、HTML 或其他附件。

## 范围与边界

本轮新增个人邮箱发送所有者 `support/personal_outlook/`，不改变现有 `support/outlook/` 固定内网 SMTP 的职责或接口。Daily Report 仍负责 Jira 查询、快照、分析和报告内容组装；现有报告渲染所有者继续生成完整 HTML，随后通过已有受管浏览器渲染依赖生成单张 PNG 长图。个人邮箱模块只负责 Outlook 版本判断、邮件草稿、正文图片粘贴、发送及桌面状态恢复。

本轮不卸载或修改 Outlook/Microsoft 365，不使用经典 Outlook COM，不申请 Microsoft Graph 权限，不读取密码、Token、Cookie 或浏览器会话，不发送附件，不新增第二套 Daily Report 布局，不修改 UI 导航和交互概念。

## 组件与所有权

### `support/personal_outlook/`

公开一个面向业务的个人邮箱发送入口，输入主题、正文长图路径、收件人和抄送人。模块内部负责：

- 检测 Windows AppX 包 `Microsoft.OutlookForWindows`、运行中的 `olk.exe` 窗口和经典 Outlook COM 注册状态；
- 多版本并存时只选择新版 Outlook；只有经典版或新版不可用时给出可操作错误；
- 通过 `mailto:` 创建带收件人、抄送人和主题的新版 Outlook 草稿；
- 只选择进程为 `olk.exe` 且标题包含本次唯一标记的草稿窗口；
- 保存当前前台窗口和剪贴板内容，将 PNG 以图片格式写入剪贴板并粘贴到正文；
- 执行发送快捷键，等待草稿窗口关闭；
- 在成功或失败路径都尽力恢复原剪贴板和前台窗口；
- 把版本、窗口、图片、剪贴板和发送失败包装为明确的个人邮箱异常。

个人邮箱模块不得导入 Daily Report 或包含项目特例。根目录 `demo_outlook.py` 改为调用该公共入口，仅保留固定测试数据和命令行示例。

### Daily Report

Daily Report 继续生成与预览一致的完整 HTML。发送前使用仓库现有受管浏览器/报告渲染依赖将整个 HTML 页面截图为单张 PNG 长图，覆盖标题、指标、表格、趋势图和说明；不得只复用趋势图，也不得新增另一套图片布局。

Daily Report 的发送调用改为个人邮箱公共入口：

- `to`、`cc` 和主题沿用计划配置；
- 正文只包含完整日报长图及必要的简短纯文本说明；
- 不生成或传递发送附件；
- `bcc` 若现有计划支持，则继续传入并保持不可见投递语义；若新版 Outlook UI 无法可靠表达 Bcc，必须在发送前明确失败，不得静默丢弃；
- 预览路径不启动 Outlook、不修改剪贴板、不抢占前台窗口。

## 执行流程

1. Daily Report 完成 Jira 查询、分析和完整 HTML 生成。
2. 长图渲染器打开本地 HTML，等待字体、图片和布局稳定后生成单张完整 PNG。
3. Daily Report 将主题、长图路径、`to`、`cc` 和可选 `bcc` 交给 `support.personal_outlook`。
4. 个人邮箱模块检测并选择新版 Outlook，创建唯一草稿窗口。
5. 模块保存原前台窗口和剪贴板，将长图粘贴到正文并发送。
6. 草稿窗口关闭后恢复剪贴板和原前台窗口；失败路径同样执行恢复。
7. Daily Report 按现有结果记录机制报告成功或个人邮箱异常。

## 静默与桌面干扰

新版 Outlook 没有可供本地 Python 调用的 COM/API，本方案无法真正后台静默。发送阶段会短暂激活 Outlook 草稿窗口，预计约 3–10 秒。实现必须把抢占范围限制在创建草稿、粘贴和发送阶段，并在结束后恢复原前台窗口与剪贴板；不得在 Jira 查询、HTML 生成或长图渲染阶段抢占焦点。

## 安全与失败处理

- 不保存或输出邮箱密码、应用密码、Token、Cookie 或浏览器认证数据。
- 只有唯一草稿窗口同时满足 `olk.exe` 归属和本次主题标记时才发送快捷键。
- 图片不存在、无法读取、剪贴板写入失败、草稿未出现、发送后未关闭或桌面状态恢复失败时报告明确错误。
- 不回退到经典 Outlook、SMTP、Graph 或其他邮件客户端。
- 不把“按下发送快捷键”单独视为完整成功；草稿窗口必须关闭。真实环境验收另在 Outlook Web 的“已发送邮件”中核对主题。

## 测试与验收

离线测试使用 fake 窗口、fake 剪贴板、fake 长图渲染器和 fake 个人邮箱发送器，至少覆盖：

- 多版本并存时选择新版，且不连接或启动经典 Outlook；
- 只有经典版、新版未安装、新版窗口不可用和草稿匹配歧义的错误；
- 收件人、抄送人、主题和完整长图正确传递；
- Daily Report 不再传递附件；
- 预览路径不调用 Outlook；
- 成功与失败路径都恢复剪贴板和原前台窗口；
- 长图覆盖完整 HTML 页面，而不是只截取趋势图或当前视口；
- Bcc 不能可靠表达时在发送前失败，不静默丢弃。

功能验收要求：运行聚焦离线测试；使用真实 Daily Report 生成一张完整长图；通过新版 Outlook 发送到批准的测试收件人；在 Outlook Web“已发送邮件”确认主题、正文长图和无附件。代码质量要求：复用现有 HTML 和受管渲染依赖，无第二套报告布局、无平行个人邮箱机制、无临时诊断或测试文件、无无关改动，且 `git diff --check` 通过。

## 执行清单

- [ ] Mason 记录起始状态并确认现有 Daily Report、报告 HTML、截图依赖和 Outlook 公共接口所有者。
- [ ] 先补个人邮箱与 Daily Report 调用的失败测试，再实现最小公共入口和长图发送链路。
- [ ] 将根目录 Demo 改为公共入口示例，清理原型中的重复机制。
- [ ] 运行聚焦测试、语法检查、凭据扫描和 `git diff --check`。
- [ ] Atlas 按 scoped diff、测试证据和真实 Outlook Web 结果完成双门验收。

## 明确排除

- 完全无窗口、完全不抢焦点的后台发送；
- Microsoft Graph、SMTP AUTH、经典 Outlook COM；
- Excel、HTML 或其他邮件附件；
- 新的 Daily Report 数据模型、布局、导航或计划配置字段；
- Outlook/Microsoft 365 安装、卸载、修复或策略修改。

## 2026-08-11 临时回切方案

为保证 Daily Report 在个人 Outlook 自动化继续调试期间稳定可用，当前交付先恢复 `support.outlook.send_email`，由固定 SMTP 发件人 `fae-qa-auto@amlogic.com` 发送。Daily Report 使用现有完整 HTML 作为邮件正文，不生成或发送 Excel 等附件，也不调用长图渲染和个人 Outlook UI 自动化。

`support/personal_outlook/` 与完整 HTML 长图渲染能力作为独立、未接入的 support 能力保留，供后续继续调试；交付前删除所有 `TEMP_DIAGNOSTIC` 日志及其专用测试和回调，只保留稳定错误处理、确认弹窗处理和重要行为测试。不得修改用户已有的 A9 工作流、`chao_outlook.py` 或其他无关文件。

### 临时回切执行清单

- [ ] 先增加 Daily Report 使用固定 SMTP HTML 正文且无附件的回归测试，并确认旧实现失败。
- [ ] 将 Daily Report 发送入口恢复为 `support.outlook.send_email`，移除当前链路的长图渲染调用。
- [ ] 删除个人 Outlook 的全部 `TEMP_DIAGNOSTIC` 代码与仅服务于临时诊断的测试，保留稳定功能测试。
- [ ] 运行 Outlook、个人 Outlook、报告渲染和 Daily Report 聚焦测试、编译检查及 `git diff --check`。
- [ ] Atlas 审查范围、凭据风险和用户原有改动，只提交批准文件并按仓库约定推送主分支。
