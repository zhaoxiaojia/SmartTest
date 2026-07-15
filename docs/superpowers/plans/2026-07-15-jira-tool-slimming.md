# SmartTest 内部 Jira 封装瘦身实施计划

> **面向执行代理：** 必须使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`，逐任务执行本计划；使用复选框记录进度。

**目标：** 在保持现有 Jira 页面行为和配置兼容的前提下，消除 `JiraWorkspaceService` 对 `JiraIssueService` 私有成员的访问，拆分过大的工作区服务，并让 `JiraBridge` 只承担 UI 适配职责。

**架构：** 保留 `JiraWorkspaceService` 作为 Bridge 使用的兼容门面，内部委托给独立的浏览服务和分析服务。`JiraIssueService` 提供公开的分页、字段计划和收藏筛选器能力，所有网络访问仍由 `JiraClient` 完成。使用请求数据类收拢 Bridge 到 Service 的长参数列表，不实现 Create Jira、Tool 页面或 Bug Clone。

**技术栈：** Python 3.10、PySide6/QObject、pytest、现有 `jira_tool` REST/字段/SQLite 缓存组件。

## 全局约束

- 不实现 Tool 页面、Bug Clone、客户系统适配器或创建 Jira。
- 不改变 QML 公共属性、Signal、Slot、页面文字及用户可见行为。
- 不改变现有 Jira 配置和缓存格式。
- `JiraClient` 保持唯一 Jira REST 请求出口。
- 不增加 `Connector`、`Provider`、`Repository` 或插件抽象。
- 开始前记录 `git status`；只修改本计划明确列出的文件，保留所有用户已有改动。
- 每个任务先写失败测试，再做最小实现；提交必须只包含该任务文件，Mason 不 push。

---

## 文件结构决策

### 新增

- `jira_tool/services/requests.py`：浏览和分析请求的不可变数据合同。
- `jira_tool/services/browse_service.py`：收藏筛选器、分页浏览和 Issue 详情业务。
- `jira_tool/services/analysis_service.py`：AI/MCP 分析、自然语言搜索和分析辅助函数。
- `testing/self_tests/jira_tool/test_issue_service_boundary.py`：Issue Service 公共边界测试。
- `testing/self_tests/jira_tool/test_workspace_services.py`：浏览、分析及兼容门面的行为测试。
- `testing/self_tests/ui/test_jira_bridge_service_boundary.py`：Bridge 不越过应用服务边界的结构测试。

### 修改

- `jira_tool/services/issue_service.py`：增加公开字段计划、分页查询和收藏筛选器方法。
- `jira_tool/services/workspace.py`：缩减为兼容门面，只委托浏览及分析服务。
- `jira_tool/services/factory.py`：集中装配 Client、Issue Service、Browse Service、Analysis Service 和 Workspace 门面。
- `jira_tool/services/__init__.py`：仅导出稳定公共服务和请求合同。
- `ui/example/bridge/JiraBridge.py`：构造请求对象并调用 Workspace 门面，不再导入 JQL 解析工具。
- `jira_tool/README.md`：用中文记录最终所有权和扩展入口。

### 保留，不在本次拆分

- `jira_tool/services/query_builder.py`：继续作为纯 JQL 构建所有者。
- `jira_tool/services/payloads.py`：继续组装稳定的 Bridge 返回字典。
- `jira_tool/services/presenter.py`：继续负责 `IssueRecord` 到 UI 行数据转换。
- `jira_tool/services/specs.py`：继续声明浏览和详情字段集合。
- `jira_tool/fields/**`、`jira_tool/cache/**`、`jira_tool/transport/client.py`：保持现有职责和存储格式。

---

### 任务 1：建立 Issue Service 的公开能力边界

**文件：**

- 新增：`testing/self_tests/jira_tool/test_issue_service_boundary.py`
- 修改：`jira_tool/services/issue_service.py`

**接口：**

- 输入：现有 `JiraClient`、`FieldRegistry`、`FieldSpec`。
- 输出：
  - `JiraIssueService.build_fetch_plan(specs, *, include_heavy=False) -> FieldFetchPlan`
  - `JiraIssueService.search_page_records(jql, *, specs, start_at, max_results, include_heavy=False) -> tuple[SearchPage, list[IssueRecord]]`
  - `JiraIssueService.fetch_favourite_filters() -> list[dict[str, Any]]`

- [ ] **步骤 1：编写公开边界失败测试**

测试使用记录调用参数的假 Client，验证字段计划、分页查询和收藏筛选器均通过 `JiraIssueService`，且分页结果转换为 `IssueRecord`：

```python
from jira_tool.core.models import SearchPage
from jira_tool.fields.registry import build_default_registry
from jira_tool.services.issue_service import JiraIssueService
from jira_tool.services.specs import browse_specs


class FakeClient:
    def __init__(self):
        self.search_calls = []

    def search_page(self, jql, **kwargs):
        self.search_calls.append((jql, kwargs))
        return SearchPage(
            issues=[{"id": "1", "key": "TV-1", "fields": {"summary": "Black screen"}}],
            start_at=0,
            max_results=25,
            total=1,
        )

    def fetch_favourite_filters(self):
        return [{"id": "7", "name": "My Bugs", "jql": "assignee = currentUser()"}]


def test_issue_service_owns_page_projection_and_saved_filter_transport():
    client = FakeClient()
    service = JiraIssueService(client, registry=build_default_registry())

    page, records = service.search_page_records(
        "project = TV",
        specs=browse_specs(),
        start_at=0,
        max_results=25,
    )

    assert page.total == 1
    assert records[0].key == "TV-1"
    assert client.search_calls[0][0] == "project = TV"
    assert "summary" in client.search_calls[0][1]["fields"]
    assert service.fetch_favourite_filters()[0]["id"] == "7"
```

- [ ] **步骤 2：运行测试并确认失败**

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool/test_issue_service_boundary.py -q
```

预期：失败，提示 `JiraIssueService` 尚无 `search_page_records`。

- [ ] **步骤 3：实现最小公开接口**

在 `JiraIssueService` 中增加公开方法；内部继续复用现有 registry 和 `_to_record`，不得暴露 `_client` 或 `_registry`：

```python
def build_fetch_plan(self, specs, *, include_heavy=False):
    return self._registry.build_plan(specs, include_heavy=include_heavy)

def search_page_records(self, jql, *, specs, start_at, max_results, include_heavy=False):
    plan = self.build_fetch_plan(specs, include_heavy=include_heavy)
    page = self._client.search_page(
        jql,
        start_at=start_at,
        max_results=max_results,
        fields=list(plan.jira_fields),
        expand=list(plan.expand) or None,
    )
    records = [self._to_record(issue, list(plan.active_specs)) for issue in page.issues]
    return page, records

def fetch_favourite_filters(self):
    return self._client.fetch_favourite_filters()
```

- [ ] **步骤 4：运行聚焦测试**

运行同一步骤 2。预期：全部通过。

- [ ] **步骤 5：提交任务 1**

```powershell
git add jira_tool/services/issue_service.py testing/self_tests/jira_tool/test_issue_service_boundary.py
git commit -m "refactor: expose Jira issue service boundaries"
```

---

### 任务 2：引入请求合同并拆分浏览服务

**文件：**

- 新增：`jira_tool/services/requests.py`
- 新增：`jira_tool/services/browse_service.py`
- 新增：`testing/self_tests/jira_tool/test_workspace_services.py`
- 修改：`jira_tool/services/workspace.py`

**接口：**

- 输出：`JiraBrowseRequest`、`JiraAnalysisRequest`，字段名与现有 `browse()`、`analyze()` 参数一一对应。
- 输出：`JiraBrowseService.fetch_saved_filters()`、`browse(request)`、`fetch_issue_detail(...)`。
- 输出：`JiraWorkspaceService` 保留现有公共方法签名，内部构造请求并委托，确保 Bridge 暂不受影响。

- [ ] **步骤 1：编写浏览服务失败测试**

用 Fake Issue Service 验证浏览服务只调用公开方法，不读取 `_client`、`_registry`：

```python
def test_browse_service_uses_public_issue_service_boundary():
    issue_service = FakeIssueService()
    service = JiraBrowseService(base_url="https://jira.example", issue_service=issue_service)
    result = service.browse(make_browse_request())

    assert issue_service.page_calls == [("project = TV", 0, 25)]
    assert result["mode"] == "browse"
    assert result["issues"][0]["keyId"] == "TV-1"


def test_saved_filters_are_normalized_without_private_client_access():
    issue_service = FakeIssueService()
    service = JiraBrowseService(base_url="https://jira.example", issue_service=issue_service)

    assert service.fetch_saved_filters() == [
        {"id": "7", "name": "My Bugs", "jql": "assignee = currentUser()"}
    ]
```

测试辅助对象必须实现明确的 `build_fetch_plan`、`search_page_records`、`fetch_favourite_filters` 和 `hydrate_issue`；不要使用 `MagicMock` 隐藏接口拼写错误。

- [ ] **步骤 2：运行浏览服务测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool/test_workspace_services.py -q
```

预期：导入失败，因为 `requests.py` 和 `browse_service.py` 尚不存在。

- [ ] **步骤 3：增加不可变请求数据类**

使用 `@dataclass(frozen=True, slots=True)` 定义请求。公共字段使用现有参数名称，不改默认值语义：

```python
@dataclass(frozen=True, slots=True)
class JiraBrowseRequest:
    worker_id: int
    selected_issue_index: int
    raw_jql_text: str
    project_ids_csv: str
    board_id: str
    board_label: str
    timeframe_id: str
    timeframe_label: str
    status_ids_csv: str
    priority_ids_csv: str
    issue_type_ids_csv: str
    keyword_text: str
    assignee_text: str
    reporter_text: str
    labels_text: str
    include_comments: bool
    include_links: bool
    only_mine: bool
    start_at: int
    append: bool
    translated_state: Callable[..., dict[str, Any]]
```

`JiraAnalysisRequest` 使用以下完整合同，不新增业务概念：

```python
@dataclass(frozen=True, slots=True)
class JiraAnalysisRequest:
    worker_id: int
    raw_jql_text: str
    project_ids_csv: str
    board_id: str
    board_label: str
    timeframe_id: str
    timeframe_label: str
    status_ids_csv: str
    priority_ids_csv: str
    issue_type_ids_csv: str
    keyword_text: str
    assignee_text: str
    reporter_text: str
    labels_text: str
    include_comments: bool
    include_links: bool
    only_mine: bool
    include_user_message: bool
    prompt: str
    translated_state: Callable[..., dict[str, Any]]
    raw_state: Callable[[str], dict[str, Any]]
    assistant_timestamp: str
```

- [ ] **步骤 4：迁移浏览和详情逻辑**

把当前 `workspace.py` 中以下职责原样迁入 `JiraBrowseService`：

- `fetch_saved_filters` 及 `_normalize_saved_filters`；
- `browse`；
- `fetch_issue_detail`。

`browse` 使用任务 1 的 `search_page_records`，禁止访问 `issue_service._client` 或 `issue_service._registry`。结果继续由 `payloads.py` 和 `presenter.py` 生成。

- [ ] **步骤 5：保留兼容门面**

`JiraWorkspaceService` 暂时保留原 `fetch_saved_filters`、`browse` 和 `fetch_issue_detail` 方法签名，方法体只构造请求对象并委托 `JiraBrowseService`。这样任务 2 不修改 Bridge，形成可独立验收的提交。

- [ ] **步骤 6：运行任务 1 和任务 2 测试**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool/test_issue_service_boundary.py testing/self_tests/jira_tool/test_workspace_services.py -q
```

预期：全部通过；测试不得发起真实网络请求。

- [ ] **步骤 7：提交任务 2**

```powershell
git add jira_tool/services/requests.py jira_tool/services/browse_service.py jira_tool/services/workspace.py testing/self_tests/jira_tool/test_workspace_services.py
git commit -m "refactor: split Jira browse service"
```

---

### 任务 3：拆分分析服务并把 Workspace 缩减为门面

**文件：**

- 新增：`jira_tool/services/analysis_service.py`
- 修改：`jira_tool/services/workspace.py`
- 修改：`testing/self_tests/jira_tool/test_workspace_services.py`

**接口：**

- 输出：`JiraAnalysisService.analyze(request: JiraAnalysisRequest) -> dict[str, Any]`。
- 保留：`JiraWorkspaceService.analyze(...) -> dict[str, Any]` 的原公共签名和结果结构。

- [ ] **步骤 1：增加分析委托失败测试**

```python
def test_workspace_facade_delegates_analysis_without_rebuilding_business_logic():
    analysis = RecordingAnalysisService(result={"mode": "analyze", "worker_id": 9})
    workspace = JiraWorkspaceService(browse_service=RecordingBrowseService(), analysis_service=analysis)

    result = workspace.analyze(**analysis_arguments(worker_id=9))

    assert result == {"mode": "analyze", "worker_id": 9}
    assert analysis.requests[0].prompt == "summarize blockers"
    assert analysis.requests[0].project_ids_csv == "TV"
```

- [ ] **步骤 2：运行测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool/test_workspace_services.py -q
```

预期：失败，因为 Workspace 尚不能接收独立的 `analysis_service`。

- [ ] **步骤 3：迁移分析实现**

将当前 `workspace.py` 中 `analyze`、MCP 上下文、自然语言条件生成、JQL 放宽重试、AI 回退文本及其纯辅助函数迁入 `analysis_service.py`。迁移要求：

- 算法和返回字典不变；
- 继续复用 `query_builder.py`、`payloads.py`、`presenter.py` 和 `JiraIssueService`；
- 不把 AI/MCP 逻辑移动到 Bridge；
- 不引入新的通用 AI 抽象；
- 所有 Issue 获取通过 `JiraIssueService` 公开方法。

- [ ] **步骤 4：将 Workspace 缩减为兼容门面**

`workspace.py` 仅保留构造函数以及四个委托入口：

```python
class JiraWorkspaceService:
    def __init__(self, *, browse_service, analysis_service):
        self._browse_service = browse_service
        self._analysis_service = analysis_service

    def fetch_saved_filters(self):
        return self._browse_service.fetch_saved_filters()

    def browse(self, **kwargs):
        return self._browse_service.browse(JiraBrowseRequest(**kwargs))

    def fetch_issue_detail(self, **kwargs):
        return self._browse_service.fetch_issue_detail(**kwargs)

    def analyze(self, **kwargs):
        return self._analysis_service.analyze(JiraAnalysisRequest(**kwargs))
```

如果现有调用使用显式关键字签名，保留显式参数并在方法内部构造数据类，不用 `**kwargs` 弱化接口。

- [ ] **步骤 5：运行聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool/test_issue_service_boundary.py testing/self_tests/jira_tool/test_workspace_services.py -q
```

预期：全部通过，且 `workspace.py` 不再包含 MCP、自然语言解析或 JQL 辅助函数。

- [ ] **步骤 6：提交任务 3**

```powershell
git add jira_tool/services/analysis_service.py jira_tool/services/workspace.py testing/self_tests/jira_tool/test_workspace_services.py
git commit -m "refactor: split Jira analysis service"
```

---

### 任务 4：集中装配并收紧 JiraBridge 边界

**文件：**

- 修改：`jira_tool/services/factory.py`
- 修改：`jira_tool/services/__init__.py`
- 修改：`ui/example/bridge/JiraBridge.py`
- 新增：`testing/self_tests/ui/test_jira_bridge_service_boundary.py`

**接口：**

- 保留：`create_jira_workspace_service(...) -> JiraWorkspaceService`。
- 保留：Jira QML 使用的全部 Bridge Property、Signal 和 Slot。
- Bridge 只导入 `create_jira_workspace_service` 和 `JiraWorkspaceService`，不导入 `transport`、`cache`、`fields` 或 `query_builder`。

- [ ] **步骤 1：编写 Bridge 边界失败测试**

使用 AST 而非字符串误判注释，验证 Bridge 不导入 Jira 内部实现：

```python
import ast
from pathlib import Path


def test_jira_bridge_only_imports_jira_application_boundary():
    path = Path("ui/example/bridge/JiraBridge.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("jira_tool")
    }

    assert imported <= {"jira_tool.services"}
```

再增加一个契约测试，实例化带 Fake AuthBridge 和 Fake Workspace 的 Bridge，确认 `refreshScope`、`loadMore`、`selectIssue` 和 `submitPrompt` 仍调用 Workspace 公共入口，不访问 Client。

- [ ] **步骤 2：运行 Bridge 测试并确认失败**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_jira_bridge_service_boundary.py -q
```

预期：AST 测试失败，因为 Bridge 当前直接导入 `jira_tool.services.query_builder` 和具体模块。

- [ ] **步骤 3：更新 Factory 装配**

`factory.py` 依次创建：

```text
JiraBasicAuth
  -> JiraClient
  -> JiraFieldMetadataCache / FieldRegistry
  -> JiraIssueService
  -> JiraBrowseService
  -> JiraAnalysisService
  -> JiraWorkspaceService
```

保留现有 factory 参数、默认值、MCP Service 创建方式及元数据缓存路径。

- [ ] **步骤 4：建立稳定 Service 导出面**

在 `jira_tool/services/__init__.py` 仅导出：

```python
from jira_tool.services.factory import create_jira_workspace_service
from jira_tool.services.requests import JiraAnalysisRequest, JiraBrowseRequest
from jira_tool.services.workspace import JiraWorkspaceService

__all__ = [
    "JiraAnalysisRequest",
    "JiraBrowseRequest",
    "JiraWorkspaceService",
    "create_jira_workspace_service",
]
```

- [ ] **步骤 5：收紧 Bridge 导入和调用**

Bridge 改为从 `jira_tool.services` 稳定出口导入。移除对 `parse_csv_ids`、`parse_csv_terms` 的直接业务依赖：

- 若这些解析只用于请求构建，交给 Service；
- 若用于页面选项摘要，仅保留 UI 展示所需的本地轻量解析，不生成 JQL、不访问 Jira 字段或缓存；
- 不修改 QML 属性、信号、槽名称和翻译文本；

- [ ] **步骤 6：运行 UI 和 Jira 聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool testing/self_tests/ui/test_jira_bridge_service_boundary.py -q
```

预期：全部通过。

- [ ] **步骤 7：提交任务 4**

```powershell
git add jira_tool/services/factory.py jira_tool/services/__init__.py ui/example/bridge/JiraBridge.py testing/self_tests/ui/test_jira_bridge_service_boundary.py
git commit -m "refactor: narrow Jira bridge boundary"
```

---

### 任务 5：清理、文档和最终验证

**文件：**

- 修改：`jira_tool/README.md`
- 仅在无调用方且前述测试覆盖时删除：被迁空的 Service 文件或无价值兼容导出。

**接口：** 不新增接口；验证最终所有权和兼容性。

- [ ] **步骤 1：检查重复实现和反向依赖**

```powershell
rg -n "_issue_service\._client|_issue_service\._registry|from jira_tool\.(transport|cache|fields|services\.query_builder)" ui/example/bridge jira_tool/services
rg -n "urlopen|Request\(|rest/api" ui/example/bridge jira_tool/services
```

预期：

- 第一条不存在对 `JiraIssueService` 私有成员的访问，也不存在 Bridge 对内部层的导入；
- 第二条的 REST 传输实现只存在于 `jira_tool/transport/client.py`，Service/Bridge 无匹配。

- [ ] **步骤 2：删除确认无调用方的空壳**

针对预计保留的辅助模块和新增服务运行明确的调用方搜索：

```powershell
rg -n "build_(scope_context|browse_result|detail_result|analysis_result)|record_to_issue_row|extract_actions|build_base_jql|browse_specs|detail_specs" -g "*.py" -g "*.qml"
rg -n "JiraBrowseService|JiraAnalysisService|JiraWorkspaceService" -g "*.py" -g "*.qml"
```

只有搜索结果证明仓库调用方已经迁移、文件只剩转发且测试覆盖新入口时才删除。预计保留 `payloads.py`、`presenter.py`、`query_builder.py` 和 `specs.py`，因为它们各自仍有明确职责。

- [ ] **步骤 3：更新中文 README**

README 必须说明：

- Bridge、Workspace 门面、Browse Service、Analysis Service、Issue Service、Client 的职责；
- 唯一依赖方向；
- Create Jira 将通过独立 `CreateIssueService` 扩展；
- Bug Clone 只能生成 `CreateIssueRequest`，不能直接调用 Jira REST；

- [ ] **步骤 4：运行完整聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/jira_tool testing/self_tests/ui/test_jira_bridge_service_boundary.py -q
```

预期：两个命令均退出码 0。第二个命令用于证明根目录历史功能未被本次改动破坏，不授权修改其实现或测试。

- [ ] **步骤 5：执行源码启动检查**

```powershell
.\.venv\Scripts\python.exe -c "from ui.example.bridge.JiraBridge import JiraBridge; from jira_tool.services import create_jira_workspace_service; print('jira-import-ok')"
```

预期：退出码 0，输出 `jira-import-ok`。随后从仓库根目录运行 `main.py`，确认启动日志完成 JiraBridge 注册且没有 Jira 导入、QML 注册或资源错误后主动关闭进程；本次不重建 `SmartTest.exe`，不得把源码验证描述为安装包验证。

- [ ] **步骤 6：执行质量门禁**

```powershell
git diff --check
git status --short
git diff --stat
```

预期：`git diff --check` 退出码 0；状态中只把本计划文件作为本次交付范围，其他起始改动保持原状。

- [ ] **步骤 7：提交任务 5**

```powershell
git add jira_tool/README.md
git commit -m "docs: document Jira integration ownership"
```

Mason 到此停止，不执行 push。Atlas 根据实际起始状态、范围内 diff、测试输出和 `git diff --check` 独立验收；若不通过，回到同一 Mason 任务做定向返工。
