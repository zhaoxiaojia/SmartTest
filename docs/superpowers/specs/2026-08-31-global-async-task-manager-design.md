# 全局 AsyncTaskManager 设计

## 目标与边界

SmartTest 需要一套业务无关的异步任务基础设施，统一管理 Web 后端和桌面 Client 中**有限、可取消、可观察进度**的后台工作。Confluence 只是第一个调用方，不能在核心层出现 Confluence、FastAPI、Qt 或浏览器前端依赖。

“全局”按进程定义：Web ASGI 进程和桌面 Qt/qasync 进程分别创建一个全局 `AsyncTaskManager` 实例。两者共享 `core` 中的任务模型、状态机和调度语义，但不能共享内存、任务对象或任务 ID；浏览器前端仅消费 Web 暴露的任务快照。首版不新增跨进程的中央任务服务。

首版覆盖一次性或有明确结束条件的任务。测试运行的 stdout/JSON 三泵、相机预览、设备持续日志等长期流式任务暂不改为普通 Future；它们后续只接入统一的状态/事件协议，并保留自身 stop、join、子进程和硬件释放机制。

## 现状与问题

当前后台执行器分散：Web 有 `ManualAuditRegistry` 的常驻线程池、Confluence details 的每次线程池、catalog/details 的 daemon thread；桌面端有 qasync `create_task`、Redmine 专用 asyncio loop、多处 Bridge 私有线程及短生命周期线程池。它们各自维护取消、进度和结果，彼此不知道并发总量。

这会造成两个直接问题：多个任务池可同时扩容，无法施加进程级并发上限；父审查的 `156` 项进度和单项目 `8` 项检查各自渲染，使页面在两个尺度间切换，甚至出现两条同级进度条。

## 核心模型

在 `core/async_tasks/` 提供以下无框架依赖的类型：

- `AsyncTaskManager`：进程内唯一的队列、工作者与任务注册表所有者。
- `TaskHandle`：提交者持有的根任务引用，用于读取快照和请求取消。
- `TaskContext`：实际工作函数收到的上下文，用于创建子任务、检查取消、报告进度、完成或失败。
- `TaskSnapshot`：不可变查询结果，含 `task_id`、父任务、类型、状态、时间、计数、错误摘要和当前可见子任务。
- `TaskEvent`：状态或进度变化事件；核心只传机器可读字段，不包含 UI 文案。
- `CancellationToken`：协作式取消信号。取消请求不强杀线程；工作函数必须在安全边界检查该信号。

状态机固定为 `queued -> running -> completed | failed | cancelled`。终态不可再迁移。失败记录经过脱敏的错误摘要，完整异常仅由调用进程的日志所有者记录。

每个根任务可以拥有任意层级的子任务。任务类型、资源键、展示名称和负载由调用方提供；核心不解释业务负载，也不持久化凭据。

## 调度与生命周期

每个进程启动时由应用组合根创建一个 manager，并在进程退出时停止接收新任务、请求取消未完成任务、等待有限时间后释放工作者。业务模块不得自行创建 `ThreadPoolExecutor`、后台 daemon thread 或私有任务队列；它们提交工作单元给 manager。

manager 使用单一共享工作池，默认并发数为 16，并由 `SMARTTEST_ASYNC_MAX_CONCURRENCY` 配置。值必须为正整数；进程启动时读取一次，非法值回退为 16。任务可声明可选的通用 `resource_key`，manager 可为同一键配置更低配额，避免某类外部资源独占工作池。没有资源键的任务只受全局并发限制。

任务的工作函数不再嵌套创建工作池。需要并行的业务把每个工作单元作为同一根任务的子任务提交，manager 统一排队和计数。父任务的完成由其已登记子任务全部进入终态决定；取消会阻止尚未开始的子任务并向运行中的子任务广播 token。

## 进度与呈现契约

根任务进度始终使用自己的稳定总量，例如 Confluence 审查显示“16/156 个项目”。子任务不得替换父任务的进度尺度。

