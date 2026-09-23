# 通用 Jira JQL 统计卡片设计

## 目标与边界

Self-Test、Task、Customer Feedback 三张卡片本质一致：读取 Jira 页面已应用的用户 JQL，与卡片声明的固定 JQL 求交集，异步查询 Jira，把成功结果原子写入账号加卡片范围的 SQLite 快照，再由 Jira 页面和 Dashboard 挂载同一个统计组件展示。

本轮以重构现有 Self-Test 为起点建立唯一通用流程，不在旧实现旁边增加第二套 service、router、任务、缓存、统计或前端组件。三张卡片只保留声明式查询与少量显示元数据差异。完成迁移后删除 Self-Test 专属分支、Customer 占位组件、重复偏好与展示状态，以及为兼容新旧路径产生的临时包装。

本轮不提供用户在线编辑卡片定义，不新增数据库配置表，不改变 Jira 页面共享过滤器的发布语义，不引入 Dashboard 专用查询或统计 owner，也不改变认证、凭据失效和普通登出的生命周期。

## 唯一模型

Core 提供一个通用 Jira JQL 统计卡片 owner，并以不可变定义注册卡片。定义只包含：

- `card_key`、标题和首项指标文案；
- 卡片固定 JQL；
- 五个产品线所需的声明式 JQL 范围及 Wireless 优先条件；
- 固定规则 fingerprint。

不为 Self-Test、Task、Customer Feedback 建立子类或专属 service。卡片注册表只保存数据，不执行查询、不持有状态。通用 owner 负责 JQL 组合、远端验证与分页、人员及产品线统计、计数守恒和统计 payload。Web 层只按 allowlist 解析 `card_key` 并把对应定义交给同一个 owner。

前端只保留一个参数化组件。`card_key` 决定 API scope、偏好 scope、可丢弃展示缓存键、标题和首项指标文案；轮询、周期控件、产品线切换、指标切换、图表绘制、失败与取消呈现全部共用。

## JQL 流程

页面共享过滤器只发布用户条件。每张卡片的最终查询唯一由 Core 组合：

```text
effective_jql = compose_jql(applied_user_jql, card_fixed_jql(selected_period))
```

`compose_jql` 继续负责括号隔离和 `ORDER BY` 保留。校验、执行、SQLite 保存和快照有效性判断必须使用同一个 `effective_jql`，其他层不得追加、删减或重写条件。Weekly、Monthly、Quarterly、Yearly 由现有 `jira_period_condition` 产生；Yearly 表示本自然年。

固定定义可由多个声明式子句组成，但最终只能形成一个可审计的卡片固定 JQL。Wireless 优先条件同时参与固定 JQL和通用归类过程，禁止在 router 或前端增加卡片名称判断。互斥条件保证一条 issue 最多进入一个产品线；Wireless 命中后不再计入原项目产品线。

GET 只重放 SQLite，不访问 Jira。Refresh 才执行远端查询。Reuse 仅在账号、卡片、用户 JQL、固定 JQL、周期和 definition fingerprint 全部一致时恢复已有有效结果。

## 卡片定义

### Self-Test

- `issuetype = Bug`。
- `"Channel of Reporter" = "Self-Test"`。
- creator 必须属于五个批准的 FAE QA Group 之一。
- `fae-wifi-qa` 命中时归入 Wireless Connection；否则按 Jira Project `IPTV/SH/TV/OTT` 映射四个业务产品线。
- 指标为 `Bugs / Resolved / P0 / Invalid`。
- 保持当前结果口径、项目映射、人员维度和未归类计数，不因通用化改变现有 Self-Test 数据。

### Task

- `issuetype = Task`。
- creator 使用与 Self-Test 相同的五个 `membersOf(...)` Group 边界。
- Wireless Group 优先；否则按 Jira Project 映射四个业务产品线。
- 不增加 Channel、resolution、labels 或额外项目排除。
- 指标为 `Tasks / Resolved / P0 / Invalid`。

### Customer Feedback

- `issuetype = Bug`。
- `"Channel of Reporter" = "Customer-Feedback"`。
- 四个业务产品线按 Jira Project `IPTV/SH/TV/OTT` 映射。
- Wireless Connection 使用以下 labels，按 Jira 实际 label 值生成 `IN` 条件：
  - `Customer_W1`
  - `Customer_W1U`
  - `Customer_W2L`
  - `customer_w2`
  - `Customer_w1u`
  - `customer-w2`
  - `customer-w2L`
  - `customer_w1d`
- Wireless 分支排除 resolution：`Invalid Case`、`Cannot Reproduce`、`HW Fix`、`Won't Fix`、`Won't Do`；`resolution is EMPTY` 保留。
- Wireless 分支排除项目 `RD SW Platform`、`Wireless Project`。
- 命中 Wireless label 的 issue 只归入 Wireless Connection，普通产品线分支显式排除同一 label 集合，不重复统计。
- 指标为 `Bugs / Resolved / P0 / Invalid`。

