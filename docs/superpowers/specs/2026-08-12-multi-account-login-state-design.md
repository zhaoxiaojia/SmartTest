# SmartTest 多账号登录状态设计

## 1. 背景与目标

SmartTest 当前由 `AuthBridge` 管理单一 LDAP 账号、当前会话和单份本地密码秘密。该模型不能表达多个历史账号，也不能根据每个账号独立的“保存密码”选择完成自动登录或账号切换。

本功能在不改变 LDAP 认证方式和既有用户数据隔离规则的前提下，提供：

- 保存曾成功登录的账号，供下拉选择和切换；
- 每个账号独立控制是否保存密码；
- 最近使用账号保存密码时，下次启动自动登录；
- 切换到保存密码的账号时直接认证，未保存密码时要求输入密码；
- 退出登录后保留账号历史，并按该账号的保存选择决定是否保留凭据；
- 支持移除单个账号及其凭据；
- 从现有单账号状态安全迁移到多账号模型。

## 2. 范围

### 2.1 本期范围

- Windows 桌面端 LDAP 登录。
- 主应用登录窗口和已登录账号面板。
- 账号历史、最近账号、保存密码、自动登录、切换账号、退出登录、移除账号。
- 旧 `auth_state.json` 和 `auth_secret.json` 的一次性迁移。
- 中英文界面文本、QRC 资源更新和相关自动化测试。

### 2.2 不在本期范围

- 修改 LDAP 服务端、认证协议或权限模型。
- Windows Hello、PIN、二次认证或系统级账号选择器。
- 云端同步账号历史或凭据。
- 多个账号同时保持在线会话。
- “一键清空全部账号”。
- 保存 Jira、Redmine、Outlook 等其他系统的独立密码；它们继续使用各自现有 owner。

## 3. 已确认的产品语义

1. 曾成功登录的账号进入账号历史，无论该账号是否保存密码。
2. “保存密码”按账号独立生效。勾选后保存到 Windows Credential Manager；未勾选时不保存，并删除该账号可能遗留的旧凭据。
3. 最近使用账号存在有效保存凭据时，下次启动自动执行 LDAP 登录。
4. 退出登录只结束当前会话，不删除账号历史。之后是否需要输入密码取决于该账号是否保存密码。
5. 账号切换使用曾成功登录账号的下拉列表。
6. 切换目标账号保存了密码时直接登录；未保存时要求用户输入密码。
7. 开始切换时先退出当前账号。目标账号认证失败后保持未登录，不自动恢复原账号。
8. 密码永不显示、永不回填到 QML、JSON、日志或错误信息。

## 4. 方案选择

采用“账号索引 + Windows Credential Manager”方案。

- 非敏感账号元数据存入本地 JSON。
- 密码按账号分别存入 Windows Credential Manager。
- `AuthBridge` 继续作为认证和会话唯一 owner。
- 复用 `support/windows_credentials.py`，不继续扩展 `AuthBridge` 内部的单账号 DPAPI 文件机制。

未采用以下方案：

- 扩展当前 DPAPI JSON：会与现有 `WindowsCredentialStore` 形成重复凭据机制，删除、迁移和错误处理成本更高。
- 仅保存最近账号：不能满足从下拉列表切换曾登录账号的要求。

## 5. 架构与所有权

### 5.1 `AuthBridge`

`ui/example/bridge/AuthBridge.py` 是唯一认证与会话 owner，负责：

- LDAP 用户名规范化和认证；
- 当前会话的账号、认证状态、用户资料和头像；
- 启动自动登录；
- 手动登录、账号切换、退出登录、移除账号；
- 协调账号索引与凭据存储；
- 向 QML 暴露账号列表、当前选择、忙碌状态和可执行动作；
- 只返回稳定的状态码和可翻译错误类别，不向 UI 暴露密码或底层凭据异常细节。

LDAP 连接、身份资料匹配和现有 `pageStateAccount` 规则保持由 `AuthBridge` 管理。

