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

- Client 登录成功后，使用本次内存中的同一组 LDAP 账号密码调用 Web `/api/auth/login`，由套件 gateway 在内存 CookieJar 中保存 `smarttest_session`。
- Client 不额外显示 Web 登录框，也不把 Web Cookie、LDAP 密码写入 JSON、日志或报告。
- Web API 通过现有 `authenticated_session` 得到账户身份。
- Client 登出或切换账户时，调用 Web logout、清空 CookieJar、套件列表、active suite 和错误状态，再使用新账户建立 Web session。
- 会话失效返回统一的重新登录状态；不得静默使用上一次账户的数据。
- 自动建立 Web session 失败不影响手动选择和执行测试；套件区域显示未登录或服务不可用。
- `AuthBridge` 只向注入的 Python gateway 提供当前已认证的内存凭据，不通过 QML Property/Slot 暴露密码。

## 10. 代码位置

主要实现位置：

- `client/app/ui/example/imports/example/qml/page/T_TestConfig.qml`
- `client/app/ui/example/bridge/TestPageBridge.py`
- `client/app/test_suites/api_gateway.py` 新增测试套件 API gateway；当前 Client 没有可复用的 Web HTTP owner。
- `web/backend/smarttest_web/` 新增 `test_suite_repository.py`。
- `web/backend/smarttest_web/app.py` 按现有单应用结构注册 REST API，不另建并行应用。
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

## 14. 实施检查表

> 执行方式：Atlas + Mason。Mason 必须读取本设计、根 `AGENTS.md`、`smarttest-dual-codex-delivery`、`smarttest-ui-workflow`、`smarttest-testing-workflow` 和 `smarttest-logging-workflow`，不得委派。每项均执行 RED → GREEN → 清理；实际交付只保留耐久行为测试。

### 任务 1：Web 套件 repository

**文件：**

- 新建：`web/backend/smarttest_web/test_suite_repository.py`
- 新建：`web/backend/tests/test_test_suite_repository.py`
- 复用：`web/backend/smarttest_web/database.py::WebDatabase`

**接口：**

```python
@dataclass(frozen=True)
class TestSuiteRecord:
    id: str
    owner_username: str
    owner_display_name: str
    name: str
    description: str
    visibility: str
    ordered_nodeids: tuple[str, ...]
    revision: int
    created_at: float
    updated_at: float

class TestSuiteRepository:
    def __init__(self, database: WebDatabase, *, now=time.time): ...
    def list_mine(self, username: str) -> list[TestSuiteRecord]: ...
    def list_shared(self, username: str) -> list[TestSuiteRecord]: ...
    def get_visible(self, suite_id: str, username: str) -> TestSuiteRecord | None: ...
    def create(self, *, owner_username: str, owner_display_name: str,
               name: str, description: str, visibility: str,
               ordered_nodeids: Sequence[str]) -> TestSuiteRecord: ...
    def update(self, suite_id: str, *, owner_username: str, revision: int,
               name: str, description: str, visibility: str,
               ordered_nodeids: Sequence[str]) -> TestSuiteRecord | None: ...
    def delete(self, suite_id: str, *, owner_username: str) -> bool: ...
    def copy(self, suite_id: str, *, reader_username: str,
             owner_display_name: str, name: str,
             visibility: str = "private") -> TestSuiteRecord | None: ...
```

- [ ] 写 repository 失败测试：schema 初始化、持久化重开、账户内名称唯一、nodeid 去重保序、mine/shared 可见性、非 owner 更新/删除失败、revision 冲突、复制归属新 owner。
- [ ] 运行 `pytest web/backend/tests/test_test_suite_repository.py -q`，确认因 owner 不存在而 RED。
- [ ] 用 `WebDatabase.transaction()` 实现 schema 和 CRUD；不直接复用 `PersistentSessionStore` 的内部连接方法。
- [ ] 将名称冲突和 revision 冲突定义为 repository 专用异常，API 不解析 SQLite 错误字符串。
- [ ] 再次运行该测试，预期全部 PASS，并运行 `test_cache_schema.py`、`test_web_session.py` 防止共享数据库回归。

### 任务 2：Web REST API 与账户权限

**文件：**

- 修改：`web/backend/smarttest_web/app.py`
- 新建：`web/backend/tests/test_test_suite_api.py`
- 复用：`authenticated_session`、`WebDatabase`、`PersistentSessionStore`

**接口：**

