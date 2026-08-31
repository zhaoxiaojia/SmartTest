# 移动端

`mobile/` 是 Android/移动端的目标目录，负责移动端界面、APK runner、系统权限和平台专属集成。

Android 工程位于 `mobile/android/`。Gradle、平台签名、priv-app 安装和 APK runner 均由该目录及既有仓库支持脚本负责；package id、case id、参数协议和步骤身份保持原有契约。后续移动端的远程业务能力通过 Web API 使用 `core/`。
