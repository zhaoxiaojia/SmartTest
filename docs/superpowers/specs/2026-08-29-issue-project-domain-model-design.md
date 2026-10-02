# Issue / Project 核心业务实体重构设计

## 目标

建立两个由 SmartTest 拥有的核心业务实体：`Issue` 只表达 Jira 业务，`Project` 只表达 Confluence 项目业务。所有 Jira、Confluence 的 client/web 消费者通过稳定实体和显式查询接口工作，不再直接传播第三方响应 `dict`，并删除被新实体替代的重复模型、Store、Mapper 与兼容流。

## 已确认边界

- `Issue` 的业务边界是 Jira，不为 Redmine 或其他平台增加兼容字段。
- `Project` 的业务边界是 Confluence 项目，不表示任意来源的通用项目。
- Redmine 等第三方平台不得继承或伪装成 `Issue`；它们通过 Jira 命令接口创建/关联 Issue。
- 初始查询只加载业务列表所需的轻量核心字段；评论、附件、自定义字段、页面详情、角色、里程碑和来源证据等详情按需加载。
- 旧 Redmine 本地缓存和 web Confluence 缓存/数据库实体数据允许失效；不实现迁移、兼容读取或旧结构回退，重构后重新同步。
- 现有 client Common 工具瘦身改动属于用户已批准的独立范围，必须保留，不得回退或混改其业务目标。

## 第三方库复用决策

仓库已声明并安装 `atlassian-python-api==4.0.7`，该依赖同时提供 `atlassian.Jira` 和 `atlassian.Confluence`。两类 API 返回普通 `dict`，没有可继承的稳定 Issue/Project 实体类。

采用组合与映射：

```text
atlassian.Jira -> JiraGateway -> JiraIssueMapper -> Issue
atlassian.Confluence -> ConfluenceGateway -> ConfluenceProjectMapper -> Project
```

- Gateway 负责认证、远程调用、分页、第三方异常归一化和库版本差异。
- Mapper 负责把第三方响应转换为 SmartTest 实体和值对象。
- `Issue`、`Project` 不导入 Jira/Confluence SDK、client、web、Qt、FastAPI 或数据库 ORM。
- 第三方原始响应不进入公开实体。确需诊断或来源留证时，由 Gateway/Repository 单独保存最小原始证据。
- 现有自写 `JiraClient` 的查询、分页、普通 CRUD 优先替换为 `atlassian.Jira`。只有第三方库没有覆盖且产品确实需要的边界能力才允许保留窄实现；不得保留第二套完整 Jira transport。
- 现有 `core/confluence/ConfluenceClient` 调整为 `ConfluenceGateway` 责任，不新建平行 Confluence client。

## 公共按需加载模型

在 `core/domain/detail.py` 定义不可变泛型值对象：

```python
class DetailState(str, Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    STALE = "stale"
    FAILED = "failed"

@dataclass(frozen=True)
class DetailSection(Generic[T]):
    state: DetailState = DetailState.UNLOADED
    value: T | None = None
    source_revision: str = ""
    error_code: str = ""
```

约束：

- `UNLOADED` 表示从未请求，不能解释为空数据。
- `LOADED` 表示请求成功；`value` 可以是空集合或空内容。
- `STALE` 必须保留最后一次成功值，并表示来源 revision 已变化。
- `FAILED` 记录稳定错误码；如果此前存在成功值则继续保留该值。
- entity、Mapper、Repository 只使用状态和稳定错误码，不保存界面提示文本。
- Repository 只加载调用方明确声明的 section，禁止隐式补拉其他详情。

## Issue 聚合

### 所有权和位置

- `core/jira/domain.py`：`Issue` 及 Jira 业务值对象。
- `core/jira/mapper.py`：`JiraIssueMapper`，只负责第三方 payload 与实体的转换。
- `core/jira/repository.py`：`IssueRepository`，只返回 `Issue` 或 `IssuePage`。
- `core/jira/commands.py`：`CreateIssueCommand`、`UpdateIssueCommand` 和结果，不让实体兼任请求 payload。

### 轻量核心字段

```python
@dataclass(frozen=True)
class Issue:
    identity: IssueIdentity
    summary: str
    project: JiraProjectRef
    status: NamedValue
    issue_type: NamedValue
    priority: NamedValue | None
    assignee: PersonRef | None
    reporter: PersonRef | None
    created_at: datetime | None
    updated_at: datetime | None
    labels: tuple[str, ...]
    revision: SourceRevision
    description: DetailSection[RichText]
    comments: DetailSection[tuple[IssueComment, ...]]
    attachments: DetailSection[tuple[IssueAttachment, ...]]
    links: DetailSection[tuple[IssueLink, ...]]
    custom_fields: DetailSection[FieldBag]
```

