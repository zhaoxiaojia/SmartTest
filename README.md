# SmartTest (Forked UI Base)

## 仓库结构

SmartTest 正在按已批准的多端目录设计分阶段重构。四个产品目录及固定依赖方向如下：

```text
client ---------------------> core
web/frontend -> web/backend -> core
mobile ------> web/backend -> core
```

- `client/`：Windows QML 桌面客户端；
- `core/`：不依赖任何端的唯一共享业务核心；
- `web/`：Web 前端与后端，前端不得直接调用 `core/`；
- `mobile/`：Android/移动端及平台专属能力。

当前桌面入口位于 `client/app/main.py`，QML 位于 `client/app/ui/`，共享核心位于 `core/`，Android 工程位于 `mobile/android/`。仓库根目录统一入口为：

```powershell
python support/smarttest.py dev client|web|mobile|all
python support/smarttest.py check client|web|mobile|all
python support/smarttest.py package client|tool|mobile|all
```

`package all` 固定执行 `mobile -> client -> tool` 并复用三个既有打包脚本；Web 只参与开发和检查，`package web` 会明确失败。`dev web/all` 报告 Web API 与前端地址，任一长期进程失败时会终止同组进程并传递退出码。

普通 push/PR 只运行 `.github/workflows/ci.yml` 的目录路由检查。仅 `v*` 标签触发 `.github/workflows/release.yml`，并要求标签为 `[self-hosted, Windows, X64, smarttest-release]` 的公司 Runner；发布构建上传签名 APK、Client 安装程序和 Tool zip，不打包 Web。

构建机的 Inno Setup、Android SDK/JDK、Node/Python、签名材料和 Runner 凭据由机器本地维护。发布工作流会用仓库的固定依赖清单创建全新的 `.venv`，不依赖开发工作区。Runner 注册 token 不得写入仓库或日志。

签名材料应放在仅构建机可访问的稳定目录（本机约定为 `C:\SmartTestBuild\signing`），并保持 `prebuilts/sdk/tools/lib/signapk.jar`、`build/target/product/security/platform.x509.pem`、`build/target/product/security/platform.pk8` 结构。管理员设置机器级环境变量后，重新启动 Runner 服务使其继承该变量：

```powershell
[Environment]::SetEnvironmentVariable('SMARTTEST_SIGNAPK_DIR', 'C:\SmartTestBuild\signing', 'Machine')
```

发布工作流在创建 Python 环境和打包之前验证该变量及三个文件；缺失时会停止且不会输出凭据内容。

<div align=center>
  <img width=64 src="doc/preview/fluent_design.svg">
</div>

<h1 align="center">
  QML FluentUI 
</h1>
<p align="center">
  A fluent design component library for Qt QML.
</p>

![win-badge] ![ubuntu-badge] ![macos-badge] ![release-badge] ![download-badge] ![download-latest]

<p align="center">
English | <a href="README_zh_CN.md">简体中文</a>
</p>
<div align=center>
  <img src="doc/preview/demo_large.png">
</div>

## Requirements
+ Python 3.11

## ⚽ Get started
+ run `example` program.

+ Build

```bash
python ./script-init-venv.py
python ./script-start.py
python ./script-build-nuitka.py
```

## 📑 Documentations

(Work in progress...🚀)

## Supported components

|Catalog|Detail|Notes / Demos|
|:----:|:----:|:----:|
|FluApp|The initial entry of the program|Router supported(SPA)|
|FluWindow|Frameless Window|*This only works on windows|
|FluAppBar|Title bar on top of the window|Drag, minimize, maximize and close are supported.|
|FluText|Common text||
|FluButton|Common button|![btn](doc/preview/demo_standardbtn.png) |
|FluFilledButton|Filled button|![filledbtn](doc/preview/demo_filledbtn.png)|
|FluTextButton|Text button|![textbtn](doc/preview/demo_textbtn.png)|
|FluToggleButton|Toggle buttons|![togglebtn](doc/preview/demo_toggle_btn.png)|
|FluIcon|Common icon|![icons](doc/preview/demo_icon.png)|
|FluRadioButton|radio button|![radiobtn](doc/preview/demo_radiobtn.png)|
|FluTextBox|Single-line input box|![textbox](doc/preview/demo_textbox.png)|
|FluMultiLineTextBox|Multi-lines input area|![textarea](doc/preview/demo_multiline_textbox.png)|
|FluToggleSwitch|toggle switch|![toggleswitch](doc/preview/demo_toggle_switch.png)|


View more [`here`](doc/md/all_components.md)!

## Reference
+ Windows design guidelines: https://learn.microsoft.com/en-us/windows/apps/design/
+ WinUI Gallery: https://github.com/microsoft/WinUI-Gallery


## License

This FluentUI library currently licensed under [MIT License](./License)

