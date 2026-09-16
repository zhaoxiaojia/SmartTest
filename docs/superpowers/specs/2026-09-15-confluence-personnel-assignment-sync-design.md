# Confluence 人员业务归属增量同步设计

## 1. 目标与范围

Web 账号会话恢复或登录成功后，从 Confluence 页面 `607299166` 异步读取 `body.storage`，解析明确且已生效的人员业务归属，并由 Core 更新 `core/config/personnel.json`。会话处理不得等待远程请求；同一个 Core 刷新入口可由后续周期同步机制复用。

本阶段不增加按钮、周期调度或 UI，也不处理审批中、`offer申请中`、`New`、`Replace`、`兼`、`代` 等不明确内容。

## 2. 数据边界

- Confluence 访问复用 `ConfluenceGateway.get_page()` 及当前账号安全凭据，正文只读取 `body.storage`。
- 页面中的业务名称唯一映射为：`TV → TV Business`、`海外运营商 → Global Operator & STB Business`、`互联 → Wireless Connection`、`国内运营商 → China Operator Business`、`智能设备 → Smart Device Business`。
- Personnel 产品线 schema 统一使用五个 canonical 显示名：`China Operator Business`、`Smart Device Business`、`TV Business`、`Global Operator & STB Business`、`Wireless Connection`。页面映射与 owner baseline 写入都使用这些值；配置中的 catalog `id`/`name` 和 employee `product_line_id` 不再保存 `IPTV`、`SmartHome`、`TV`、`STB`、`Wi-Fi` 旧值。
- 人员身份只接受 Confluence `ri:user`，通过官方 `GET /rest/api/user?key=...` 解析 account 后与已有 `FAE-QA` employee 精确匹配；纯文本中文或英文均跳过，不查询、不参与归属，也不阻断同页有效身份同步。
- user-key 临时网络错误、HTTP 429 与 5xx 固定最多尝试三次；其他 4xx 不重试。
- Data Center 解析结果必须带有效 `username`/`name`/`accountId`。account 精确命中已有 `FAE-QA` 时直接使用；已有唯一同名但 account 为空的 FAE-QA 可补全明确 account。其余明确 `ri:user` 使用当前账号凭据经现有 Jira user search owner 复核，只有 account 与 displayName 均精确一致且结果唯一、active 时，才以空白人员模板加入 FAE-QA；数字后缀原样保留。
- Jira 复核失败、无结果、inactive 或歧义只跳过当前身份，不阻断同批其他明确人员的原子更新；不使用 LDAP、Teams、拼音、别名或模糊匹配。
- 人员匹配与归属更新仅针对 `FAE-QA`；同名的其他部门人员不参与匹配。
- 表格解析保留 `rowspan` 并向后续产品行传递当前业务；人员只从表头确认的 `Owner` 及 `成员1`—`成员8` 列读取，不扫描生态/产品、备注或其他列。
- 不明确标记按单个人员单元格跳过，不影响同行其他明确人员。表头/列契约不符或整页无明确 `FAE-QA` 匹配时不写文件。
- 页面明确归属替换已匹配 FAE-QA 人员的非 owner product-line assignments。经 Jira 唯一核实的新账号只创建 active/user 的空白模板，不推断组织、职级或其他字段。`product_lines` 与 `technical_centers` 中明确 `owner_account` 的归属是永久基线，所有部门只保留该基线及本次页面明确解析出的适用归属；employee 的其他字段保持原值。
- `primary` 从全部 assignments 及相关读取/持久化契约中移除；Confluence 不推断主次。
- 解析或远程访问失败、存在歧义时不写文件；只有内容实际变化时才使用同目录临时文件原子替换。

## 3. Owner 与启动流程

- `core/confluence` 是页面解析、人员匹配、assignment 合并和原子持久化的唯一业务 owner。
- `ConfluenceGateway.resolve_user_keys` 是带有界 retry 的 user-key 查询 owner；非现有 FAE-QA 的明确账号复用 `JiraGateway.search_users` 复核，不访问 user-list、LDAP 或 Teams。
- Web backend 仅在当前账号会话恢复或登录成功后，用该账号安全凭据提交进程内异步任务；不在无请求 lifespan 选账号，不保存凭据副本，不等待任务完成。
- 同一进程启动期间的同一账号只触发一次。未来周期机制调用同一个 Core refresh 方法。

## 4. 验收边界

Durable tests 覆盖 canonical 映射、`ri:user` 精确身份、Jira 唯一 active 复核、纯文本与不明确单元格跳过、`rowspan`/`colspan` 展开、Owner/成员列边界、owner 永久基线、原子写入、失败不破坏配置，以及 Web 会话触发的异步去重。交付代码不保留联调诊断日志、LDAP/user-list 路径或第二套缓存、transport、任务 owner。
