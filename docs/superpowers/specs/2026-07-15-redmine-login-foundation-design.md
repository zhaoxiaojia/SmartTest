# SmartTest Redmine 登录与全局集成基础设计

## 目标

为 SmartTest 建立可被多个页面和产品线复用的浏览器自动化与 Jira 集成能力，并以 SmartHome Redmine 登录作为首个 Playwright 业务。SmartTest 展示原生工作台，不嵌入或照搬 Redmine 网页。

本阶段完成三项工作：

1. 将现有 `tools/` 迁移为 `support/`。
2. 将现有 `jira_tool/` 按职责拆分为全局 `support/jira_integration/` 与 Jira 页面薄层 `jira/`。
3. 建立 `support/browser_automation/`，并实现 `tool/SmartHome/redmine/` 的登录流程。

Redmine 查询、Bug 详情解析、Jira 字段映射、仿 Jira 详情布局和批量 Clone 不在本阶段实现。

## 目录与所有权

```text
SmartTest/
├─ support/
│  ├─ browser_automation/       # 全局 Playwright 运行时与隔离会话
│  ├─ jira_integration/         # 全局 Jira REST、字段、缓存和服务
│  ├─ logging.py
│  ├─ report.py
│  ├─ param_conversion.py
│  ├─ scripts/
│  └─ packaging/
├─ jira/                        # Jira 页面专属工作区与展示业务
├─ tool/
│  └─ SmartHome/
│     └─ redmine/               # SmartHome Redmine 业务适配
├─ testing/
└─ ui/
```

### `support/browser_automation`

拥有 Playwright 浏览器进程生命周期、Browser Context 创建与回收、系统/账户会话隔离、导航超时、通用诊断和人工输入事件合同。它不包含 Redmine、SmartHome、Bug、Filter 或 Jira 等业务概念。

应用共享一个浏览器进程；每个“系统标识 + 服务地址 + 账户”使用独立 Browser Context。Cookie、缓存和认证状态不得跨 Context 共享。

### `support/jira_integration`

拥有可被任意页面或工具复用的 Jira 能力，包括认证、唯一 REST 出口、字段元数据与提取、稳定模型、通用缓存、查询及未来 Create Issue 服务。其包名不得使用 `jira`，避免与第三方 Python Jira 库冲突。

### 根目录 `jira`

只拥有 Jira 大页面需要的工作区状态、页面浏览用例、展示组装和 UI 适配。它依赖 `support/jira_integration`，但不得成为其他业务访问 Jira 的入口。

### `tool/SmartHome/redmine`

拥有 Redmine 页面识别、选择器、登录状态机及 Redmine 专属错误分类。它依赖 `support/browser_automation`。未来 Clone 功能只能调用 `support/jira_integration`，不得依赖根目录 `jira`。

## Redmine 登录流程

公开入口 `https://support.amlogic.com/` 当前重定向至 `/login?back_url=...`。登录表单通过 `POST /login` 提交 CSRF Token、用户名和密码。初始登录页没有验证码，手机验证预计出现在账号密码提交后的后续状态中。

登录状态机：

1. 从 SmartTest 当前认证会话取得内存中的 LDAP 用户名和密码。
2. 创建 Redmine 专属隔离 Browser Context，访问 Redmine 入口并提交默认 LDAP 凭据。
3. 根据页面的明确证据分类结果：登录成功、需要验证码、账号密码错误、页面结构不受支持或网络失败。
4. 只有出现明确的账号密码错误提示或等价认证失败证据，才请求用户在 SmartTest 中输入独立的 Redmine 用户名和密码，然后重试。
5. 如果跳转到验证码或手机验证状态，只请求验证码，不得误判为账号密码错误。
6. 登录成功后保留当前 Context 供后续 Redmine 操作复用；会话失效时重新进入完整登录状态机。

SmartTest 不显示默认 LDAP 用户名和密码。用户补充的 Redmine 凭据及验证码只在当前登录流程的内存中使用，不写入日志、配置、Cookie 之外的持久化文件或诊断材料。

## UI 合同

Redmine 页面只展示 SmartTest 原生工作台状态。登录阶段允许显示原生进度和输入弹窗：

- 正在使用当前 SmartTest 账户登录；
- 需要 Redmine 独立账号密码；
- 需要手机验证码；
- 登录成功；
- 可执行的失败原因与重试入口。

Bridge 仅转换 Qt 属性、信号、槽和异步结果。Bridge 与 QML 不直接调用 Playwright、不持有网页选择器、不判断 Redmine 页面结构。

## 错误处理与诊断

登录错误至少分为凭据错误、验证码待输入、验证码错误、网络/超时、页面结构变化和内部运行时错误。固定应用文本由 UI 翻译；Redmine 返回的必要外部错误保持原文并避免包含敏感数据。

诊断日志不得记录密码、验证码、认证 Token、Cookie 或完整受保护页面内容。开发模式可保留经过脱敏的当前 URL、状态名称和选择器失败位置。第一阶段允许在调试配置下显示 Playwright 窗口，正式模式默认后台运行。

## 迁移顺序

1. 独立完成 `tools/` 到 `support/` 的机械迁移，更新导入、脚本、构建清单、文档与测试。
2. 将 `jira_tool/` 的通用能力迁移到 `support/jira_integration/`，页面专属能力迁移到根目录 `jira/`，保持现有 Jira 页面行为。
3. 建立并测试 `support/browser_automation/`。
4. 建立 `tool/SmartHome/redmine/` 登录状态机与 UI 适配。
5. 使用授权账户进行真实环境验证；用户亲自提供需要的验证码。

各阶段应形成独立、可审查的提交，不混入后续查询、映射、布局或 Clone 功能。

## 验收标准

- 原 `tools` 导入和工程脚本全部迁移到 `support`，不存在有效的 `tools` Python 包依赖。
- 现有 Jira 页面功能与持久化数据保持兼容；通用 Jira 能力可从 `support.jira_integration` 使用。
- Playwright 浏览器进程可复用，不同系统/账户 Context 的 Cookie 与缓存隔离。
- Redmine 首先使用当前 SmartTest LDAP 凭据，且默认凭据不展示、不落盘、不进入日志。
- 明确凭据错误时才弹出独立账号密码输入；验证码状态只弹出验证码输入。
- 成功登录后会话可被同一 Redmine Context 复用；失效后能重新登录。
- 单元测试覆盖登录状态转换、错误分类、Context 隔离和敏感信息脱敏。
- 现有 Jira、认证和 Tool 页面聚焦测试通过，源码模式能够启动。
- `git diff --check` 通过，且不包含无关或用户已有改动。

## 交付方式

这是跨越公共包、Jira 页面、Tool 页面和 UI 合同的高风险重构，采用 SmartTest 双 Codex 交付。Atlas 负责范围、设计和最终验收；Mason 负责目标代码调查、实现、清理和自测。
