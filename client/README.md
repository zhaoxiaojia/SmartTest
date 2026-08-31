# 桌面客户端

`client/` 是 Windows QML 桌面端的目标目录，负责页面、Qt Bridge、本地交互和桌面打包。

桌面入口位于 `client/app/main.py`，QML、FluentUI 和 Bridge 位于 `client/app/ui/`。从仓库根目录运行 `python client/app/main.py`；桌面端保持本机独立运行，不以 Web 后端可用作为前提。
