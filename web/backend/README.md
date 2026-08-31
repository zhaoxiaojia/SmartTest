# SmartTest Wi-Fi Database Backend

独立安装与启动：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn smarttest_web.app:app --app-dir web/backend --host 127.0.0.1 --port 8000 --no-access-log
```

数据库连接全部来自环境变量：`WIFI_DB_HOST`、`WIFI_DB_PORT`、`WIFI_DB_USER`、`WIFI_DB_PASSWORD`、`WIFI_DB_NAME`、`WIFI_DB_POOL_SIZE`。其中 host、user、password、name 必填，不提供默认凭据。`GET /health` 不访问数据库；数据库配置仅在 Database API 首次使用时解析。

服务提供健康检查、Wi-Fi Database 查询，以及 `/api/report-workspaces/{source}`
下的只读报告列表、正文与下载接口。数据库 owner 仅接受单条参数化
`SELECT`/只读 `WITH`，不建表、不迁移或写入数据。

Jira 工作台在用户点击 Start 后复用 Core 确定性审查，成功时自动生成原格式 XLSX，
通过统一 Download 按钮下载。Confluence Apply 加载所选项目详情，Review 按日期窗口
手动审查并生成每产品线 XLSX 的 ZIP。页面不自动执行审查。

`/api/auth/login|session|logout|logout-all` 复用 Client 同一 Core LDAP owner。浏览器只持有
HTTP-only/Secure 会话 token，SQLite 只保存 token 哈希与账号身份，会话按最后活动时间
滑动保留 90 天并支持多设备独立登录。服务端凭据在 Windows 使用 Credential Manager；
Linux 使用 `cryptography` AEAD 加密后写入同一 SQLite，32 字节主密钥须以 URL-safe Base64
配置在 `SMARTTEST_WEB_CREDENTIAL_KEY`，主密钥不写入数据库。重启后 Jira/Confluence
复用当前 session 的服务端凭据。`/api/preferences/{scope}` 保存认证账号的非敏感页面偏好，
支持跨设备读取、批量更新与 scope 重置。Jira/Confluence 当前态缓存使用 SQLite；
Confluence 切换账号先读取该账号已确认可见的缓存，再在进入页面时后台获取一次
四产品线动态目录。详情与审查仅手动触发，不周期刷新；403 只撤当前账号映射，保留共享数据。
