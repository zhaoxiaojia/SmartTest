# Redmine 原生过滤重构设计

## 目标

SmartTest 不再重复实现 Redmine 已有的项目、状态、类型、Subject 和全文过滤语义。前端只表达查询意图，Python 将其转换为 Redmine 原生查询参数；Redmine 返回候选 Issue 后，SmartTest 只负责详情补全、未更新分析、Clone 状态和本地关注清单。

## 单一所有权

- `RedmineQuery`：保存结构化查询条件，不包含前端文案。
- 原生查询构造器：唯一负责把结构化条件转换为 Redmine 参数，包括 `f[]`、`op[...]`、`v[...][]`、分页和排序。
- `RedmineContextCollector`：唯一负责执行查询、分页并解析 Redmine Issue 列表。
- `RedmineBridge`：负责把 QML 输入转换为结构化查询、管理异步状态和应用最终结果，不拼接 URL。
- `view_model`：只把已经查询得到的数据转换为显示模型，不再重复按项目、状态、类型、Subject 或全文过滤。
- `context_store`：按 LDAP 账号保存界面条件、缓存视图和本地关注 ID。

## 普通过滤

前端保留项目、状态、类型，并新增默认可见且允许为空的 Subject。Contains text 继续独立存在。

字段映射：

- 项目：使用项目作用域 URL；全部项目使用 Redmine 全局 Issue 查询入口。
- 状态：`status_id`。
- 类型：`tracker_id`。
- Subject：`subject`，操作符 `~`。
- 全文：`any_searchable`，多个文字关键词使用操作符 `*~`。
- 精确 Issue ID：`issue_id`，操作符 `=`。

所有非全文条件由 Redmine 按 AND 组合。Contains text 中的文字关键词之间为 OR。

## Contains text 语义

输入使用空格、逗号、中文逗号、分号或换行分词，去空、去重并保留原始文本值。

例如 `60371 播放失败`：

1. 使用 `any_searchable + *~` 查询全部关键词，覆盖 Subject、Description 和 Notes。
2. 对纯数字关键词额外使用 `issue_id + =` 精确查询。
3. 两类结果按 Issue ID 合并去重。
4. 项目、状态、类型和 Subject 条件同时应用到每个查询分支。

因此最终语义是“任一全文关键词命中，或任一精确 ID 命中”，而不是把 Issue ID 和全文错误地按 AND 连接。

Redmine 返回候选 Issue 后，SmartTest 只对候选执行详情、评论、未更新和 Clone 检测。详情内容不再由本地 `_match()` 二次过滤。

## “我关注的”Quick view

“我关注的”是本地维护、Redmine 原生执行的特殊过滤器，不在普通 Issue 条目增加关注按钮。

- Quick views 增加“我关注的”。
- 前端提供一个 ID 集合输入框，接受空格、逗号、中文逗号、分号和换行。
- 确认后逐个或分批执行 Redmine `issue_id` 原生查询。
- 有效 ID 保存到当前 LDAP 账号的 context JSON；不同账号相互隔离。
- 未检索到的 ID 不保存，并在前端一次性列出。
- 打开该 Quick view 时只加载已保存 ID，随后复用统一详情和状态分析流程。
- 用户可重新编辑整个 ID 集合；空集合表示清空关注列表。

## Jira Channel of Reporter

Channel of Reporter 保持级联下拉：

- 一级默认 `Customer-Feedback`。
- 二级默认明确显示 `None`，值为空。
- 二级保留 Jira 返回的 reason1 至 reason9 选项。
- 提交 `None` 时不发送错误文本，只使用空子值。

## 缓存与异步状态

- 查询开始时保留当前缓存列表和详情。
- 查询成功后一次性替换可见视图并保存对应条件。
- 查询失败或取消时保留旧视图，只更新状态文本。
- 普通 Search、Issues assigned to me 和“我关注的”分别保存缓存，但共享同一个查询与分析管线。
- 项目元数据刷新不得重算或清空可见 Issue 列表。

## 冗余删除

- 删除 `view_model._match()` 中项目、状态、类型和文本的业务过滤。
- 删除 collector 中与原生查询构造器重复的 URL 拼接。
- 删除 Bridge 中按业务分支手写过滤参数的逻辑。
- 不保留旧本地 Contains text 兼容路径，不建立第二套关注列表文件。

## 错误处理

- Redmine 返回无结果：正常显示空列表。
- 关注 ID 部分无效：保存有效部分并列出无效 ID。
- 关注 ID 全部无效：不覆盖原有有效列表，并提示用户修正。
- 查询网络失败：保留缓存和用户输入，允许重试。
- 账号切换：立即切换到该账号的查询条件、关注 ID 和缓存。

## 验收与测试

- 原生查询参数覆盖项目、状态、类型、Subject、全文、Issue ID 和分页。
- `60371 播放失败` 生成全文分支和精确 ID 分支，并正确合并去重。
- Subject 为空时不生成 Subject 参数。
- `view_model` 不再执行重复业务过滤。
- 关注 ID 解析支持约定分隔符、账号隔离、有效/无效反馈、清空和重新编辑。
- 三类列表复用同一查询及分析管线，并保持 cache-first。
- Channel 二级默认显示 `None`，提交值为空。
- QML、翻译、QRC、Bridge、collector 和 context store 定向测试通过。
