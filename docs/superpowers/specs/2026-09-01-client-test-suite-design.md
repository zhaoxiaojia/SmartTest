# Client 测试套件与模块批量选择设计

## 1. 目标

在 SmartTest Client 的 Test 页面增加两项能力：

1. 保留现有测试目录树，并支持按任意目录层级一键选择、取消及显示半选状态。
2. 用户可将当前有序用例集合保存为账户关联的测试套件；套件保存到 SmartTest Web 的 SQLite，支持私有、共享、加载和复制。

第一阶段只保存用例身份与执行顺序，不保存用例参数、DUT、环境设备、凭据、展开状态或测试结果。

## 2. 范围

### 2.1 包含

- Client Test 页面中的目录三态选择。
- 我的套件和共享套件布局。
- 套件列表、详情、创建、更新、删除、复制 API。
- Web 会话鉴权、账户归属和可见性控制。
- SQLite 持久化与 schema migration。
- Client 异步 loading、错误、重试和失效用例提示。
- 中英文固定文本与相关耐久测试。

### 2.2 不包含

- 保存用例参数、DUT serial、Wi-Fi 密码或环境配置。
- 多人共同编辑同一个套件。
- 离线套件、本地 JSON 副本或双向同步。
- 套件版本历史、审批、标签、收藏和分页。
- 加载时合并当前选择。
- Web 前端套件管理页面。

## 3. 方案与 owner

采用：

```text
Client QML
  -> TestPageBridge
    -> TestSuiteApiGateway
      -> SmartTest Web REST API
        -> TestSuiteRepository
          -> SQLite
```

- QML 只展示状态并转发操作。
- `TestPageBridge` 拥有目录选择关系、当前套件视图状态和异步操作编排。
- Client 套件 gateway 是唯一 HTTP 边界，负责请求、会话携带及错误映射。
- Web API 负责鉴权、输入校验和权限判定。
- `TestSuiteRepository` 是套件持久化 owner。
- SQLite 是套件唯一持久化事实源；Client 不建立套件本地数据库或 JSON 缓存。

## 4. Client 页面设计

### 4.1 页面结构

Test Cases 区域调整为：

```text
┌ Test Suites ────────────────────────────────────┐
│ [我的套件] [共享套件]              [刷新]       │
│ [搜索套件……]                                   │
│                                                │
│ 中屏基础测试   29 条   Coco    2026-09-01      │
│ IPTV 冒烟测试  12 条   Zhang   2026-08-31      │
│                                                │
│ [加载] [另存为我的套件]                        │
└────────────────────────────────────────────────┘

┌ Current Selection ─────────────────────────────┐
│ [保存当前套件] [清空选择]                      │
│ [筛选用例……]                                  │
│ ☑ tests                                       │
│   ◩ android                                   │
│     ☑ common                                  │
│       ☑ iptv                                  │
│       ☐ system                                │
└────────────────────────────────────────────────┘
```

套件区域默认折叠，用户展开后可调整其与测试树之间的高度。展开状态属于前端显示偏好，可由 `FrontendStateStore` 保存；套件数据不得进入该 store。

### 4.2 套件列表

使用两个页签：

- `我的套件`：当前账户创建的私有和共享套件。
- `共享套件`：其他账户主动共享的套件，不包含当前账户套件。

每行显示：

- 名称。
- 用例数量。
- 创建者显示名。
- 私有/共享标识。
- 更新时间。

我的套件操作：加载、更新、重命名、切换可见性、删除。

共享套件操作：加载、另存为我的套件。不得显示更新或删除入口。

### 4.3 Loading 与错误

复用现有公共异步反馈组件：

- 首次加载：套件区域显示 `AppLoadingIndicator` 或等高骨架列表。
- 后续刷新：保留旧列表，在标题区域显示非阻塞 loading。
- 创建、更新、删除、复制：仅锁定相关操作按钮，显示动作状态。
- 请求失败：保留最后成功列表，显示错误摘要和重试按钮。
- 未登录：显示“请先登录 SmartTest Web”，不回退到本地保存。
- 空列表：分别显示“还没有我的套件”和“暂无共享套件”。

同一时刻只允许一个套件写操作；列表读取可在写操作完成后自动刷新一次。

## 5. 目录三态批量选择

### 5.1 状态

每个目录节点由其当前后代用例计算：