`IssueIdentity` 保存 Jira `id`、`key` 和 `web_url`；`JiraProjectRef` 保存 Jira project key/id/name；`NamedValue`、`PersonRef` 和 `SourceRevision` 是无 UI 文本的稳定值对象。

### 查询与详情加载

```text
IssueRepository.search(query, page) -> IssuePage
IssueRepository.get(issue_key) -> Issue
IssueRepository.load_details(issue, IssueDetails(...)) -> Issue
```

`IssueDetails` 只能显式声明 `description/comments/attachments/links/custom_fields`。返回新不可变实体，只更新已请求 section。

## Project 聚合

### 所有权和位置

- `core/confluence/project.py`：`Project` 及 Confluence 项目值对象。
- `core/confluence/project_mapper.py`：`ConfluenceProjectMapper`，合并 Product Space 目录事实与项目详情页事实。
- `core/confluence/project_repository.py`：`ProjectRepository`，拥有查询、同步和按需详情加载。
- 现有 `core/tools/common/project_weekly_audit/project_facts.py` 中仍有效的页面解析能力迁入上述 owner；迁移后删除旧工具命名与重复模型。

### 轻量核心字段

```python
@dataclass(frozen=True)
class Project:
    identity: ProjectIdentity
    name: str
    product_space: ProductSpaceRef
    catalog_page: ConfluencePageRef
    status: NamedValue | None
    stage: NamedValue | None
    support_mode: NamedValue | None
    customer_summary: str
    owner_summary: tuple[PersonRef, ...]
    revision: SourceRevision
    roles: DetailSection[tuple[ProjectRole, ...]]
    milestones: DetailSection[ProjectMilestones]
    hardware: DetailSection[FieldBag]
    software: DetailSection[FieldBag]
    facts: DetailSection[FieldBag]
    evidence: DetailSection[tuple[SourceEvidence, ...]]
```

`ProjectIdentity` 保存 Confluence project identity 与业务 `project_id`；`ConfluencePageRef` 只保存 page id/title/url/version，不保存 HTML 正文。

### 查询与详情加载

```text
ProjectRepository.query(filters, page) -> ProjectPage
ProjectRepository.get(project_id) -> Project
ProjectRepository.load_details(project, ProjectDetails(...)) -> Project
ProjectRepository.refresh_catalogs(scope) -> ProjectSyncResult
```

`ProjectDetails` 只能显式声明 `roles/milestones/hardware/software/facts/evidence`。页面正文、表格行、页面树和抓取进度只存在于 Gateway/Mapper/Repository，不进入 `Project`。

## Redmine 与第三方平台

- Redmine 使用独立 `RedmineIssue` 和 Redmine 自己的 Store/Repository。
- `RedmineIssue` 不继承、不聚合完整 `Issue`，也不复制 Jira 状态、优先级或 custom field 语义。
- Redmine 创建 Jira 的数据流：

```text
RedmineIssue -> RedmineToJiraMapper -> CreateIssueCommand
-> IssueRepository.create(...) -> IssueRef / Issue
```

- 创建或查重成功后，Redmine 只保存 `IssueRef`（Jira id/key/url），不把 Jira entity 塞回 Redmine entity。
- 其他第三方平台复用同一个 Jira command boundary，各自拥有自己的源实体和 Mapper。
- 可以共享纯展示 DTO，但展示 DTO 不是核心实体，不能反向成为业务 owner。

## 原有结构替换

### Jira

- `IssueRecord` 的查询结果职责由 `Issue` 替代。
- `UnifiedIssue` 不再承担 Jira/Redmine 混合业务；Jira 消费者改用 `Issue`，Redmine 消费者改用 `RedmineIssue`。
- `IssueStore` 拆回各业务 owner；不保留通用可变 Store。
- `CreateIssueRequest` 替换为 `CreateIssueCommand`。
- `ExistingIssue` 替换为 `IssueRef` 或 Repository 查询结果。
- `JiraIssueService`、presenter 和 bridge 中的重复 payload 转换收敛到 `JiraIssueMapper` 与展示 DTO Mapper。

### Confluence