上述 JQL 由字段、值、互斥分支和周期声明确定性拼接。用户提供的示例仅作为业务条件来源，不作为可直接执行的原始字符串保存。

## 数据、任务与缓存边界

继续复用现有 Jira analytics SQLite owner。查询状态、issue membership、统计 payload、active/pending generation 和 definition fingerprint 均以 `(account, card_key)` 隔离。普通登出与会话过期保留账号有效结果；明确凭据失效才走既有统一删除入口。

一个 Refresh 对应一个根任务。任务内部完成远端查询、必要的 creator group 解析、通用统计和一次原子激活；不得为每张卡片建立新的任务 registry。失败、取消、profile group 读取失败或服务重启 interrupted 均不覆盖旧有效结果。任务查询与取消继续按真实 session 加 `card_key` 授权，另一会话只能读取持久结果，不能取得或操作原任务。

浏览器 sessionStorage 只保存按账号加 `card_key` 隔离的可丢弃展示 payload，用于同步首帧。任何查询、导出或业务动作不得从中读取权威 issue ID。Jira 页面与 Dashboard 读取同一 API 和同一 SQLite 快照；Dashboard 不启动独立查询，不保存第二份结果。

## 重构与删除范围

- 把 `jira_api.py` 中 `card_key == "self-test"`、Self-Test 专属 import 和单卡片 allowlist 替换为一次注册表解析。
- 把 `team_bug_service` 中可复用的 JQL、聚合、产品线与指标模型迁入通用卡片 owner；保留 Group 常量与 Jira/产品线业务常量的单一来源。
- 删除只服务 Self-Test 的 service 包装、重复 fingerprint 组装和专属统计 builder 注入。
- 删除 `createJiraCustomerPlaceholder`，三张卡片统一通过同一个组件挂载。
- 将固定的 `jiraSelfTest` 展示缓存键改为通用 `card_key` scope；账号切换和注销仍由全局生命周期统一清理。
- Dashboard 卡片注册只声明组件和 `card_key`，不复制 Jira 页面模板、查询或状态处理。
- 迁移完成后不保留新旧双读、双写、fallback 或废弃 API；已有有效 Self-Test SQLite 数据原位兼容，只有 definition fingerprint 不匹配时按既有规则返回 `no_snapshot`，不得自动发起远端查询。

新增抽象必须替换至少 Self-Test 与两张新卡片的重复需求。禁止创建只有转发作用的基类层级、每卡片一个文件的薄包装或新的通用 repository。交付时报告生产代码新增、删除和净变化；重构部分以净减少为目标，新业务增加不得掩盖可删除冗余。

## 前端布局

Jira 页面展示三张共享卡片：Self-Test、Task、Customer Feedback。每张卡片拥有独立周期选择和结果状态，但共用页面已应用的用户 JQL。标题分别为：

- `Product Lines Self Test Jiras Statistics`
- `Product Lines Task Jiras Statistics`
- `Product Lines Customer Feedback Jiras Statistics`

Dashboard 可分别引用三张卡片，引用的仍是同一组件实例类型与对应 `card_key` 数据，不建立 Dashboard 变体。既有卡片高度、滚动、产品线、指标切换和图表机制保持共享；本轮不重新设计视觉效果。

## 验证与验收

- Core：三个定义生成确定性 fixed/effective JQL；用户 JQL、周期和 `ORDER BY` 组合正确；Customer Wireless labels、resolution、project 排除与互斥归类正确。
- 统计：三张卡片统一按 creator 展示人员；Wireless 优先；同一 issue 不重复；总数、五线合计和明确未归类计数保持守恒。
- Web：三个 `card_key` 共用 API、任务和 SQLite owner；账号、卡片和 session 隔离；GET 无远端；Refresh、Reuse、失败、取消、旧任务防覆盖和服务重启行为一致。
- 兼容：现有 Self-Test 结果口径不变；旧有效快照按 fingerprint 规则恢复；Customer 占位偏好迁入正式卡片 scope，不产生第二份 owner。
- 前端：Jira 页面三卡片与 Dashboard 三种引用均使用共享组件；周期、轮询、首帧缓存、账号切换、空结果和错误呈现一致。
- 质量：删除专属分支、占位和重复封装；无临时诊断、废弃路径和未使用样式；后端、Core、前端完整相关测试、lint、build 与 `git diff --check` 通过。

## 非目标

- 不开放自定义卡片编辑器或任意 JQL 卡片创建。
- 不修改 Jira 原生数据、创建 Issue 或写回字段。
- 不为 Dashboard 增加独立 Apply、Refresh 或远端查询入口。
- 不新增第三方依赖，不改变认证与凭据生命周期。
