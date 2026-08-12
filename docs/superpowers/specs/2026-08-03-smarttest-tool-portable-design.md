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

## 2026-08-12 运行时资源完整性设计

Tool portable 的业务数据文件与动态 Python 依赖必须分开管理和验证。新增一个由打包 owner 管理的统一运行时资源清单，清单声明源文件、portable 相对目标和必需性；`tool.spec` 的 `datas` 与 `script-build-tool-portable.py` 的产物校验共同消费该清单，禁止在两处重复手写。首批必需资源包括 `config/personnel.json` 与 `build/generated/build_manifest.json`，后续 Tool 业务新增文件型运行时依赖时只允许扩展该清单。

frozen Tool 的资源根必须解析为包含完整清单的 onedir 根或 PyInstaller `_MEIPASS` 根；不得回退到源码目录，也不得允许脱离 portable 目录的裸 EXE 继续运行。资源缺失时抛出面向用户的明确错误，列出缺失的相对资源并提示运行完整 `SmartTestTool` 目录中的 EXE，不暴露无意义的底层 `FileNotFoundError`。

构建校验在生成 ZIP 前依次执行：验证目录与全部必需资源；验证 Python archive 的允许/禁止模块；执行动态依赖 smoke imports；从 portable EXE 的实际工作目录执行一个 context smoke 模式，真实调用 `create_context_objects` 并确认 `AuthBridge` 已成功加载人员资源；最后才执行窗口启动存活检查和 ZIP 创建。任何一步失败都不得生成新的 ZIP。

### 执行清单

- [ ] 先为统一资源清单、spec 消费、缺失资源失败和完整 context smoke 增加失败测试。
- [ ] 建立唯一 Tool runtime resource manifest，并让 spec 与构建校验共同消费。
- [ ] 收紧 frozen `runtime_root`，对裸 EXE/资源不完整目录提供明确错误。
- [ ] 增加 portable context smoke CLI，并在 ZIP 创建前执行。
- [ ] 验证现有 portable 目录、重新构建 Tool、从产物目录启动 smoke 与 UI，并检查 ZIP 结构。
- [ ] 运行 Tool UI/打包聚焦测试、编译和 `git diff --check`，清除构建诊断残留。
