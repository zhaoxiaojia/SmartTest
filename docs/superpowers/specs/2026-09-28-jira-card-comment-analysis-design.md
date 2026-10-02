# Jira 卡片评论人分析设计

## 目标

将所有 Jira 统计卡片的 `Resolved` 指标替换为 `Comments`，并将 `P0` 指标替换为 `Verify`。卡片按既有 JQL 范围查询 issue 时，同时取得评论和状态历史；按产品线、评论人和验证人统计。评论人与验证人都只统计 FAE-QA 花名册成员。

## 范围

- 覆盖 Self-Test、Task、Customer Feedback 三张 Jira 统计卡片。
- 保留现有 Bugs、Invalid、产品线、周期对比、认证、异步任务和 SQLite 快照机制。
- P0 指标移除；本次实现验证历史和验证人分析。

## 数据边界

1. issue 集合仍由每张卡片的有效 JQL 决定，其中包含共享的 `creator IN membersOf("fae-*-qa")` 约束。
2. 批量查询在基础字段外请求 Jira `comment` 字段；不调用每个 issue 的 `issue_get_comments`。
3. 评论记录使用 Jira 返回的作者和创建时间；只有作者在 FAE-QA 花名册中时才进入统计。
4. 评论归属到该 issue 的 Jira 项目对应产品线。评论人本人在花名册中的产品线归属不改变该归属。
5. 当前期、上一期仍完全由既有卡片 JQL 的自然周期条件决定；在该 issue 集合内累计评论条数。本次不新增评论创建时间筛选，评论创建时间仅作为后续评论人分析的原始数据保留。
6. 验证记录取 issue history 中最后一次 `Resolved -> Verified` 状态流转；验证人必须在 FAE-QA 花名册中，归属到该 issue 的 Jira 项目产品线。

## 调用与并发

```text
有效卡片 JQL
  -> search_all_payloads(fields=CORE_FIELDS + ["comment"], expand=["changelog"], page_size=100)
  -> 每页 100 条、最多 4 个分页请求并发
  -> Core 解析评论和最后一次验证记录，并按花名册过滤
  -> 当前期/上一期评论聚合
  -> SQLite 卡片快照
  -> Web 卡片
```

真实请求验证显示 history 数据密度高时响应显著变大，因此卡片使用每页 100 条与最多 4 并发；Gateway 的既有默认 1000 条分页保持不变，其他调用方不受影响。

## Core 契约

- `JiraGateway`：允许统计卡片调用显式传入额外字段、expand 和页大小；默认基础查询字段及默认 1000 条分页保持不变。
- 评论解析：复用既有 `IssueComment` 的作者和创建时间语义，不复制详情页的单 issue 获取机制。
- 验证解析：从 history 中提取最后一次 `Resolved -> Verified` 的操作者和时间，不创建逐 issue 获取流程。
- 统计结果：人员行的 `resolvedCount` 改为 `commentCount`，`p0Count` 改为 `verifyCount`；评论统计单位为评论条数，验证统计单位为已验证 issue 数。
- 花名册：复用现有 `load_fae_qa_roster()` 与产品线映射；非 FAE-QA 评论作者被排除。

## Web 契约

- 顶部指标从 `Resolved` 改为 `Comments`，从 `P0` 改为 `Verify`。
- 当选择 `Comments`，柱状图按评论人显示当前期与上一期评论条数及既有差异展示。
- 当选择 `Verify`，柱状图按验证人显示当前期与上一期已验证 issue 数及既有差异展示。
- 现有 Bugs、Invalid 的请求参数和展示不变。
- 异步卡片加载通过 `core.logging.smart_log` 记录安全的阶段耗时、期别、页数和处理数量；不得记录凭据、JQL 正文、issue/history/comment 正文。

## 验收

- 卡片查询请求同时携带 `comment` 与 `changelog`，卡片分页为 100、最大并发为 4；其他 Gateway 调用保持既有默认分页。
- 非 FAE-QA 评论作者不出现在 Comments 图表或总数中。
- 非 FAE-QA 验证人不出现在 Verify 图表或总数中；重复验证只归属最后一次验证人。
- 评论随命中当前期或上一期 JQL 的 issue 归入对应周期，且按 issue 的产品线显示；本次不按评论创建时间再筛选。
- Resolved、P0 不再出现在卡片指标或接口展示数据中。
- 覆盖 Core 聚合、Jira 请求字段、Web API、加载耗时日志和前端卡片测试；现有 Jira 卡片指标回归通过。

## 实施检查清单

- [ ] 先补充 history、FAE-QA 验证人、最后一次验证、100 条卡片分页与日志字段的失败测试。
- [ ] 以最小改动扩展批量卡片请求和 Core 聚合。
- [ ] 替换 Web 卡片的 P0 指标、图例和前端测试。
- [ ] 运行 Core、Web API、前端卡片相关测试及完整后端测试。
- [ ] 移除调试残留，执行 `git diff --check`，审核并提交。
