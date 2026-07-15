# SmartTest 内部 Jira 封装瘦身设计

**日期：** 2026-07-15
**状态：** 方案方向已确认，书面设计待 Coco 审阅

## 目标

在继续深度开发 Jira 功能前，瘦身 SmartTest 内部的 `jira_tool` 架构。在保持现有 Jira 页面行为不变的前提下，为网络请求、字段转换、缓存、查询、工作区及后续创建 Jira 建立唯一且清晰的职责归属。

本次不修改、不吸收根目录的 `jira_handler.py`。

## 范围

### 本次包含

- 减少 `ui/example/bridge/JiraBridge.py` 中的业务逻辑。
- 合并 `jira_tool` 内重复或只有转发作用的封装。
- 保持 `jira_tool/transport/client.py` 为 Jira REST 请求的唯一出口。
- 明确查询、工作区、同步及未来创建 Jira 的服务边界。
- 保持现有 Jira UI 行为、配置、持久化数据和外部调用合同不变。
- 为本次调整的 Service 和 Bridge 边界补充聚焦测试。

### 本次不包含

- 根目录的 `jira_handler.py`。
- 新增顶层 `Tool` 页面及导航。
- Bug Clone 功能及客户系统适配器。
- 客户系统认证、网页解析或 API 接入。
- 通用 Connector 或插件框架。
- Jira 页面重新设计或用户可见行为变更。
- 迁移现有 Jira 用户配置。

## 总体架构

依赖方向固定为：

```text
Jira QML
  -> JiraBridge（UI 适配层）
  -> 应用服务层
  -> JiraClient（唯一 REST 边界）
  -> Jira Server
```

依赖不得反向。QML 不直接调用 `jira_tool`，Service 不导入 QML 或 Qt，`JiraClient` 不负责展示逻辑或业务流程判断。

## 职责划分

### JiraBridge

`JiraBridge.py` 仅负责：

- Qt Property、Signal 和 Slot；
- 页面可见的加载、错误、选择和分页状态；
- 发起异步的应用服务调用；
- 把稳定的 Service 返回结果转换为现有页面视图模型；
- 发出经过翻译的固定 UI 文本。

它不得负责 REST 路径、请求体构建、JQL 拼装、Jira 字段提取、缓存存储细节、同步决策或未来创建 Jira 的校验。

Bridge 方法应保持统一流程：接收页面操作，调用一个应用服务，再更新页面状态。

### JiraClient

`jira_tool/transport/client.py` 继续作为唯一 Jira 网络边界，负责：

- 认证、基础地址、API 版本、TLS、超时和 JSON 编解码；
- HTTP 方法及 Jira 接口调用；
- 分页请求机制；
- 将 HTTP 和传输错误转换为统一的领域传输错误。

它不决定页面展示哪些字段，不组织 Issue 展示结构，也不判断业务流程是否可以继续。

后续可在这里增加项目元数据、Issue Type、Create Metadata、创建 Issue 和上传附件等底层请求。本次重构不要求实现这些能力，除非实现过程中需要用最小接口证明最终边界可行。

### 应用服务层

Service 按用户业务用例组织，不按“一个接口一个包装器”组织：

- `issue_service.py`：Issue 查询和 Issue 级操作。
- `workspace.py`：组装 Jira 页面消费的稳定工作区数据。
- `sync_service.py`：基于其他职责所有者完成同步判断和执行。
- `query_builder.py`：在确有复用价值时负责纯 JQL 构建。
- 后续的 `create_issue_service.py`：Create Metadata、动态校验、请求构建、创建 Issue 和附件上传顺序。

现有 Service 文件只有在职责更清晰时才保留、合并或重命名。只有单一调用方且仅做简单转发的文件，应合并到对应应用服务中。

### 字段与数据模型

- `jira_tool/fields/` 是 Jira 字段规格、提取和规范化的唯一所有者。
- `jira_tool/core/models.py` 保存跨 Service 使用的稳定数据合同。
- Jira 原始响应尽量限制在 transport 和字段处理边界内；传给 Bridge 的结果使用稳定模型或明确约定结构的字典。
- 只有当 `core/models.py` 会混入明显无关的合同并变得难以理解时，才新增模型文件。

