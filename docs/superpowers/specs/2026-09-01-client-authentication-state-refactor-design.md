# Client 认证状态收敛设计

## 1. 目标

Client 认证由 `AuthBridge` 作为唯一运行时 owner，明确区分：

- `signed_out`：没有选中账户或用户明确退出到无凭据会话。
- `credential_required`：已有选中账户，但没有可用的运行时凭据。
- `authenticating`：正在进行 LDAP 验证。
- `authenticated`：首次手动登录已通过 LDAP 验证，或后续启动已从 Windows Credential Manager 恢复有效保存凭据，且存在可供 Python 业务使用的用户名和密码。

“选中过账户”“保存过账户资料”“存在 active_account_id”均不能单独代表已认证。QML 的 Logout 和业务 session 只能由 `authenticated` 驱动；选中账户资料仍可用于登录选择展示，但不得作为认证证明。

## 2. 权威状态与持久化边界

- `AuthAccountStore` 继续只持久化账户索引、最后账户、remember 偏好和 active account 标识，不保存密码，不把 active account 当作运行时认证证明。
- Windows Credential Manager 继续是保存 LDAP 密码的唯一安全 owner；保留既有一次性 legacy migration。
- `AuthBridge` 内存中的 `_username + _password + authenticated` 是本次进程可用 session。首次手动登录必须完成 LDAP 验证；后续进程启动读取 active account 对应的 Windows Credential Manager 凭据后直接恢复该内存 session，不重复 LDAP 验证。
- 启动时优先选择 active account，否则只展示上次账户。只有 active account 开启 remember 且能从 Windows Credential Manager 读取身份匹配、密码非空的凭据时，才直接恢复 `authenticated`；显式 Logout 会清空 active account，因此重启后保持未认证。缺失、错误凭据或未开启 remember 时进入 `credential_required`。
- 不记住密码的成功登录仅在当前进程有效；重启后进入 `credential_required`。

## 3. 单一 Python 凭据契约

`AuthBridge.runtime_credentials()` 是唯一 Python-only 业务接口：

```python
def runtime_credentials(self) -> AuthenticatedCredentials | None: ...
```

- 仅 `authenticated` 且内存用户名、密码完整时返回。
- 不声明为 QML Slot/Property，不发出密码信号，不写日志。
- Test Suite 与 Redmine 统一调用此接口。
- Test Suite 建立 Web session 时调用 Web `/api/auth/client-session`；该入口信任 Client 已完成的首次 LDAP 验证，只做非空检查并创建现有持久 session，不重复 LDAP。浏览器 `/api/auth/login` 仍是 Web 首次 LDAP 验证入口，但账户已有 Web 侧保存凭据后也不重复 LDAP。Client 专用入口本身不产生 `invalid_credentials`；只有下游业务存在明确凭据失效分类时，才可调用统一凭据失效入口，网络和服务错误不得推断为凭据失效。

## Web 账户凭据与 session 生命周期

- Web 首次验证某账户时由浏览器 `/api/auth/login` 调用 LDAP；成功后按账户保存凭据。Windows 复用 Windows Credential Manager，Linux/Ubuntu 复用现有 AES-GCM 加密存储。
- 后续浏览器登录、Web 重启以及 Client `/api/auth/client-session` 使用保存的账户凭据创建 session，不重复 LDAP。session 只保存身份、有效期和账户关联，不再拥有或删除凭据。
- 普通 logout、logout-all、session revoke、过期和清理只处理 session；账户凭据继续保留。既有数据库中的 per-session `credential_ref` 在首次读取时迁移到账户 owner，列仅作为兼容遗留存在，新 session 不再写入。
- 只有下游明确 `invalid_credentials` 才调用账户凭据失效入口：删除账户凭据并撤销该账户所有 session。Web Jira/Confluence 仅把 HTTP 401 且响应包含 `WWW-Authenticate: Basic ...` 挑战视为账号密码被认证端明确拒绝；普通 401、无认证挑战的权限响应、网络和超时仍保留为 session/服务错误，不得删除凭据。异步 Confluence 刷新保存该明确状态，后续请求继续返回 `invalid_credentials`，使 Client 进入统一重新 LDAP 流程。
- 删除或合并经仓库使用证明没有必要保留的 `currentPassword`、`transientCredential`、`authenticated_credentials`、`acquireRuntimeCredential`、`isAuthenticated` 以及 runtime credential supply 信号/QML 模式。
- `_set_auth_state(...)` 是唯一认证身份写入函数；删除只供旧测试调用的 `_apply_authenticated_identity(...)`，测试通过公开登录行为或该权威状态函数构造必要状态。
- `invalidate_runtime_credentials(code)` 是唯一 Python 内部凭据失效入口。只有业务明确返回 `invalid_credentials` 时才清理内存凭据、Windows Credential Manager 凭据、remember 标记和 active account，并统一发出认证状态变化；超时、网络不可用、`ldap_unavailable`、`service_unavailable` 和普通 session 401 均不得调用。
- Redmine 自有登录框仍可收集 Redmine 专用账号密码；这不构成第二个 SmartTest LDAP runtime credential owner。

## 4. 通知与生命周期

- `authChanged` 只表示认证身份、选中账户或认证状态发生变化；Test Suite、Redmine 等业务据此失效或重建 session。
- remember 偏好变化使用独立 `preferencesChanged`，不得触发业务 session 重置。
- 登录、切换、退出、删除当前账户会改变认证生命周期并发出 `authChanged`。
- 日志复用 `core.logging`，记录 startup selection、credential availability、authentication start/success/failure；只包含账户标识、阶段和错误码，不包含密码、Cookie 或凭据内容。

## 5. UI 行为

- LoginWindow 仅负责账户选择、LDAP 登录、remember 偏好及取消；不再提供 auto login 业务概念或控件。
- 删除 runtime credential supply 专用模式；没有已认证 session 时不得显示 Logout。
- 未引入新页面、新凭据存储或 UI 重设计；固定文本如未变化则不改翻译/QRC。

## 6. 实施检查表

- [x] 用行为测试锁定 remembered active account 重启、缺失保存凭据和不记住密码重启。
- [x] remembered active account 启动直接恢复内存 session，不执行 LDAP；业务仅在明确 `invalid_credentials` 时通过唯一入口统一失效保存凭据和 active session。
- [x] 用行为测试锁定 selected-account-only 不等于 authenticated，且 UI 不显示 Logout。
- [x] 新增唯一 `runtime_credentials()`，迁移 Test Suite 与 Redmine，删除冗余 API/信号/QML 模式。
- [x] preference toggle 只发 `preferencesChanged`，不使业务 session 重置。
- [x] 保持登录、切换、退出、删除和 legacy migration 行为。
- [x] 补安全生命周期日志测试，确认无秘密输出。
- [x] 运行 Auth/UI/Test Suite/Redmine 定向测试、源码启动、翻译/QRC（如修改）、边界、compile 和 diff check。
- [x] 迁移当前仓库 Auth Profile 与 Redmine 测试中的旧路径、旧启动语义和旧 credential supply 测试替身，保证项目 `.venv` 下完整运行。
- [x] 删除 Client 中全部 auto login 状态、存储字段、方法、QML 控件和翻译；旧 JSON 中的未知字段读取时忽略，并在后续写入时自然移除。
- [x] 开发启动未配置 `SMARTTEST_WEB_BASE_URL` 时向 Client 子进程注入 `http://127.0.0.1:8000`，外部配置优先；启动日志记录最终 Web base URL。
