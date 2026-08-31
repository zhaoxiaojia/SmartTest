# SmartTest 多端统一日志设计

## 目标

SmartTest Client、SmartTest Tool、Web Server、测试运行时和 Android 使用同一日志记录协议、字段语义与可读格式。日志公共机制由 `core` 唯一拥有；平台层只负责接入本平台输出通道，不得重新封装日志模型、格式器、文件写入或级别体系。

## 当前状态

- `support/logging.py` 已拥有 Python 侧结构化记录、控制台格式、JSONL、可读文件、运行事件、颜色和路径处理，并被 Client、Core、测试运行时及工具广泛使用。
- Web 请求目前依赖 Uvicorn access log，格式与 SmartTest 日志不一致，也缺少统一的耗时和平台字段。
- Android 直接使用 `android.util.Log`，没有完整遵守 Python 日志字段和显示顺序。
- `support` 不是公共业务 owner；继续让各端直接使用框架日志会产生重复格式和调试分裂。

## 唯一所有权

### Python 公共实现

将 `support/logging.py` 的有效实现迁移到 `core/logging/`：

```text
core/logging/
├── __init__.py       # 稳定公共导入入口
├── record.py         # SmartLogRecord、字段标准化、显示字段
├── formatter.py      # 控制台、JSONL、可读文本格式
└── logger.py         # smart_log、输出通道、路径与运行事件
```

迁移以现有成熟实现为基础，不重写已有机制。所有 Python 调用改为从 `core.logging` 导入；迁移完成后删除 `support/logging.py`，不保留长期兼容转发层。

### 跨平台协议

标准记录字段为：

```text
timestamp, platform, level, domain, source, message,
request_id, case_nodeid, step_id, extra
```

其中 `platform` 取值为 `client`、`tool`、`web`、`runner`、`mobile`。未适用的身份字段使用空值，不创建平台私有同义字段。

标准可读格式为：

```text
<timestamp> [<platform>] [<domain>] [<LEVEL>] [<source>] <message>
```

JSONL 保留同一字段语义，不包含 ANSI；颜色只属于控制台或 UI 展示。

### Android 适配器

Android 无法直接执行 Python，因此在 `mobile/android` 保留一个必要的 Kotlin 适配器。它只完成：

- 构造与公共协议一致的字段；
- 按统一可读格式写入 Logcat；
- 保留 case/request/step 身份。

它不得定义第二套级别、字段别名、文件格式、日志模型或业务日志入口。现有散落的 `Log.i/w/e` 调用迁移到该适配器；完成后移除重复的格式拼接。

## 各端接入

### Client、Tool 与测试运行时

- 全部使用 `core.logging.smart_log`。
- 保留 `FluLogger` 仅作为第三方 UI 接口所需的薄适配层；不得拥有格式、存储或级别决策。
- 现有静态日志、运行事件和报告日志行为保持不变，仅增加统一 `platform` 字段和新的导入路径。

### Web Server

- FastAPI 增加一个请求日志中间件，在请求结束时调用 `core.logging.smart_log`。
- 请求日志包含 method、path、status、duration_ms；异常请求在保留 FastAPI 错误处理的同时按相应级别记录。
- 不记录请求体、数据库密码、Token、Cookie 或其他敏感信息。
- 关闭 Uvicorn access log，避免同一请求打印两次；Uvicorn 启动和框架错误日志接入统一 Python logging handler 或使用同一格式。
- Vite 只负责开发代理；浏览器 `console.log` 不属于服务端日志，也不建立远程采集机制。

### Android

- Runner、Command、设备操作和 Case 统一调用 Kotlin 适配器。
- Android 原生日志 tag 仅作为 Logcat 路由信息，正文必须保持统一格式。

## 规则与防回退

1. 新增 `.codex/skills/smarttest-logging-workflow/SKILL.md`，记录唯一 owner、字段协议、平台适配边界、敏感信息和验证要求。
2. 在根 `AGENTS.md` 的 Required Skill Routing 中增加日志相关路由；任何 logger、print、Logcat、FastAPI access log、日志格式或日志存储改动必须读取该 skill。
3. 扩展 `support/ci/check_product_boundaries.py`，至少拒绝：
   - 新增 `support.logging` 导入；
   - Python 产品代码新增自有 logger/formatter/file handler；
   - Web 重新开启独立 access-log 格式或请求日志中间件；
   - Android 在批准的适配器之外新增直接 `android.util.Log` 调用；
   - 产品运行代码使用临时 `print` 代替公共日志。
4. 命令行构建、CI 检查和离线脚本可以继续使用 stdout，但不能被产品运行时导入为日志机制。

## 清理范围

- 删除 `support/logging.py` 及其过时测试/兼容引用。
- 合并或删除重复的 FluentUI、Web、测试运行时日志格式化逻辑，只保留真实平台接口需要的薄适配。
- 删除 Android 散落的直接 Log 调用和重复字符串格式。
- 不改业务日志文案，不借迁移新增埋点、远程上传、日志服务器、账号或权限功能。
- 不处理解析外部固件日志等业务工具中的原始 stdout，除非它们属于 SmartTest 产品运行日志入口。

## 实施顺序

1. 固定现有 Python 日志行为和新增跨平台字段的回归测试。
2. 建立 `core.logging`，迁移 Python 调用并删除 `support/logging.py`。
3. 接入 FastAPI 请求日志，关闭重复 Uvicorn access log，验证 Vite → FastAPI 请求可见。
4. 建立 Android 薄适配器并迁移直接 Log 调用。
5. 写入 logging skill、AGENTS 路由和自动边界检查。
6. 全仓搜索并移除冗余实现、临时诊断和废弃兼容路径。

## 验收标准

- Python 各产品入口只从 `core.logging` 使用公共日志，仓库中不存在 `support.logging` 导入或实现文件。
- Client、Tool、Web、Runner、Mobile 的可读日志字段顺序一致，并带正确 `platform`。
- Web 每个 API 请求只打印一次，包含 method/path/status/duration，且请求经 Vite 代理后可在服务端看到。
- Android 业务代码不直接调用 `android.util.Log`；公共适配器输出与协议一致。
- 原有静态 JSONL、可读日志、运行事件、报告日志及 UI 颜色行为没有回归。
- 边界检查能拒绝一个故意新增的私有 logger、`support.logging` 导入和 Android 直接 Log 调用。
- Python 聚焦测试、Web 全量检查、Android 单元测试与 debug APK 构建通过；无真实 Android 设备时明确说明未做硬件验证。
- `git diff --check` 通过，五个既有用户未提交文件保持原样，当前 Web Wi-Fi Database 改动完整保留。

## 不在范围内

- 云端日志收集、遥测、告警平台和远程检索。
- 浏览器日志上传。
- 改写业务日志内容或增加新业务埋点。
- 修改 Wi-Fi Database 查询、图表、导出或导航行为。
