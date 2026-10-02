# Project Weekly Audit 失败证据设计

## 目标

Project Weekly Audit 在用户主动审查后，为每条 `failed` 结果生成可快速确认的证据：

- 显示对应 Confluence 页面局部截图；
- 用自然语言说明网页现状及判定失败的原因；
- 给出可执行的调整建议；
- 保留 Confluence 原始页面入口；
- 缩略图可在 SmartTest 内点击放大；
- 历史批次加载当时保存的证据，不重新抓取当前网页。

截图属于辅助证据。截图失败不改变业务审查状态，也不导致整个项目审查失败。

## 范围

### 本次实现

- 仅为 `failed` finding 自动采集截图。
- 在 SmartTest 报告卡片中展示缩略图并支持点击放大。
- 在历史 JSON 中保存截图相对路径、截图状态及自然语言判定说明。
- XLSX 导出自然语言判定说明和调整建议。
- 截图失败时显示可读提示及 Confluence 链接。
- 复用现有 Playwright `BrowserRuntime`、LDAP 临时凭据和 FluentUI 图片/弹窗机制。

### 本次不实现

- 不为 `passed` 或 `not_applicable` 采集截图。
- 不把截图直接嵌入 XLSX，避免工作簿体积快速增长。
- 不依赖 Codex、Chrome 插件或用户当前浏览器会话。
- 不保存 LDAP 密码、Cookie、浏览器 profile 或页面完整 HTML。
- 不开发定时调度和 A 项目集合页遍历。

## 用户流程

1. 用户点击审查。
2. Confluence 业务层完成项目读取及规则审查。
3. 系统收集全部 `failed` findings，并按页面分组。
4. Playwright 使用当前审查操作持有的 LDAP 临时凭据建立隔离会话。
5. 每个失败页面只加载一次；同页多个失败项复用页面。
6. 证据采集器按规则定位页面标题、更新时间、章节、表格行或附件区域。
7. 每条 finding 保存独立证据图片及证据状态。
8. 浏览器上下文关闭，临时认证状态销毁。
9. UI 显示失败原因、调整建议、缩略图和 Confluence 按钮。
10. 用户点击缩略图，在应用内弹窗查看适配窗口的大图。

## 业务合同

### Finding 展示字段

每条失败项必须向用户提供：

- `page_title`：发生问题的页面；
- `rule_id`：稳定的机器规则标识；
- `reason`：简短判定结论；
- `explanation`：自然语言说明网页实际内容、审查周期或计算证据，以及为什么触发失败；
- `guidance`：应该如何调整；
- `page_url`：Confluence 原始链接；
- `evidence_path`：批次目录内截图的相对路径，可为空；
- `evidence_status`：`captured`、`unavailable` 或 `not_requested`；
- `evidence_message`：截图不可用时的可读说明。

### 自然语言解释

自然语言解释由业务规则根据结构化证据生成，不由 QML 拼接，也不调用 AI 重新猜测结论。

示例：

> 本周审查周期为 2026-07-27 至 2026-07-30。Test Report Store 最后更新于 2026-07-11，且本周没有新增附件或报告链接，因此判定为未通过。

对应调整建议：

> 如果本周已经产出测试报告，请在周四前上传附件或添加报告链接；如果本周没有报告产出，请填写 N/A，并说明原因。

指标错误必须包含行名、实际值、规则口径和期望值。页面缺项必须说明当前页面实际为空或缺少哪类信息。

## 组件边界

### `support/confluence_integration`

- 继续负责 Confluence 页面、版本、附件和认证访问。
- 不负责规则判定、截图布局或 UI。

### `support/browser_automation`

- 继续拥有 Playwright 生命周期、浏览器启动和隔离上下文。
- Confluence 截图能力通过现有 runtime/session 接口扩展或组合，不新增第二套 Playwright launcher。

### `support/confluence_audit`

- 规则 owner 生成结构化失败证据及自然语言解释。
- 新的证据采集协作者按 `rule_id` 选择稳定定位策略。
- 服务在规则完成后批量采集失败证据，并把结果写入同一批次。
- 同一 URL 共享页面加载；每条 finding 仍拥有独立证据结果。
- 截图异常转换为 `evidence_status=unavailable`，不得覆盖原 finding 状态。

### `ui/example/bridge/ConfluenceAuditBridge.py`