### 5.2 `AuthAccountStore`

新增一个轻量账号索引 owner，建议位于 `ui/example/bridge/auth_accounts.py`。它只负责 `%LOCALAPPDATA%\Amlogic\SmartTest\auth_accounts.json` 的读写、校验和原子更新，不负责认证或凭据访问。

建议数据结构：

```json
{
  "schema_version": 1,
  "last_account_id": "sha256-derived-id",
  "accounts": [
    {
      "account_id": "sha256-derived-id",
      "username": "user.name",
      "display_name": "User Name",
      "remember_password": true,
      "last_login_at": "2026-08-12T10:30:00+08:00"
    }
  ]
}
```

约束：

- `account_id` 由规范化账号的 `casefold()` 值计算稳定摘要，避免凭据 target 直接包含域账号字符。
- 同一账号的大小写、`DOMAIN\\user` 与可识别的等价输入不得产生重复条目；规范化规则由 `AuthBridge` 单点提供。
- `remember_password` 表示产品选择和期望状态，不作为“凭据一定可读”的证明；实际自动登录前仍需读取 Credential Manager。
- 账号按 `last_login_at` 降序输出，最近成功登录账号置顶。
- JSON 中不保存密码、密码掩码、Token、LDAP bind 结果或完整异常。
- 写入采用临时文件替换，损坏文件不得导致应用启动失败。

### 5.3 Windows Credential Manager

复用 `support.windows_credentials.WindowsCredentialStore`，为 SmartTest LDAP 登录使用独立 target prefix，例如：

```text
SmartTest/Auth/<account_id>
```

每个账号一条 Generic Credential：

- credential reference：`account_id`；
- username：规范化后的登录账号；
- password：用户输入的 LDAP 密码；
- persistence：沿用当前 `CRED_PERSIST_LOCAL_MACHINE` 行为。

QML 和账号 JSON 不直接调用或读取 Credential Manager。凭据读取后只在认证调用所需的最短生命周期内存在，不进入属性、Signal 参数、返回对象或日志。

### 5.4 `LoginWindow.qml`

QML 只负责展示和交互：

- 历史账号下拉框；
- 新账号输入入口；
- 密码输入框；
- “保存密码”复选框；
- 自动登录、登录和切换过程的忙碌状态；
- 已登录账号资料、切换、退出和移除动作；
- 本地化错误提示。

QML 不读写账号 JSON、Credential Manager 或 `FrontendStateStore`。密码输入框继续明确标记为敏感且禁止前端持久化。

## 6. 状态模型

`AuthBridge` 对外提供以下互斥状态：

| 状态 | 含义 | 允许的主要动作 |
|---|---|---|
| `signed_out` | 未登录，等待选择或输入账号 | 选择账号、输入密码、登录 |
| `credential_required` | 已选账号没有可用保存凭据 | 输入密码、修改保存选项、登录 |
| `authenticating` | 正在执行 LDAP 登录 | 取消窗口关闭以外的认证动作均禁用 |
| `authenticated` | 当前账号已登录 | 切换账号、退出、移除账号 |
| `auth_failed` | 最近一次认证失败 | 修改密码、重新登录、选择其他账号 |

不新增第二套“视觉登录状态”。QML 根据 `AuthBridge` 暴露的状态、当前账号和账号列表渲染。

建议账号模型每项包含：

```text
accountId: str
username: str
displayName: str
rememberPassword: bool
isCurrent: bool
isLastUsed: bool
```

不得包含密码、Credential Manager target 全名或内部异常。

## 7. 业务流程

### 7.1 应用启动

