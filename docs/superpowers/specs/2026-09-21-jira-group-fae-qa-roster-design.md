# Jira Group 驱动的 FAE-QA 名册设计

## 目标与边界

Self-Test Jira 统计不再读取 `core/config/personnel.json`。唯一名册来源为当前认证 Jira 账号通过既有 `JiraGateway` 查询结果 creator 的用户 profile group；其它仍依赖 `personnel.json` 的审查和桌面功能保持不变。

## 唯一 owner

- `JiraGateway.user_groups(username)` 通过普通用户可访问的 `GET rest/api/2/user?username=...&expand=groups` 读取 profile group 并归一化错误，不调用要求管理员权限的 group-member enumeration，也不新增 HTTP client。
- `core.jira.services.team_bug_service` 负责固定 group 到 `core.product_lines` 业务常量的映射、确定性去重、多 group 成员关系和 fingerprint。
- Self-Test JQL 无需预加载完整名册。Refresh 的同一个异步任务先取得 issue rows，再对唯一 creator account 查询 profile group、构造动态名册并聚合；任一 profile 失败即令 refresh 失败，不激活待处理快照。
- 有效查询快照同时保存固定 group/business mapping fingerprint 与统计 payload。GET 和 Reuse 只重放 SQLite 快照，不访问 Jira；Refresh 才重新计算 live membership。

## 固定映射

- `fae-wifi-qa` → `WIRELESS_CONNECTION`
- `fae-SH-qa` → Smart Device Business
- `fae-stb-qa` → Global Operator & STB Business
- `fae-tv-qa` → TV Business
- `fae-iptv-qa` → China Operator Business

每个查询结果中的 creator account 按 case-insensitive identity 合并，再过滤五个批准 group 并保留全部产品线成员关系。账号与产品线均稳定排序。预查询 fingerprint 只覆盖固定 group/business 映射与固定 JQL；动态 roster 自身另有包含成员关系的确定性 fingerprint，但不用于假装预知 live membership。

## 查询与缓存

Self-Test 固定条件使用五个 `creator IN membersOf("group")` 子句的 OR 组合，并继续叠加 `issuetype = Bug`、Self-Test Channel 和既有 calendar period。统计按 Jira `creator` 归属人员；产品线仍按 Jira project 映射，Wireless Connection 成员保持既有优先规则。

异步查询成功前由同一任务逐个读取唯一 creator profile 并生成统计 payload；repository 原子激活 issue snapshot、统计 payload 与 mapping fingerprint。profile 读取失败、查询失败或取消均不替换现有有效快照。GET 与 Reuse 不刷新 group。

## 验证

- Gateway 用户 profile group 的认证请求、解析与错误行为，并证明未使用管理员 group-member endpoint。
- 名册确定性、多组成员不覆盖、空名册与 fingerprint。
- JQL 只含五个 group、使用 creator 而非 reporter，并保持周期边界。
- Web Refresh 在 issue 查询后使用当前认证 gateway 解析唯一 creators；group 失败显式且保留旧快照；GET/Reuse 仅重放持久统计且无远端请求。