### 缓存

每类缓存只有一个读写所有者。Service 通过该所有者使用缓存，不直接读写缓存文件。缓存键和失效策略属于业务层，不属于 Bridge 或 QML。

## 合并与删除原则

本次重构遵守以下限制：

1. 所有 Jira 请求必须经过 `JiraClient`。
2. 同一种 Jira 字段转换只有一份实现。
3. 同一种缓存数据只有一条读写路径。
4. 删除不提供策略、边界、转换或测试隔离价值的包装层。
5. 不新增推测性的 `Connector`、`Provider`、`Repository` 或插件层。
6. 不为了目录对称而移动已经职责清晰的代码。
7. 必须兼容公共导入时，只保留轻量兼容导出，不维护两套可运行实现。
8. 所有仓库调用方完成迁移且测试证明不再使用后，才能删除旧路径和兼容导出。

## 后续创建 Jira 的边界

目标应用服务合同为：

```text
CreateIssueService
  get_create_context(project, issue_type)
  validate(request, metadata)
  create(request)
  upload_attachments(issue_key, files)
```

`CreateIssueRequest` 包含目标项目、Issue Type、摘要、描述、标准字段和自定义字段。必填字段不得硬编码，校验必须使用目标项目和 Issue Type 对应的 Jira Create Metadata。

后续 Bug Clone 的数据流独立为：

```text
客户系统适配器 -> ExternalIssue -> 字段映射 -> CreateIssueRequest -> CreateIssueService
```

客户系统适配器不得直接请求 Jira；Jira 创建服务也不得理解客户网页或客户特有字段。

## 错误处理

- `JiraClient` 统一传输错误，同时保留 Jira 返回的可执行错误信息。
- Service 补充操作上下文，并返回或抛出稳定的领域错误。
- Bridge 翻译固定应用文本，Jira 返回的外部内容保持原文。
- 被取消或已经过期的异步结果不得覆盖较新的页面状态。
- 重构后不得静默回退到第二套传输路径或并行的旧数据流。

## 实施策略

本次是保持行为不变的重构，按有限步骤执行：

1. 用聚焦测试固定现有公共行为和调用关系。
2. 盘点现有模块，并标记为保留、合并、迁移或删除。
3. 将泄漏到上层的 REST 请求和字段处理收回现有职责所有者。
4. 将业务流程决策从 `JiraBridge` 移入应用服务。
5. 调用方迁移完成后，删除多余转发模块和废弃路径。
6. 验证当前源码模式的 Jira 行为；创建 Jira 留到独立交付中实现。

本次涉及 UI 和 Jira 层之间的共享合同调整，实施采用方案 B：Atlas 负责范围和验收，Mason 负责目标代码调查、实现、清理和自测。

## 验收标准

### 功能验收

- 现有 Jira 页面的加载、筛选、分页、Issue 详情、刷新和同步行为保持不变。
- 现有 Jira 配置和缓存无需迁移即可继续读取。
- 聚焦的 Jira Service 和 Bridge 测试通过。
- 源码模式启动无 Jira 导入、QML 注册或资源错误。

### 代码质量验收

- `JiraBridge.py` 不再直接处理 Jira HTTP/REST、缓存文件、字段提取或 JQL 业务构建。
- `JiraClient` 是 `jira_tool` 和 Jira UI 流程中唯一有效的 Jira REST 路径。
- 字段转换和缓存访问各自只有一个所有者。
- 不保留并行实现、推测性抽象、临时诊断或无关改动。
- 被删除或合并的模块不存在仓库调用方。
- 范围内 diff 审查及 `git diff --check` 通过。

## 交付边界

当现有 Jira 功能行为保持不变，并且后续新增创建 Jira 服务时无需向 `JiraBridge.py` 添加 REST、元数据校验或请求体构建逻辑，本次重构即完成。

`Tool` 页面和 Bug Clone 必须进入独立设计及实施计划，不在本次重构中顺带开发。