1. 加载并校验账号索引。
2. 若需要，执行旧单账号状态迁移。
3. 取得 `last_account_id` 对应账号。
4. 若账号不存在，进入 `signed_out` 并显示空账号输入。
5. 若账号未启用保存密码，进入 `credential_required`，默认选中该账号并聚焦密码框。
6. 若账号启用保存密码，尝试从 Credential Manager 读取凭据。
7. 凭据存在时进入 `authenticating`，执行 LDAP 登录。
8. 登录成功后进入 `authenticated`，更新显示资料与最近登录时间。
9. 凭据缺失、不可读或 LDAP 认证失败时，删除不可用凭据，把该账号更新为 `remember_password=false`，进入 `auth_failed`；账号历史继续保留。

自动登录必须在 UI 可呈现状态后执行，避免同步 LDAP 调用阻塞窗口首次显示。认证期间展示明确加载状态并禁用重复提交。

### 7.2 手动登录新账号

1. 用户选择“使用其他账号”并输入账号、密码。
2. 用户可勾选“保存密码”。
3. `AuthBridge` 校验非空输入并执行 LDAP 认证。
4. 认证失败时清空密码输入，不新增账号历史，不写凭据。
5. 认证成功时写入或更新账号历史，并设为最近使用账号。
6. 勾选保存密码时写入 Credential Manager；未勾选时删除同账号旧凭据。
7. 凭据写入失败时，登录会话仍可成功，但账号按未保存密码处理，并向用户提示“已登录，但密码未保存”。

账号只有在首次 LDAP 登录成功后才进入历史。

### 7.3 选择历史账号

- 选择当前已选账号不触发认证。
- 未登录时选择保存密码的账号：立即读取凭据并认证。
- 未登录时选择未保存密码的账号：进入 `credential_required`。
- 下拉项的锁形标记只表示该账号选择了保存密码，不展示密码长度或掩码。
- 若索引标记为已保存但凭据不存在，自动修正索引并要求输入密码。

### 7.4 已登录状态切换账号

1. 用户从账号下拉框选择不同账号。
2. `AuthBridge` 清除当前内存密码、认证身份、资料和当前账号相关的动态状态。
3. 目标账号有可读凭据时直接 LDAP 登录；否则进入密码输入状态。
4. 目标认证成功后发布一次完整的账号变更通知，使依赖 `pageStateAccount` 的页面切换到目标命名空间。
5. 目标认证失败后保持未登录，不恢复旧账号。

切换期间不得让旧账号身份与新账号页面状态同时可见。

### 7.5 退出登录

- 清除当前内存密码、认证状态、用户资料和会话级动态数据。
- 保留账号索引。
- 若该账号 `remember_password=true`，保留 Credential Manager 凭据。
- 若该账号 `remember_password=false`，确保 Credential Manager 中不存在该账号凭据。
- 退出后默认选中刚退出账号；有保存密码时用户再次选择或执行登录可直接认证，未保存时必须输入密码。

退出登录本身不触发自动重新登录。自动登录只在新的应用启动周期发生。

### 7.6 移除账号

- 二次确认后删除账号索引条目、Credential Manager 凭据和该账号头像缓存。
- 若移除当前账号，先结束当前会话。
- 若移除 `last_account_id`，选择剩余账号中最近成功登录者作为新的最近账号；没有剩余账号则置空。
- 不删除该账号已有的 Jira/UI 页面偏好和历史报告。本期仅删除认证相关数据，避免隐式破坏业务数据。

## 8. 旧状态迁移

迁移源：

- `%LOCALAPPDATA%\Amlogic\SmartTest\auth_state.json`
- `%LOCALAPPDATA%\Amlogic\SmartTest\auth_secret.json`

迁移规则：

1. 仅处理结构有效、包含账号且旧密码可成功解密的旧状态。
2. 先把凭据写入 Windows Credential Manager。
3. 凭据写入成功后，再写新账号索引，标记 `remember_password=true` 和最近账号。
4. 新索引写入成功后，删除旧 `auth_state.json` 和 `auth_secret.json`。
5. 任一步失败时保留尚未安全迁移的旧文件，不写半完成的“已保存密码”状态。
6. 迁移过程可重复执行且结果一致，不产生重复账号。
7. 旧状态只有账号、没有有效密码时，只迁移账号历史并标记 `remember_password=false`。