```text
GET    /api/test-suites?scope=mine|shared
GET    /api/test-suites/{suite_id}
POST   /api/test-suites
PUT    /api/test-suites/{suite_id}
DELETE /api/test-suites/{suite_id}
POST   /api/test-suites/{suite_id}/copy
```

- [ ] 写 API 失败测试：未登录 401、owner 来自 session、私有跨账户 404、共享读取、共享原记录不可写、复制成功、名称冲突 409、revision 冲突 409、非法 visibility/nodeids 422。
- [ ] 运行 `pytest web/backend/tests/test_test_suite_api.py -q`，确认路由不存在而 RED。
- [ ] 在 `create_app()` 中创建一个 `TestSuiteRepository(cache_database)`，所有 handler 只做鉴权、输入归一化、repository 调用和 payload 映射。
- [ ] 列表 payload 不含 `orderedNodeids`；详情、创建、更新和复制 payload 包含有序 nodeid。
- [ ] 非 owner 读取私有记录、更新和删除统一返回 `404 not_found`；不得泄露资源存在性。
- [ ] 运行新 API 测试及 `web/backend/tests/test_api.py`、`test_web_session.py`，预期全部 PASS。

### 任务 3：Client Web 套件会话 gateway

**文件：**

- 新建：`client/app/test_suites/__init__.py`
- 新建：`client/app/test_suites/api_gateway.py`
- 修改：`client/app/ui/example/bridge/AuthBridge.py`
- 新建：`core/testing/self_tests/ui/test_test_suite_api_gateway.py`
- 复用：Python 标准库 `urllib.request`、`http.cookiejar.CookieJar`，不新增 HTTP 依赖。

**接口：**

```python
@dataclass(frozen=True)
class AuthenticatedCredentials:
    username: str
    password: str

class TestSuiteApiGateway:
    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0): ...
    def login(self, credentials: AuthenticatedCredentials) -> dict: ...
    def logout(self) -> None: ...
    def list_suites(self, scope: str) -> list[dict]: ...
    def get_suite(self, suite_id: str) -> dict: ...
    def create_suite(self, payload: dict) -> dict: ...
    def update_suite(self, suite_id: str, payload: dict) -> dict: ...
    def delete_suite(self, suite_id: str) -> None: ...
    def copy_suite(self, suite_id: str, payload: dict) -> dict: ...
```

- [ ] 写 gateway 失败测试：登录 Cookie 仅存内存、后续请求携带 Cookie、401 映射为 `authentication_required`、409/422/503 映射稳定错误码、日志/异常不包含密码或 Cookie。
- [ ] 写 `AuthBridge.authenticated_credentials()` 失败测试：仅已认证时返回 Python dataclass；方法不得声明为 QML Slot/Property。
- [ ] 运行两个测试并确认 RED。
- [ ] 使用标准库 opener + CookieJar 实现单一 HTTP owner；base URL 只从 `SMARTTEST_WEB_BASE_URL` 读取，未配置时返回 `service_unavailable`，不在代码中硬编码部署地址。正式环境使用 HTTPS，保证 Web 返回的 Secure session Cookie 可被 CookieJar 发送。
- [ ] AuthBridge 登录成功、退出和切换账户只发出现有 `authChanged`；gateway 生命周期由 TestPageBridge 响应该信号，不向 QML 传递凭据。
- [ ] 运行 gateway、AuthBridge 和日志脱敏测试，预期全部 PASS。

### 任务 4：Bridge 套件异步状态与加载语义

**文件：**

- 修改：`client/app/ui/example/main.py`
- 修改：`client/app/ui/example/bridge/TestPageBridge.py`
- 新建：`core/testing/self_tests/ui/test_test_page_suites.py`

**组装：**

```python
auth_bridge = AuthBridge()
suite_gateway = TestSuiteApiGateway(web_base_url())
test_page_bridge = TestPageBridge(
    runtime_root,
    auth_bridge=auth_bridge,
    suite_gateway=suite_gateway,
)
```

**Bridge API：**

```text
Properties: suitePanelLoading, suiteRefreshRunning, suiteActionRunning,
            suiteActionKind, suiteError, suiteScope, activeSuiteId,
            activeSuiteRevision
Slots: refreshSuites(), setSuiteScope(scope), loadSuite(id),
       createSuite(name, description, visibility),
       updateActiveSuite(name, description, visibility),
       deleteSuite(id), copySuite(id, name, visibility)
Models: suiteRows()
```

