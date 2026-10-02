# 全局异步反馈与 DUT 顺序刷新设计

## 目标与边界

统一生产页面的加载和任务进度视觉 owner，并将测试配置页的一次 DUT 刷新明确为顺序异步流程：扫描 ADB 后立即发布设备列表，再自动准备 Android Client。流程不增加第二个操作入口，不修改 APK/Kotlin 业务，也不新增定时器模拟进度。

## Owner 与接口

- `AppLoadingIndicator.qml`：统一不确定时长的加载动画。
- `AppTaskProgress.qml`：统一确定/不确定任务进度、阶段文本和错误文本。
- `TestPageBridge`：拥有刷新序列状态，暴露 `dutRefreshRunning/Phase/Progress/Detail/Error`；运行期间拒绝重复刷新。
- `ParameterHelper`：`refresh_duts_async` 只扫描，`prepare_android_client_async` 单独执行准备并透传真实阶段回调。
- `android_client`：安装/特权准备 owner 发出真实阶段；命令日志按 return code 分类，空输出不记录。

## 顺序与失败语义

1. 进入 `scan` 并显示 Loading。
2. 后台扫描 ADB。
3. 立即更新并保留 DUT 列表；单设备或仍有效的已选设备作为准备目标。
4. 自动执行 check APK、install status、root、remount、push、provision、reboot、wait online、verify 等实际经过的阶段。
5. 成功进入 `complete`；失败进入 `failed`，保留 DUT 列表并展示失败阶段和原因；所有出口清除 running。

成功命令的 stderr（包括 adb remount 的正常说明）为 info，空 stderr 不写日志；非零返回码为 error，异常和最终验证失败继续抛出并保留 stdout、stderr、returncode 证据。

## UI 与兼容

生产 QML 的直接进度控件迁移到两个公共组件；FluentUI 展示/示例页不迁移。现有 busy/state 只绑定反馈，不改变原业务触发。资源注册到 `resource.qrc` 并重新生成 `resource_rc.py`；新增中英文固定文本。

## 生产异步反馈矩阵

本矩阵以 `ui/example/bridge` 中当前含 async/thread 的生产 owner 为边界；同一 owner 的内部 worker 合并记录，避免把内部实现误当成新的用户流程。

| Bridge / 入口 | 现有状态 owner | QML 反馈 owner | 结论 |
|---|---|---|---|
| `TestPageBridge.discoverCases` | discovery 状态，页面树占位 | 页面既有加载呈现 | 保留；发现与动态字段已有领域呈现 |
| `TestPageBridge.refreshGlobalSchema` | `dutRefresh*` | `T_TestConfig` 的 `AppLoadingIndicator`、`AppTaskProgress` | 已绑定扫描文本、阶段、明细、进度和错误 |
| `AuthBridge` 登录/验证/关闭账户 | `authBusy`、认证状态 | `LoginWindow`、`RedmineLoginView` 的 `AppLoadingIndicator` | 已绑定；不修改认证逻辑 |
| `JiraBridge` 查询、详情、过滤器 | `loading/detailLoading/filtersLoading` | `T_Jira`、Issue 组件的公共 Loading/Progress | 已绑定；会话消息进度保留领域呈现 |
| `JiraAuditBridge` 审计 | `view.state/progressValue` | `JiraAuditWorkspace.AppTaskProgress` | 已绑定确定/不确定进度 |
| `ConfluenceAuditBridge` 目录、详情、审计 | `catalogBusy/detailBusy/auditBusy/progress` | `ConfluenceAuditWorkspace` 公共 Loading/Progress | 已绑定 |
| `RedmineBridge` 登录、查询、项目加载 | `loading/dataLoading/projectsLoading` | 登录和 Issue 公共 Loading/Progress | 已绑定 |
| `DailyReportBridge` 预览、发送 | `state/statusText` | `DailyReportWorkspace.AppTaskProgress` | 已绑定 |
| `DebugBridge.prepareKpiReview` | 页面 `loadingVideo/progressPercent` | `T_Debug.AppTaskProgress` | 已绑定 |
| `BootVideoBridge.refreshCameraModes` | `isProbingCameraModes` | `T_BootVideo.AppLoadingIndicator` | 本轮补齐；按钮在探测期间禁用 |
| `BootVideoBridge` 测试 worker/预览 loop | `isRunning`、预览和结果指标 | Boot Video 领域预览、指标、开始/停止按钮 | 排除：连续采集/预览已有领域呈现 |
| `RunBridge` pytest 进程和 stdout/event pumps | `isRunning`、DUT/step progress | `T_Run` 的步骤、DUT、日志和停止控制 | 排除：连续运行事件泵已有完整领域呈现 |
| `HomeBridge.refreshWallpaper` | 内部 `_refreshing_wallpaper` | 壁纸缓存/回退背景 | 排除：页面初始化后台刷新，非用户阻塞操作 |

检查未发现其他“用户触发、会阻塞当前页面、已有 busy/loading/progress 却未绑定反馈”的入口。没有为了填表新增认证、Jira、审计、持久化或数据状态。

## 实施与验收清单

- [x] RED：证明扫描被 APK 准备阻塞、阶段接口缺失、成功 stderr 被误分级。
- [x] 拆分扫描和准备，并保证列表先发布。
- [x] 接入 Android Client 真实阶段和 finally 等价的全部出口复位。
- [x] 公共 Loading/Progress 组件、QRC 和测试配置页接入。
- [x] 生产直接进度控件迁移（展示示例除外）。
- [x] Android 命令日志按内容与 returncode 分类。
- [x] 聚焦测试、QML/翻译源校验、资源生成、compileall、diff check。

## 限制

无设备时流程只完成扫描；多设备且没有有效选择时立即发布列表并等待用户选择，下次单击仍执行同一完整序列。自测不构建 APK、不安装或连接外部设备，真实 root/remount/reboot 阶段需在可用 DUT 环境验收。