- `unchecked`：没有后代用例被选中。
- `checked`：全部后代用例被选中。
- `partial`：部分后代用例被选中。

文件节点继续使用当前选中状态。目录状态不持久化，也不创建第二套选择模型。

### 5.2 操作规则

- 点击展开箭头只展开或收起。
- 点击目录勾选框，原子选择或取消其目标后代用例。
- 根节点支持全选和取消全部。
- 无筛选时，目标是该目录全部后代用例。
- 有筛选时，目标仅为当前筛选结果中可见的后代用例。
- 批量操作保留测试发现顺序；取消只移除目标，不改变其余用例顺序。
- 一次批量操作只保存一次状态、发射一次 UI 更新，并按最终选择触发一次参数/DUT 上下文刷新。

### 5.3 Bridge 接口

`caseTree(...)` 的目录节点增加：

```text
selectionState: unchecked | partial | checked
selectableCount: int
selectedCount: int
```

新增 Bridge 操作：

```text
setTreeNodeSelected(node_key, selected, filter_text)
clearSelectedCases()
```

Bridge 根据 `node_key` 和当前发现结果解析 nodeid；QML 不遍历或推断后代关系。

## 6. 套件数据模型

SQLite 新增 `test_suites`：

```sql
CREATE TABLE test_suites (
    id TEXT PRIMARY KEY,
    owner_username TEXT NOT NULL,
    owner_display_name TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'shared')),
    ordered_nodeids_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (owner_username, name)
);

CREATE INDEX ix_test_suites_visibility_updated
ON test_suites(visibility, updated_at DESC);
```

约束：

- `id` 由服务端生成。
- `owner_username` 和 `owner_display_name` 来自认证会话，不能由 Client 指定。
- `name` 去除首尾空格后不能为空；同一账户内唯一。
- `ordered_nodeids_json` 是非空、去重、保持顺序的字符串数组。
- `revision` 每次更新递增，用于检测多端覆盖。
- 删除为物理删除；第一阶段不提供恢复站。

数据库 migration 沿用现有 Web schema owner，不创建第二个数据库文件。

## 7. Web API

### 7.1 列表

```http
GET /api/test-suites?scope=mine
GET /api/test-suites?scope=shared
```

- `mine`：`owner_username == 当前账户`。
- `shared`：`visibility == shared` 且 owner 不是当前账户。
- 第一阶段按 `updated_at DESC` 返回全部记录。
- 列表只返回摘要，不返回 `orderedNodeids`。

### 7.2 详情

```http
GET /api/test-suites/{suite_id}
```

当前账户可读取自己的全部套件和其他账户的共享套件。无权限与不存在统一返回 `404`，避免泄露私有资源身份。

### 7.3 创建

```http
POST /api/test-suites
```

请求：

```json
{
  "name": "中屏基础测试",
  "description": "中屏软件自动化检查",
  "visibility": "private",
  "orderedNodeids": ["testing/tests/...::test_..."]
}
```

### 7.4 更新

```http
PUT /api/test-suites/{suite_id}
```

仅 owner 可更新。请求包含当前 `revision`；不一致返回 `409 revision_conflict`，Client 提示刷新后重试，不自动覆盖。

### 7.5 删除

```http
DELETE /api/test-suites/{suite_id}
```

仅 owner 可删除；Client 必须显示确认对话框。

### 7.6 复制

```http
POST /api/test-suites/{suite_id}/copy
```

只允许复制可读取的套件。服务端创建属于当前账户的新记录；Client 提交新名称和可见性，不能继承原 owner。默认复制为私有。

## 8. Client 状态与数据流

### 8.1 状态

Bridge 对 QML 暴露：

```text
suitePanelLoading
suiteRefreshRunning
suiteActionRunning
suiteActionKind
suiteError
suiteScope
suiteSearchText
mySuites
sharedSuites
activeSuiteId
activeSuiteRevision
```

套件列表是 Web 数据的短期显示镜像，只存在于进程内存，不持久化。

### 8.2 页面进入

1. 用例发现与套件列表加载并行执行。
2. 套件列表可先显示，但在用例发现完成前禁用“加载”。
3. 用例发现失败不影响查看套件列表；套件 API 失败不影响手动选择和执行用例。

### 8.3 保存当前选择

1. 用户点击“保存当前套件”。
2. 弹窗填写名称、说明和是否共享。
3. Bridge 读取当前有序 nodeid。
4. 空选择阻止提交并明确提示。
5. Web 创建成功后刷新“我的套件”并选中新记录。