- `ProjectCandidate`、`ConfluenceProject` 由 `Project` 替代。
- `ProjectCollection`、`ProjectCollectionFilter` 的业务查询职责迁入 `ProjectQuery`、`ProjectPage` 和 Repository。
- web snapshot/数据库行与 `Project` 之间只有 Repository codec；API 不再把内部 snapshot dict 当成业务实体。
- 删除迁移后无消费者的 `project_weekly_audit` 旧模型、工具命名、过滤与重复序列化代码。

### 删除原则

- 同一业务事实只保留一个 owner。
- 所有消费者完成替换后立即删除旧类，不保留 re-export、兼容 alias、双写、旧缓存读取或旧字段 fallback。
- 删除以真实引用扫描为准；不因名称相似删除仍被其他业务使用的协议、页面解析或展示组件。

## 数据和缓存

- 新实体序列化使用显式 schema version，并由对应 Repository codec 管理。
- 旧 Redmine cache 与旧 Confluence project snapshot/database rows 不迁移、不读取。
- 首次使用时通过各自远程源重新同步；同步失败必须如实返回失败，不用旧缓存掩盖。
- `Issue`/`Project` 不包含同步进度、页面 loading、选择状态、错误提示文本或 UI 展开状态。

## 实施检查单

- [ ] 记录起始 `git status`，保护已批准的 client Common 工具瘦身改动和其他用户改动。
- [ ] 为 `DetailSection` 状态约束建立 RED 测试，再实现公共值对象。
- [ ] 为轻量 `Issue`、显式详情加载和 Jira Mapper 建立 RED 测试。
- [ ] 复用 `atlassian.Jira` 建立唯一 Jira Gateway；记录第三方未覆盖能力和保留的最小窄实现。
- [ ] 将 Jira 查询、详情、创建/查重消费者迁移到 `Issue`、`IssueRepository` 和 command boundary。
- [ ] 建立独立 `RedmineIssue` 与 `RedmineToJiraMapper`，替换 Redmine 对 `UnifiedIssue` 的依赖。
- [ ] 删除 `IssueRecord`、`UnifiedIssue`、通用 `IssueStore`、`CreateIssueRequest`、`ExistingIssue` 及无消费者代码。
- [ ] 为轻量 `Project`、显式详情加载和 Confluence Mapper 建立 RED 测试。
- [ ] 将 project facts、web repository/API 消费者迁移到 `Project`、`ProjectRepository` 和查询对象。
- [ ] 删除 `ProjectCandidate`、`ConfluenceProject`、旧 collection/filter 模型、旧缓存兼容和无消费者代码。
- [ ] 清理重复 Mapper、dict 业务流、re-export、旧测试和失效依赖声明。
- [ ] 运行 Jira、Redmine、Confluence、web API、client bridge 的聚焦测试以及 import/compile 检查。
- [ ] 验证列表查询不加载详情 API，详情请求只加载明确 section。
- [ ] 从仓库根目录进行有界 client source 启动和 web API source 验证；不构建桌面包。
- [ ] 检查净生产代码增长/减少、scoped diff、生产引用扫描和 `git diff --check`。

## 验收标准

- `Issue` 是唯一 Jira issue 核心实体，字段不含 Redmine/UI/transport/ORM 兼容语义。
- `Project` 是唯一 Confluence project 核心实体，字段不含 HTML/table row/UI/同步进度。
- Jira 与 Confluence 普通远程访问复用 `atlassian-python-api==4.0.7`，不存在第二套完整 transport。
- Redmine 通过 command + Mapper 调用 Jira，不继承或伪装 `Issue`。
- 轻量查询不会获取评论、附件、项目详情页或页面树。
- 每个详情分区正确区分 `UNLOADED`、`LOADED`、`STALE`、`FAILED`。
- 旧缓存允许失效，没有迁移、兼容读取、双写或回退代码。
- 原有重复模型及无消费者代码删除，生产引用扫描无残留。
- client Common 工具瘦身改动完整保留且相关测试仍通过。
- Functional Acceptance 和 Code Quality 均 PASS，`git diff --check` 通过。

## 交付方式与配额

采用 Atlas + 唯一 Mason 单线程交付。Mason 负责目标代码调查、TDD 实现、清理和自测；Atlas 依据 scoped diff、引用边界和新鲜测试证据验收。配额基线为剩余 90%（已使用 10%）；已使用达到 13% 时报告，达到 15% 或 30 分钟内增加 5% 时暂停并请求 Coco 授权继续。
