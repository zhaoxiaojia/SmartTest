# SmartTest

SmartTest 是一个单仓库多端项目：

- `client/`：Windows QML 桌面客户端；
- `core/`：不依赖任何产品端的共享业务核心；
- `web/`：独立 Web 前端和 FastAPI 后端；
- `mobile/`：Android 客户端。

依赖方向固定为：

```text
client ---------------------> core
web/frontend -> web/backend -> core
mobile ------> web/backend -> core
```

## 环境准备

基础环境为 Python 3.10、JDK 17 和 Android SDK。Windows Client 发布机还需要 Inno Setup；Android 正式产物需要平台签名材料。Web 使用的固定 Node.js/npm 由初始化脚本安装到项目 `.venv`，不依赖系统预装。

在仓库根目录执行一次初始化命令。该命令会创建或更新 `.venv`，安装 Client、测试、打包和 Web 后端 Python 依赖，安装 Playwright Chromium 和固定版本的 Node.js/npm，并在 `web/frontend/` 执行 `npm ci`：

```powershell
python core/devtools/scripts/init_venv.py
```

首次克隆、删除 `.venv` 后或依赖清单变化时重新执行；日常启动不需要重复初始化。任一依赖安装失败时脚本直接返回失败。

签名材料只保存在构建机。默认约定目录为 `C:\SmartTestBuild\signing`，其中保持以下结构：

```text
prebuilts/sdk/tools/lib/signapk.jar
build/target/product/security/platform.x509.pem
build/target/product/security/platform.pk8
```

管理员设置机器级变量后，需要重启 GitHub Runner 服务：

```powershell
[Environment]::SetEnvironmentVariable('SMARTTEST_SIGNAPK_DIR', 'C:\SmartTestBuild\signing', 'Machine')
```

## 统一命令

以下命令都从仓库根目录执行。

### 独立开发

```powershell
./.venv/Scripts/python.exe client/scripts/dev.py
./.venv/Scripts/python.exe web/scripts/dev.py
```

Client 和 Web 分别维护自己的长期运行生命周期，不提供统一 `dev all`。Mobile 开发构建直接使用 `mobile/android/gradlew`。

### 检查

```powershell
./.venv/Scripts/python.exe core/devtools/smarttest.py check client
./.venv/Scripts/python.exe core/devtools/smarttest.py check web
./.venv/Scripts/python.exe core/devtools/smarttest.py check mobile
./.venv/Scripts/python.exe core/devtools/smarttest.py check all
```

所有 `check` 都先验证产品边界。Client 执行编译和仓库入口测试；Web 执行后端 pytest 以及前端 test/lint/build；Mobile 执行 Gradle unit tests；`check all` 依次检查三个产品端。

### 打包

```powershell
./.venv/Scripts/python.exe core/devtools/smarttest.py package client
./.venv/Scripts/python.exe core/devtools/smarttest.py package web
./.venv/Scripts/python.exe core/devtools/smarttest.py package mobile
./.venv/Scripts/python.exe core/devtools/smarttest.py package all
```

- `package client`：复用 Client 自有脚本生成 Windows Client 安装程序和 Tool 便携 ZIP；
- `package web`：生成 Web 静态分发资源；
- `package mobile`：构建并平台签名 Android APK；
- `package all`：固定按 `client -> web -> mobile` 复用三个单产品入口。

正式产物只位于：

```text
dist/mobile/app-debug-platform.apk
dist/client/SmartTest-Setup.exe
dist/tool/SmartTestTool-<version>-windows-x64.zip
```

Client 和 Tool 的中间 runtime 分别位于 `build/client_runtime/`、`build/tool_runtime/`，不是发布产物。

## 版本与发布

`core/release/version.json` 是全局产品版本 owner，值必须使用 `MAJOR.MINOR.PATCH`。任何 `dev`、`check` 或 `package` 命令都不会自动修改版本。

准备新版本时手动修改一次，例如：

```json
{
  "version": "1.2.0"
}
```

先运行检查并提交普通代码；普通 push/PR 只触发检查，不打包、不改版本。发布时创建与文件内容精确匹配的 tag：

```powershell
git tag v1.2.0
git push origin v1.2.0
```

`v*` tag 触发 `.github/workflows/release.yml`。工作流会先校验 tag 等于 `v` 加 `version.json` 的版本；不匹配会在安装依赖和打包之前明确失败。匹配后，带 `[self-hosted, Windows, X64, smarttest-release]` 标签的公司 Runner 创建固定 Python 环境，检查机器级签名配置，按 `package all` 生成并上传 APK、Client 安装程序和 Tool ZIP。Web 不参与发布打包。

Runner 注册凭据和签名材料不得写入仓库、workflow 或日志。

## 来源与许可证

桌面界面复用了 QML FluentUI 项目的组件和设计模式，并继续遵循仓库中的许可证声明。Fluent Design 参考：[Windows design guidelines](https://learn.microsoft.com/windows/apps/design/) 和 [WinUI Gallery](https://github.com/microsoft/WinUI-Gallery)。仓库代码许可证见 [LICENSE](LICENSE)。