- [ ] 写失败测试：认证后自动登录 Web 并加载 mine；切换账户先清空旧状态和 Cookie；未登录/服务失败不影响当前用例选择；列表读取与 discovery 并行；写操作互斥。
- [ ] 写加载失败测试：替换而非合并、按 `orderedNodeids` 保序、失效 nodeid 被报告、只保存/emit/上下文刷新一次、共享加载不设置可更新权限。
- [ ] 运行 `test_test_page_suites.py` 并确认 RED。
- [ ] 在 main 中显式注入 AuthBridge 和 gateway；不得从 QML 或全局单例查找密码。
- [ ] 复用现有 Qt/async task adapter 执行网络调用；不得阻塞 GUI 线程或新增线程管理器。
- [ ] 实现成功、错误和重试状态；错误保留最后成功列表。
- [ ] 运行新测试及现有 TestPageBridge、参数映射、异步反馈测试，预期全部 PASS。

### 任务 5：目录三态选择

**文件：**

- 修改：`client/app/ui/example/bridge/TestPageBridge.py`
- 新建或扩展：`core/testing/self_tests/ui/test_test_page_case_tree.py`

- [ ] 写失败测试：叶子全未选/全选/部分选择对应目录状态；状态向祖先聚合；过滤时批量操作仅影响可见后代；取消不打乱其他选择；全选按发现顺序。
- [ ] 写行为计数测试：一次目录操作只调用一次 state save、一次 UI emit 和一次 context refresh。
- [ ] 运行测试确认当前目录节点无三态能力而 RED。
- [ ] 扩展 `caseTree()` 返回 `selectionState/selectableCount/selectedCount`，复用当前 `_cases`、`_set_case_selected()` 和 `_save_and_emit()`。
- [ ] 实现 `setTreeNodeSelected(node_key, selected, filter_text)` 与 `clearSelectedCases()`；不得让 QML传 nodeid 列表。
- [ ] 运行树测试和现有单文件选择/Selected 排序测试，预期全部 PASS。

### 任务 6：QML 套件布局与交互

**文件：**

- 修改：`client/app/ui/example/imports/example/qml/page/T_TestConfig.qml`
- 修改：`client/app/ui/example/example_en_US.ts`
- 修改：`client/app/ui/example/example_zh_CN.ts`
- 修改：`client/app/ui/example/imports/resource.qrc`（仅在新增独立 QML 组件时）
- 新建或扩展：`core/testing/self_tests/ui/test_test_suite_ui.py`

- [ ] 写失败测试：我的/共享页签、刷新、保存、加载、另存、更新、删除、私有/共享、空状态、错误重试和 loading 状态均可由 Bridge 状态驱动。
- [ ] 写目录节点交互测试：展开箭头不选择；勾选调用 `setTreeNodeSelected`；partial 使用 FluentUI 三态视觉。
- [ ] 运行 UI 测试确认 RED。
- [ ] 在 Test Cases 上方实现可折叠套件区域；复用 `AppLoadingIndicator`/`AppTaskProgress`，不新增页面级 loading 机制。
- [ ] 保存/另存对话框只提交名称、说明、visibility；更新当前套件必须由显式按钮触发。
- [ ] 删除前显示确认对话框；共享套件不显示修改/删除入口。
- [ ] 固定文本同时更新中英文 TS；外部作者名、套件名和 nodeid 保持原文。
- [ ] 运行 UI、翻译和 QRC 测试，重新生成 `resource_rc.py`，预期全部 PASS。

### 任务 7：跨层验收与交付清理

- [ ] 启动隔离 Web 测试服务，用两个账户完成：创建私有、跨账户不可见、切换共享、跨账户加载、复制、原作者更新不影响副本。
- [ ] 从 Client 源码登录同一 LDAP 账户，验证自动 Web session、套件 loading、目录全选、保存、重启 Client 后重新加载。
- [ ] 验证 Web 不可用时仍可手动选择并运行测试，套件区域给出可恢复错误。
- [ ] 运行 Web backend 全量测试、相关 Client/UI/self-tests、pytest collect、compileall、翻译/QRC 校验和 bounded source startup。
- [ ] 搜索并移除 `TEMP_DIAGNOSTIC`、临时 print、密码/Cookie 输出、重复 helper、source-shape 探针和被放弃的兼容路径。
- [ ] 执行 `git diff --check`，按 Web repository/API、Client gateway/Bridge、QML 交互三个业务结果形成原子提交。
- [ ] Atlas 从 status、stat、scoped diff、测试证据和最高实际环境验证完成 Functional Acceptance 与 Code Quality 双门禁。