### 8.4 更新自己的套件

更新只在用户明确点击“更新套件”时发生。加载某套件后继续增删用例，不自动写回 Web。

### 8.5 加载套件

加载采用替换语义：

1. 获取套件详情。
2. 用当前 discovery 结果解析 `orderedNodeids`。
3. 按套件顺序保留仍存在的 nodeid。
4. 原子替换当前选择并保存现有 Test 页面状态。
5. 一次性刷新树、Selected、参数和 DUT/环境上下文。
6. 若存在失效 nodeid，加载有效部分并显示失效数量和原始 nodeid；不得猜测替代用例。

加载共享套件不会自动复制，也不会获得更新权限。

## 9. 账户和会话

- Client gateway 必须复用 SmartTest Web 已有登录会话，不单独传 `owner_username`。
- Web API 通过现有 `authenticated_session` 得到账户身份。
- Client 登出或切换账户时，清空进程内套件列表、active suite 和错误状态，再为新账户加载。
- 会话失效返回统一的重新登录状态；不得静默使用上一次账户的数据。

如果当前 Client 尚无可复用 Web session transport，实施前必须复用现有 Web 登录/会话机制；不得以 Client 本地账户 ID 代替服务端鉴权。

## 10. 代码位置

主要实现位置：

- `client/app/ui/example/imports/example/qml/page/T_TestConfig.qml`
- `client/app/ui/example/bridge/TestPageBridge.py`
- Client 中新增测试套件 API gateway，放入现有 Client HTTP/service owner；若调查确认不存在该 owner，再新增单一 gateway 文件。
- `web/backend/smarttest_web/` 新增 `test_suite_repository.py`。
- `web/backend/smarttest_web/app.py` 注册 REST API；若现有路由拆分机制已存在则按该机制注册，不另建并行应用。
- Web SQLite migration owner。
- `client/app/ui/example/example_en_US.ts`
- `client/app/ui/example/example_zh_CN.ts`

不得把套件数据库操作放入 QML、Bridge 或 `core/testing/state`；现有 `TestPageState` 继续只保存当前工作选择与参数。

## 11. 错误规则

稳定错误状态至少包含：

- `authentication_required`
- `invalid_input`
- `name_conflict`
- `not_found`
- `revision_conflict`
- `service_unavailable`

外部错误文本不进入翻译；固定提示由 Client 根据错误码显示本地化文本。日志不得记录会话 token 或凭据。

## 12. 测试与验收

### 12.1 树选择

- 目录全选、取消和半选。
- 多层目录状态向上聚合。
- 搜索状态只操作可见后代。
- 批量选择保持发现顺序。
- 一次批量操作只保存和刷新一次。

### 12.2 Repository 与 API

- 创建、列表、详情、更新、删除和复制。
- 同账户名称唯一。
- 私有套件对其他账户不可见。
- 共享套件可读、可复制但不可更新或删除。
- owner 字段不能由请求伪造。
- revision 冲突不会覆盖新数据。
- 服务重启后套件仍存在。

### 12.3 Client

- 页面进入并行加载。
- 首次 loading、后台刷新、空状态、错误和重试。
- 保存、另存、更新和删除按钮状态。
- 加载替换当前选择并保持顺序。
- 失效 nodeid 明确提示。
- 切换账户清理旧账户套件状态。
- 套件 payload 不包含参数、DUT、环境和凭据。

### 12.4 回归

- 现有单文件选择、Selected 排序、参数映射和运行链路保持不变。
- 用例发现失败仍可正确展示错误。
- Web 不可用时仍可手动选择并执行测试，但不能保存或加载套件。
- 运行 Client 源码验证和 Web API 测试；不以静态 source-shape 断言替代行为测试。

## 13. 交付顺序

1. Web 数据模型、migration、repository 和权限测试。
2. Web REST API 与契约测试。
3. Client gateway 和异步状态测试。
4. 目录三态选择及批量操作。
5. Test 页面套件布局、loading 和交互。
6. 端到端源码验证、清理和交付审查。

实施属于跨 Client、Web、SQLite 和账户权限的中高风险改动，采用 Atlas + Mason。真实 Web 会话集成是最高实际验收边界；无法使用真实环境时必须明确说明，不能以 mock 结果代表端到端通过。