迁移完成后的生产流程不再读写旧文件。旧 DPAPI 辅助函数在迁移兼容期结束后从 `AuthBridge.py` 删除；迁移读取逻辑保持局部、只读和可测试。

## 9. 异常处理

### 9.1 LDAP 认证失败

- 错误账号或密码：显示统一的账号/密码错误，不泄露 LDAP 服务端细节。
- 网络或服务器不可用：提示暂时无法连接 LDAP，可重试或选择其他账号。
- 自动登录认证失败：删除该账号保存凭据并要求重新输入密码。
- 手动登录失败：清空密码输入，不更改账号历史和当前保存状态。

### 9.2 凭据存储失败

- 读取不存在：降级为未保存密码。
- 读取损坏或访问失败：不自动登录，提示需要重新输入密码；不得删除无法判定归属的其他凭据。
- 写入失败：允许本次 LDAP 登录成功，但 `remember_password=false`，提示密码未保存。
- 删除时目标不存在：按幂等成功处理。
- 删除发生系统错误：账号可从下拉历史移除，但必须提示凭据清理失败，并保留可重试的安全记录；不得静默宣称已完全删除。

### 9.3 账号索引损坏

- 记录 warning 级结构化日志，但日志不包含密码或凭据内容。
- 将损坏文件改名为带时间戳的 `.corrupt` 备份后创建空索引。
- Credential Manager 中的孤立凭据不自动枚举或删除，避免误删其他版本或安装实例的数据。

### 9.4 并发与重复操作

- `authenticating` 状态禁止重复点击登录、切换、退出或移除。
- 每次认证请求带递增 generation；过期请求完成后不得覆盖较新的账号选择。
- 应用关闭时不强制等待无限期 LDAP 请求；现有连接超时策略继续生效。

## 10. 安全与隐私约束

- 密码只存在于密码输入控件、认证调用局部变量和 Credential Manager 适配层的短生命周期缓冲区。
- QML 属性、Signal、JSON、缓存、日志、异常文本、测试快照、报告和截图不得包含密码。
- 密码控件禁止 `FrontendStateStore` 持久化，切换账号、认证失败、退出和窗口关闭时清空。
- 不通过“读取后回填密码框”实现保存密码；保存凭据时密码框保持空白。
- 日志可记录账号、操作、结果类别和错误码，但不得记录密码、CredentialBlob 或 LDAP 完整 bind payload。
- 账号移除与保存选项关闭必须针对规范化后的单一 `account_id`，避免大小写或域前缀差异留下旧凭据。
- 认证成功之前不得把输入账号标记为可信历史账号。

## 11. UI 设计

### 11.1 未登录视图

- 账号控件使用可输入的下拉框，列表为成功登录历史。
- 每项显示头像或首字母、显示名、账号；保存了密码的账号显示锁形图标。
- 列表尾部提供“使用其他账号”。
- 未保存密码的历史账号被选中时显示密码输入框和“保存密码”复选框。
- 新账号默认不勾选“保存密码”，避免未经明确选择持久化凭据。
- 保存密码账号自动认证时显示“正在登录…”和进度状态，不显示密码框。

### 11.2 已登录账号面板

- 保留现有资料卡片。
- 在账号区域增加账号下拉切换入口。
- 提供“退出登录”和“移除账号”两个语义明确的动作。
- “移除账号”使用确认对话框，说明会删除此设备保存的登录信息，但不会删除 SmartTest 业务数据。

### 11.3 可用性

- 登录提交支持 Enter。
- 忙碌期间控件禁用，避免重复请求。
- 认证失败后焦点回到密码框。
- 下拉列表为空时不展示空面板。
- 固定文本同时更新 `example_en_US.ts` 和 `example_zh_CN.ts`，不得在 Python/QML 中维护双语字典或 fallback 文案。

## 12. 接口设计

