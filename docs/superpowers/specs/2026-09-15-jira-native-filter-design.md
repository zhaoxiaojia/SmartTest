# Jira 原生过滤器复刻设计

## 目标

在 SmartTest Jira Analytics 页面复刻 Jira Server/Data Center 的 Issue Filter 使用方式，让熟悉 Jira 的用户可以通过 Basic 条件或 Advanced JQL 确定分析数据范围。同时保留 SmartTest 自己的视觉体系、账号隔离、SQLite 快照和异步查询机制。

本设计只覆盖 Jira 查询过滤器。固定周期对比过滤器是独立能力，后续单独设计和实现，不混入本次查询过滤器。

## 业务边界

- Jira Analytics 查询过滤器与 Tools 周审查过滤器是两个独立业务 owner，互不读取或覆盖对方的条件与快照。
- Jira Analytics 过滤器只确定 Issue 数据范围，不决定图表类型、统计维度、Top N 或周期对比方式。
- Browser 只提交一次已应用查询，不通过 Web 分页收集 Jira Issue。
- 后端通过 `core/jira` 统一入口访问 Jira REST API；全量查询沿用 `atlassian-python-api`、每页 1000 条、同一 Gateway 全局最多 4 个在途请求。
- SQLite 是账号查询条件、有效查询快照和 Issue 数据的持久 owner；前端只保存未提交控件状态和可丢弃的同步首帧展示。
- 第一版只读取 Jira Saved Filter，不在 Jira 中创建、覆盖、收藏、共享或删除 Filter。

## 页面结构

Jira Analytics 页面顶部显示一条紧凑的查询栏，布局参考 Jira Basic Search，视觉使用 SmartTest 自有组件：

```text
Project: All ▾  Type: All ▾  Status: All ▾  Current User ▾
Contains text   More ▾   Search   Advanced
```

用户从 `More` 添加的条件显示在第二行，每个条件是可展开、可移除的条件块：

```text
Resolution: Unresolved ×
Component: Video ×
Created Date: Last 30 days ×
```

查询栏包含两种互斥编辑模式：

- **Basic**：通过字段控件构建 JQL。
- **Advanced**：直接编辑完整 JQL，显示校验状态、Search 和切回 Basic 的入口。

两种模式编辑的是同一个查询，不创建两份独立过滤状态。

## Basic 模式

### 固定条件

第一版固定展示以下常用条件：

- Project
- Issue Type
- Status
- Current User
- Contains text
- Resolution

Project、Issue Type、Status 和 Resolution 支持多选。同字段多个值生成 `IN (...)`；不同字段之间使用 `AND`。Current User 使用 Jira 函数 `currentUser()`。Contains text 生成 Jira 文本搜索条件，不在浏览器对结果进行二次全文扫描。

### More 动态条件

`More` 的字段清单从当前账号可见的 Jira 字段元数据生成，不在前端维护一份固定自定义字段表。

字段列表分为：

- 最近使用条件；
- 全部可查询条件；
- 当前已启用条件。

第一版支持以下字段控件类型：

- 单选与多选；
- 用户；
- 日期与日期范围；
- 文本；
- 数字；
- Version；
- Component。

无法可靠构建 Basic 条件的复杂字段仍出现在字段清单中，但标记为仅支持 Advanced JQL，不生成不完整或猜测性的条件。

字段名称、字段 ID、schema 和可选值由后端 Jira 过滤器服务统一返回。前端只根据声明的控件类型渲染，不理解 Jira 自定义字段业务。

## Advanced 模式

Advanced 模式显示：

- JQL 编辑框；
- Jira 校验状态；
- Search；
- Basic 切换入口。

Advanced 输入的 JQL 原文是权威查询。后端使用 Jira 能力校验，不在前端实现完整 JQL 解析器。

### Basic 与 Advanced 转换

- Basic 条件可以稳定生成 Advanced JQL。
- Advanced JQL 只有在能无损还原为已支持的 Basic 条件时才能切回 Basic。
- 包含 `OR`、`NOT`、`EMPTY`、不受支持的比较运算、复杂嵌套或仅 Advanced 支持字段时，保持 Advanced 模式并提示无法无损转换。
- 不能为了切换模式删除、重排或静默改写用户 JQL。
- 第一版只对 SmartTest Basic Builder 自己生成且未被手工改变的 JQL提供确定性回切；任意手写 JQL 不做猜测性解析。

## Jira Saved Filter

第一版提供只读 Saved Filter 选择入口：

1. 加载当前账号有权读取的 Jira Filter 候选；
2. 用户选择 Filter 后读取其 JQL；
3. 将该 JQL载入 Advanced 模式；
4. 用户点击 Search 后才应用，不因选中 Filter 自动启动全量查询。

