# SmartTestTool 便携版设计

## 目标

新增独立的 Windows `SmartTestTool` 便携版。产物解压后直接运行，不生成 Inno Setup 安装包。完整版 SmartTest 的入口、导航和打包流程保持不变。

## 产品范围

保留：

- 登录、身份和 Tool 权限判断。
- Tool 页面全部现有业务：Jira Format Audit、Project Weekly Audit、Redmine、全局 Schedule。
- 完整 Settings 页面、About、主题、语言和必要的前端状态。
- Tool 业务实际使用的 Jira、Confluence、Redmine、Excel 导出和 Windows Scheduler owner。

排除：

- Home、Test、Run、Report、AI、独立 Jira、Debug、Boot Video 页面。
- 上述页面的 Bridge、QML、测试运行数据、Android/APK 与 Python 子进程运行时。
- Tool 未实际使用的 OpenCV、NumPy、Matplotlib 等大型依赖。
- Inno Setup 和安装器包装阶段。

Settings 中已有的配置项保持可见和可编辑；若某设置只保存配置而不执行已移除业务，不因此引入对应业务运行时。

## 架构

### 独立入口

新增 Tool 专用 Python 入口，仅实例化 Tool 壳需要的 QObject/Bridge。不得从完整版 `ui/example/main.py` 转发启动，避免其顶层 import 把已排除业务带入 PyInstaller 分析。

### 独立导航壳

新增 Tool 专用 QML App/Window/导航清单，复用现有登录、Tool、Settings、About 和通用 FluentUI 组件。已排除页面不只是隐藏，而是不进入 Tool 版 QRC 和运行对象图。

### 精简资源

新增 Tool 专用 QRC 与生成资源。资源清单只包含专用壳、复用页面的传递依赖、必要图片、字体和翻译；不整目录复制 `ui/`。

### 独立 PyInstaller 目标

新增 `SmartTestTool` `onedir` spec：

- 使用专用入口和 Tool QRC。
- datas 只收集 personnel、build manifest 及 Tool 运行必需文件。
- 不复制整个 `testing/`、`AI/`、`jira/`、`android_client/`、`support/` 或 `ui/` 源目录。
- hidden imports 只声明 Tool 的动态依赖。
- 明确排除已移除业务和确认未使用的大型依赖。

### 构建产物

新增便携构建脚本，依次：

1. 更新翻译与 Tool QRC。
2. 按桌面打包规则更新 build manifest 版本。
3. 执行 Tool 专用 PyInstaller spec。
4. 验证目录运行时的关键 import、资源和启动。
5. 生成 `dist_tool/SmartTestTool-<version>-windows.zip`。

目录产物保留为 `dist_tool/SmartTestTool/`，不调用 Inno Setup，不构建或复制 APK，不构建测试 Python runtime。

## 依赖纪律

- Tool 内 Jira Audit 可保留其实际使用的 Jira integration；排除独立 Jira 页面不等于排除所有 Jira 客户端依赖。
- Redmine 若实际依赖 QtWebEngine，则保留对应 Qt 模块；不得仅为追求体积破坏登录流程。
- Settings 配置 owner 保留，但已移除业务的执行模块不得被 Settings 间接导入。
- 任何依赖排除必须通过 import、QML 加载或便携产物启动验证证明安全。

## 验收

- 便携目录和 ZIP 均生成，解压后可直接运行 `SmartTestTool.exe`。
- 登录、Tool、Settings、About 可访问，Tool 权限与完整版一致。
- Jira Format Audit、Project Weekly Audit、Redmine 与全局 Schedule 的关键交互可加载，无缺失 Bridge/QML/动态 import。
- 导航中不存在 Home、Test、Run、Report、AI、独立 Jira、Debug、Boot Video。
- 产物不包含 `testing/`、`AI/`、Android/APK、OpenCV、NumPy、Matplotlib及已移除 Bridge。
- 提供与当前完整版构建的耗时、目录体积、文件数和 ZIP/安装包大小对比；若缺少可比的旧产物，明确只报告新产物实测值。
- 完整版相关入口和回归不受影响。