最终接口名可在实现时按现有命名规范微调，但职责不可改变。建议 `AuthBridge` 暴露：

```text
accounts: QVariantList
selectedAccountId: str
authState: str
authBusy: bool
rememberPassword: bool

selectAccount(account_id: str) -> QVariantMap
login(username: str, password: str, remember_password: bool) -> QVariantMap
setRememberPassword(enabled: bool) -> QVariantMap
logout() -> None
removeAccount(account_id: str) -> QVariantMap
startAutoLogin() -> None
```

返回对象只包含：

```text
success: bool
code: str
message: str
requiresPassword: bool
```

`message` 由 `AuthBridge.tr(...)` 生成固定界面文本；外部 LDAP 文本只进入受控日志，不直接展示。

## 13. 测试与验收

### 13.1 账号索引

- 空索引、正常读写、最近账号排序和原子更新。
- 等价账号规范化后不重复。
- 损坏索引安全恢复。
- JSON 不包含密码或凭据数据。

### 13.2 凭据行为

- 成功登录且勾选保存密码后写入对应账号凭据。
- 成功登录但未勾选时删除该账号旧凭据。
- 登录失败不写入凭据或历史账号。
- 读取缺失/失败时要求输入密码。
- 移除账号只删除目标账号凭据。
- 凭据读写失败的降级行为和用户提示符合设计。

### 13.3 启动与自动登录

- 最近账号保存有效凭据时自动登录。
- 最近账号未保存密码时停留登录页并选中账号。
- 自动登录失败后保留账号、清除失效凭据并要求密码。
- 自动登录不会在同一启动周期因退出登录再次触发。

### 13.4 切换与退出

- 保存密码账号可直接切换。
- 未保存密码账号切换后要求密码。
- 切换开始即结束原会话；失败后保持未登录。
- 退出登录保留账号历史，并按保存选择保留或删除凭据。
- 切换成功后 `pageStateAccount` 与用户资料同步更新，不出现旧账号数据闪现。

### 13.5 迁移

- 有效旧状态迁移为一个已保存账号并删除旧文件。
- 无有效旧密码时只迁移账号历史。
- Credential Manager 写入失败时保留旧文件。
- 重复迁移不产生重复账号。
- 迁移日志不包含秘密。

### 13.6 UI、翻译与资源

- QML 账号下拉、密码条件显示、保存密码复选框、忙碌禁用、退出和移除行为测试。
- 密码控件不参与前端持久化。
- 中英文固定文本完整，无 `unfinished`、乱码或 fallback。
- 重建对应 QRC，并确认生成资源晚于 QML 和翻译源。

### 13.7 验证命令

