# 本地认证会话恢复设计

## 目标与原则

SmartTest 将认证收敛为一个由 `AuthBridge` 与 `AuthAccountStore` 共同拥有的稳定状态机。LDAP 只用于用户明确发起的登录或账号切换；应用启动、页面导航和 Tool 入口均不得访问 LDAP。

三个持久化概念彼此独立：

- `active_account_id`：唯一的持久化已认证会话标记。
- `remember_password`：仅表示该账号是否在 Windows Credential Manager 中保存凭据，以及显式认证时是否需要手工输入密码。
- `auto_login`：仅表示未恢复活动会话时，启动后默认选中哪个历史账号；全局最多一个，不代表认证成功，也不依赖保存密码。

`last_account_id` 只表示最近使用或选择的账号，不能证明已认证。

## 持久化模型

继续复用现有 `auth_accounts.json`、`AuthAccountStore` 和 `support/windows_credentials.py`，不新增第二套账号或凭据存储。

- 登录或切换成功后写入新的 `active_account_id`。
- Logout、移除活动账号或显式撤销会话时清空 `active_account_id`。
- 关闭应用、关闭登录窗口、临时网络故障、认证失败、过期结果和取消切换都不清除原活动会话。
- `auto_login=true` 时关闭其他账号的 auto 标记；允许 `remember_password=false`。
- 凭据缺失只把目标账号的 `remember_password` 改为 false，不改变 auto 或活动会话。
- 旧数据缺少 `active_account_id` 时按未登录处理；保留既有一次性迁移读取能力。

## 启动状态恢复

应用创建唯一 `AuthBridge` 并完成 QML context 注册后，只调用一次 `restoreStartupSession()`：

1. 若 `active_account_id` 指向有效历史账号，从非敏感账号索引、人员配置和头像缓存恢复完整运行时身份，状态为 authenticated。
2. 该过程不读取 Credential Manager、不调用 LDAP、不启动认证 worker，并且不受 remember 或 auto 影响。
3. 若无活动会话，优先选择唯一 `auto_login=true` 的账号；否则选择 `last_account_id`。
4. 默认选择只恢复账号展示和偏好，状态仍为未登录；用户之后显式提交登录或切换时才认证。

## 显式认证事务

只有以下操作调用 LDAP：

- 用户输入账号密码并提交登录。
- 用户选择历史账号并明确发起切换；保存了凭据时由 bridge 直接从 Credential Manager 取凭据，未保存时要求输入密码。

认证事务开始时保留原活动会话快照：

- 成功：原子更新账号资料、凭据策略、头像缓存和 `active_account_id`，新账号成为唯一活动会话。
- `invalid_credentials`、`ldap_unavailable`、依赖不可用、取消或过期结果：若原来已有活动会话，完整保留原账号、profile、头像和活动标记；原来未登录则继续未登录。
- 已保存凭据被明确判定无效时，只删除目标账号凭据并关闭其 remember；临时网络错误不删除凭据或偏好。
- 关闭登录窗口时取消尚未完成的事务并清理 pending 密码引用，但不得退出原活动会话。

## UI 与导航边界

- QML 只绑定 `AuthBridge` 属性、信号和 Slot，不直接读写账号文件或凭据。
- Save password 与 Auto login 可独立勾选；Auto login 不因 Save password 关闭而禁用或被清除。
- Footer、受保护页面和 Tool 仅依据恢复后的 `authenticated` 状态放行，不触发 LDAP。
- Logout 清除活动会话后保留历史账号，并按 remember 决定下次显式认证是否需要输入密码。

## 验收与测试

- 活动会话在 auto=false 时重启仍恢复，且无 LDAP/凭据读取。
- 无活动会话时，auto 账号仅成为默认选择并保持未登录；无 auto 时回退 last 账号并保持未登录。
- auto 可独立于 remember，且全局最多一个。
- 登录和切换是唯一 LDAP 入口；启动、导航和 Tool 不调用 LDAP。
- 切换失败、LDAP 不可用、取消、关闭窗口和旧 worker 返回均保留原活动会话。
- Logout 后重启未登录；移除活动账号后未登录。
- 凭据缺失只关闭目标 remember；临时失败保留活动会话、凭据、remember 和 auto。
- 运行认证/UI 聚焦 pytest、真实 QML/route smoke、翻译检查、Credential adapter 测试、`compileall`、QRC freshness 和 `git diff --check`。

## TDD 执行记录

- RED：新增启动恢复、无活动默认选择、auto/remember 独立、取消切换保留会话测试；旧实现 5 项全部失败。
- GREEN：状态 owner 收敛后上述 5 项全部通过；最终验收以交付时命令结果为准。