manager 为每个根任务计算一个 `visible_child`：

- 子任务运行不超过 `SMARTTEST_ASYNC_CHILD_VISIBLE_AFTER_MS`（默认 2000 ms）时不对 UI 暴露；
- 超过阈值时，只选择运行时间最长的一个子任务，附带其自身计数和展示名称；
- 子任务结束后立刻隐藏，下一候选子任务满足阈值才显示；
- 相同根任务的进度事件按 `SMARTTEST_ASYNC_PROGRESS_INTERVAL_MS`（默认 250 ms）合并，终态事件不延迟。

UI 只能把根任务绘制为一条主进度条。`visible_child` 仅渲染为主进度条下的一行状态文字，例如“当前：Yak612 · Test Plan · Category（3/8）”，而不是第二条同级进度条。没有可见子任务时不保留空白占位。

## 适配边界

### Web

Web 应用在 startup 创建 manager，在 shutdown 关闭它。Web 适配层负责把 `TaskSnapshot` 转换为 REST 响应，并按会话/账户重验任务归属；任务 ID 只在所属会话中可查询、下载或取消。核心不依赖 HTTP。

新增通用任务查询和取消接口，业务创建接口只返回根任务 ID；现有前端仍可用 500ms 轮询读取快照，后续是否改推送不属于本次范围。Confluence 页面只订阅一个当前根任务，并按上述主进度/延迟子状态呈现。

Confluence 调用顺序保持已确认的业务规则：进入页面读取数据库缓存；Reset 只发起过滤器/catalog 任务；Apply 发起项目详情任务；Review 发起审查任务。它们都通过 manager 提交，不能互相预同步而产生第二个可见任务。

首批 Web 迁移对象为 `ManualAuditRegistry`、`BackgroundFactsRefresh` 和 `ConfluenceProjectSyncCoordinator`，删除它们各自的线程池、daemon thread 和平行进度状态。

### 桌面 Client

桌面应用启动时创建其本进程的 manager。Qt Bridge 不可由后台工作线程直接修改 QObject/QML 字段；桌面适配器把任务事件转换为既有 Qt signal，再由主线程更新 `Property` 与 `AppTaskProgress`。

qasync coroutine 仍由主事件循环执行，Bridge 将其登记为 manager 管理的任务；同步阻塞工作由 manager 工作者执行。Redmine 的专用 asyncio loop、RunBridge 和 BootVideo 不在首版强行合并：先为其建立适配接口与状态观察，待明确各自 loop/硬件清理协议后分批迁移。首批桌面迁移只包含 AuthBridge、HomeBridge、DebugBridge 等一次性线程任务。

## 迁移顺序与验收

1. 在 `core` 实现无框架依赖的任务模型、状态机、队列、取消和事件合并，并以单元测试固定并发、终态、取消、父子进度和 2 秒可见阈值。
2. 建立 Web 组合根和 REST 适配器，迁移 Confluence 三个执行所有者；验证缓存/Reset/Apply/Review 的触发边界，以及单主进度条的快照契约。
3. 建立 Qt/qasync 适配器，迁移三个一次性 Bridge；验证信号在主线程消费且不新增私有线程。
4. 为 Redmine、RunBridge、BootVideo 建立迁移清单和资源释放验收，不在本次重构中改变其长期流式业务行为。

验收条件：同一进程内所有首批迁移任务只由一个 manager 调度；默认总并发最多 16；业务模块不再为这些任务创建独立线程池；根进度不被子进度覆盖；快速子任务不显示，慢子任务仅显示文字状态；取消、失败和授权边界可复现并有测试；既有 Confluence 缓存、Reset、Apply、Review 行为不回归。

## 非目标

本次不引入 LLM，不建立跨进程共享任务服务，不修改浏览器端执行模型，不把长期硬件/子进程流强制改为普通 Future，也不更改 Confluence 审查规则或模糊匹配业务逻辑。