实现阶段至少执行：

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_auth_bridge.py testing\self_tests\ui\test_login_window.py -q
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_owned_ui_translations.py -q
.\.venv\Scripts\python.exe -m compileall -q ui\example\bridge support\windows_credentials.py
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
git diff --check
```

若仓库中的实际登录窗口测试文件名不同，实现计划应使用现有对应测试 owner，不为文件名一致性创建重复测试模块。

最高实际环境验收包括：在 Windows 用户会话下以两个真实 LDAP 测试账号验证保存、重启自动登录、无密码切换、需密码切换、错误密码、退出和移除。没有真实 LDAP/Windows Credential Manager 环境时必须明确报告该限制。

## 14. 完成标准

### Functional Acceptance

- 多个成功登录账号可在下拉框中选择。
- 每账号“保存密码”选择独立且持久。
- 最近保存密码账号可在新启动周期自动登录。
- 保存密码账号直接切换，未保存密码账号要求输入密码。
- 切换失败保持未登录，不恢复旧账号。
- 退出保留账号历史，并正确保留或删除凭据。
- 移除账号只清理目标账号认证数据。
- 旧单账号状态安全迁移。

### Code Quality

- `AuthBridge` 是唯一会话 owner，QML 不读写凭据或账号文件。
- 复用 `WindowsCredentialStore`，不保留长期并行 DPAPI 凭据实现。
- 不新增密码日志、密码持久化、重复账号状态或页面局部认证流。
- 测试保护安全边界和主要状态转换，不保留探索性断言或实现形状测试。
- 相关测试、编译、翻译、QRC 时序和 `git diff --check` 全部通过。

## 15. 实施边界与复用结论

本功能是跨认证状态、凭据存储、QML 和用户隔离状态的公共机制变更，实施应使用 Atlas + Mason 双交付。Mason 负责目标代码调查、TDD 实现、清理和自测；Atlas 负责需求边界、设计一致性、diff 验收和最终交付。

复用结论：扩展 `AuthBridge` 作为唯一认证 owner，复用 `WindowsCredentialStore` 作为唯一密码持久化机制，保留现有 LDAP、人员资料、头像和 `pageStateAccount` 流；只新增一个非敏感账号索引 owner，不新增第二套会话、凭据或用户页面状态机制。

## 16. 实施检查表

实施遵循 TDD，每项先建立行为失败证据，再做最小实现；不得为了测试方便暴露密码或增加第二套认证状态。

### 16.1 账号索引与凭据引用

- [ ] 在现有 UI self-tests 中增加账号规范化、去重、排序、损坏恢复和原子写入测试。
- [ ] 新增 `ui/example/bridge/auth_accounts.py`，实现非敏感 `AuthAccountStore`，并保持单一文件 owner。
- [ ] 为 SmartTest LDAP 定义独立 `WindowsCredentialStore` prefix 和稳定的 `account_id` 引用。
- [ ] 验证账号 JSON、日志和公开模型均不含密码或 CredentialBlob。

### 16.2 `AuthBridge` 会话状态机

- [ ] 为启动自动登录、手动登录、保存选项更新、退出、切换失败和移除账号增加持久行为测试。
- [ ] 扩展 `AuthBridge` 的账号模型、选择状态、认证状态和忙碌状态接口。
- [ ] 将成功登录后的账号索引与凭据更新集中在一个提交点，失败路径不得写入半完成状态。
- [ ] 确保切换开始即清除旧会话，过期认证结果不能覆盖新选择。
- [ ] 保持 `pageStateAccount`、LDAP 资料、头像和既有权限消费方接口兼容。

### 16.3 旧状态迁移

- [ ] 覆盖有效旧凭据、无密码旧账号、凭据写入失败、索引写入失败和重复迁移测试。
- [ ] 增加局部只读迁移器，按“凭据写入 → 新索引写入 → 删除旧文件”的顺序迁移。
- [ ] 从正常认证路径移除旧 `auth_secret.json` 写入和并行 DPAPI 保存机制。
- [ ] 验证迁移日志和异常均不包含密码。

### 16.4 登录与账号界面

- [ ] 为账号下拉、新账号入口、条件密码输入、保存密码选项、忙碌禁用、退出和移除增加 QML/bridge 测试。
- [ ] 修改 `LoginWindow.qml`，只消费 `AuthBridge` 模型和动作，不直接访问持久化 owner。
- [ ] 保留现有已登录资料卡片，并加入账号切换和移除入口。
- [ ] 确保密码控件切换、失败、退出和关闭时清空，并继续禁用前端持久化。
- [ ] 同步中英文翻译并重建 QRC。

### 16.5 集成验收与清理

- [ ] 运行账号、登录窗口和翻译聚焦测试。
- [ ] 运行 UI bridge `compileall`、QRC 时序检查和 `git diff --check`。
- [ ] 在可用 Windows Credential Manager 环境验证凭据写入、读取、删除和旧状态迁移。
- [ ] 在可用 LDAP 环境以两个账号验证启动自动登录、直接切换、需密码切换、失败后未登录、退出和移除。
- [ ] 清理临时诊断、探索性测试、旧 DPAPI 生产写入和重复状态流。
- [ ] Atlas 从实际 diff、测试证据、复用结论和净生产代码增长完成最终验收。