SmartTest 不复制 Jira Filter 的共享、订阅、收藏和权限模型。保存 SmartTest 页面查询不等于修改 Jira Filter。

## 状态模型

每个账号分别维护：

- `draftMode`：当前 Basic 或 Advanced 编辑模式；
- `draftBasicConditions`：尚未应用的 Basic 控件值；
- `draftJql`：尚未应用的 Advanced 文本；
- `appliedJql`：最后一次通过 Jira 校验并成功应用的权威 JQL；
- `querySnapshotId`：SQLite 中当前有效查询快照标识；
- `sourceFilterId`：可选，只记录本次 JQL来源的 Jira Filter，不作为 Issue 权威范围。

重新进入页面时优先恢复最后一个有效数据库查询快照并原位展示。草稿与已应用状态视觉上必须可区分。账号切换或注销时清除浏览器中的上一账号草稿和展示 payload。

## Search 数据流

1. 用户编辑 Basic 条件或 Advanced JQL。
2. 点击 Search。
3. Basic 模式先在后端生成规范 JQL；Advanced 模式直接提交原始 JQL。
4. 后端调用 Jira 校验查询。
5. 校验失败时返回 Jira 错误信息，保留当前有效结果和未提交草稿。
6. 校验成功后更新当前账号、当前会话的 SQLite 查询快照。
7. 后端创建异步 Jira 全量查询任务。
8. `core/jira` 以 1000 条每页、Gateway 全局最多 4 并发获取 Issue，按 Key 去重。
9. 结果分批映射并写入 SQLite；浏览器不接收或保存十万级原始 Issue 集合。
10. 前端通过一条任务事件连接接收进度、失败或完成状态。
11. 完成后，Issue 明细分页和图表聚合都从 SQLite 快照读取。

同一账号发起新 Search 时，旧任务不得覆盖新查询快照。取消只终止运行时任务，不删除最后一次有效结果。

## API 与所有权

### `core/jira`

负责：

- Jira 字段元数据与候选值访问；
- Saved Filter 列表和 Filter JQL读取；
- JQL 校验与 Issue 搜索；
- Jira 第三方客户端异常规范化。

### Web 后端 Jira Analytics

负责：

- Basic 条件 schema；
- Basic 条件到 JQL 的确定性构建；
- 账号与会话查询快照；
- 异步任务、取消和进度；
- SQLite Issue 写入与快照查询。

### Web 前端

负责：

- Basic/Advanced 控件与切换；
- 草稿状态；
- 条件块、校验错误和任务进度展示；
- 不构建权威资源 ID，不分页抓取 Jira，不解析任意 JQL。

## 错误处理

- JQL 无效：显示 Jira 返回的校验错误，不清空有效结果。
- 字段或候选值无权限：从当前候选中移除并提示，不回退到全量权限。
- Filter 无权访问或已删除：保留已载入草稿，标记来源失效。
- Jira 网络或服务失败：任务失败但保留最后一次有效快照。
- 账号凭据明确失效：走既有统一 `invalid_credentials` 生命周期。
- 页面离开或刷新：后台任务可继续；重新进入时根据任务和 SQLite 状态恢复展示。

## 首版明确不包含

- 向 Jira 创建、覆盖、删除、共享、收藏或订阅 Saved Filter；
- 搬迁旧项目的图表级过滤器、浏览器全量 Issue 缓存或 `window.allIssueData`；
- 周期对比过滤器；
- 图表类型、统计维度和 Dashboard 卡片设计；
- 任意 JQL 的自研完整解析器；
- 在浏览器中按 Jira 分页请求并拼装全量结果。

## 验收标准

1. Basic 固定条件和 More 动态条件能够生成可由 Jira 校验的 JQL。
2. Basic 生成的 JQL 可切换到 Advanced，并在未修改时无损切回。
3. 不可表示的 Advanced JQL 不会丢失条件，并明确阻止无损回切。
4. Saved Filter 只读取 JQL，选择 Filter 不自动查询，也不修改 Jira Filter。
5. Search 只在校验成功后更新当前账号的 SQLite 查询快照。
6. 查询失败或取消时保留最后一次有效结果。
7. Browser 不通过分页 Web 请求收集 Jira Issue，图表和明细只查询 SQLite。
8. Jira Analytics 与 Tools 周审查过滤器互不影响。
9. 账号切换不会显示或复用其他账号的草稿、快照或结果。
10. 单元测试覆盖 JQL 构建、模式切换合同、字段 schema、Saved Filter 只读、账号隔离、任务竞态与错误保留；前端测试覆盖核心交互和无障碍名称。

