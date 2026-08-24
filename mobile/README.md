# 移动端

`mobile/` 是 Android/移动端的目标目录，负责移动端界面、APK runner、系统权限和平台专属集成。

阶段一不迁移现有源码：Android 工程仍位于 `android_client/`，原有 Gradle、签名、安装及桌面集成路径保持不变。后续移动端的远程业务能力通过 Web API 使用 `core/`。