- 把业务层已经生成的 explanation、证据 URL 和证据状态转换为 QML 可消费模型。
- 负责将受控的本地路径转换为图片 URL。
- 不解析网页、不推导规则、不读取截图文件内容。

### QML

- 报告卡片按顺序显示原因、判定解释、调整建议、截图缩略图和 Confluence 按钮。
- 缩略图使用现有图片组件。
- 点击缩略图打开现有 FluentUI 弹窗，大图按比例缩放，允许关闭。
- 图片缺失时显示 evidence message，不保留空白占位框。

## 截图定位策略

定位策略为规则级静态代码，不使用 AI 操作浏览器：

- 周更新：页面标题及最后修改时间区域；
- Highlights / Impact：对应标题至下一章节之间；
- 测试指标：发生不一致的具体表格行，并包含表头；
- Fail 可追踪性：Fail 行及 Comments/Jira 列；
- Test Plan：当前周表头及对应计划列；
- Environment：现有配置内容与缺失项相关区域；
- Report Store：最后修改时间及附件/报告列表。

定位不到目标元素时，可退化为主内容区截图；仍失败则记录 `unavailable`。

截图默认 PNG，限制最大像素尺寸并保留可读文字。不得截取浏览器密码提示、Cookie、开发者工具或其他站点标签页。

## 存储

每个批次使用独立目录：

```text
confluence_audit/
  history/
    <batch-id>.json
    <batch-id>/
      evidence/
        <project-id>-<rule-id>-<digest>.png
```

- JSON 只保存相对路径，避免用户目录变化导致历史失效。
- 文件名由稳定标识和摘要构成，不包含页面正文、人员姓名或凭据。
- 历史 schema 升级后仍能加载没有 evidence 字段的旧报告。
- 删除历史批次的能力不在本次范围；不额外实现清理机制。

## 认证与安全

- 只复用用户本次主动审查时 AuthBridge 提供的临时 LDAP 凭据。
- 凭据仅传入隔离 Playwright 上下文的登录流程，不写日志、JSON或截图文件名。
- 审查结束后关闭 context 和 browser session。
- 禁止持久化 storage state、Cookie、密码或浏览器 profile。
- 页面和截图只保存在现有 SmartTest 用户数据目录。

## 错误处理

- Playwright 未安装或浏览器不可用：审查照常完成，所有待截图项标记 `unavailable`。
- LDAP 网页登录失败：不影响 API 已生成的审查结论；提示重新登录后再次审查可补充截图。
- 单页面超时：只影响该页证据，继续其他页面。
- 单规则定位失败：先退化为主内容区截图，再记录不可用。
- 本地写文件失败：记录简短错误类型，不暴露路径以外的敏感信息。

## 性能

- 每次主动审查最多启动一个浏览器 runtime 和一个隔离 context。
- 失败项按 URL 分组，每个页面只导航一次。
- 同一规则证据可使用同一次 DOM 快照定位。
- 页面和单批次设置有限超时；一个页面失败不阻塞其余页面。
- 截图采集作为审查进度阶段展示，但不改变审查规则结果。

## 测试与验收

### 单元测试

- finding schema 向后兼容旧历史数据。
- 自然语言解释包含审查周期、网页事实和失败因果。
- 规则定位策略返回预期区域或正确退化。
- 截图异常不改变 finding 状态。
- 相同页面多个 finding 只导航一次。
- 证据路径保持在批次目录内。

### UI 测试

- 有证据时显示缩略图。
- 点击缩略图打开大图弹窗。
- 无证据时显示说明，不出现空白图片。
- explanation、guidance 和 Confluence 链接均可见。
- 中英文固定文字完整，QRC 资源已更新。

### 环境验收

- 使用 Muffin314 的真实失败项完成一次主动审查。
- 失败卡片显示对应局部截图。
- 点击图片可以放大并清楚阅读文字。
- 历史批次重新加载后图片仍可查看。
- 截图功能被人为禁用时，审查仍成功且结果不变。

## 复用决策

- 复用 `support/browser_automation` 的 Playwright runtime，不增加浏览器依赖或 launcher。
- 复用 AuthBridge 临时 LDAP 凭据，不增加账号配置。
- 复用 AuditHistoryStore 批次存储，不增加第二套报告存储。
- 复用 FluentUI 图片和弹窗组件，不新增图片查看框架。
- 新增代码只承担 Confluence 失败证据定位与批次资产关联这一现有 owner 尚未覆盖的职责。
