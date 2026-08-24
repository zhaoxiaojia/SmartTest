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

当前桌面入口位于 `client/app/main.py`，QML 位于 `client/app/ui/`，共享核心位于 `core/`，Android 工程位于 `mobile/android/`。从仓库根目录运行 `python client/app/main.py` 启动桌面端；目录边界可通过 `python support/ci/check_product_boundaries.py` 检查。

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

