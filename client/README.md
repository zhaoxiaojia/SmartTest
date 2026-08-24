# 桌面客户端

`client/` 是 Windows QML 桌面端的目标目录，负责页面、Qt Bridge、本地交互和桌面打包。

阶段一不迁移现有源码：桌面入口仍为仓库根目录的 `main.py`，QML 和 Bridge 仍位于 `ui/`。后续迁移后，桌面端可直接调用 `core/`，且不得以 Web 后端可用作为本机运行前提。
