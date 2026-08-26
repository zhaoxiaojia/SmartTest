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

Jira 工作台只读取 Client 已导出的 XLSX，默认读取用户 `Downloads` 下的
`jira_format_audit_*.xlsx`；服务器部署时可通过 `SMARTTEST_JIRA_REPORT_DIR`
指定共享目录。Jira 列表接口的 `jql` 参数只与 Client 导出中保存的“JQL 查询条件”匹配，
不会使用 Web 凭据访问 Jira，也不会启动新的审查。

`/api/auth/login|session|logout` 复用 Client 同一 Core LDAP owner。浏览器只持有
HTTP-only/Secure 会话 cookie；账号、临时密码和 LDAP 头像仅保存在后端进程内，
退出、过期或服务重启即清除。Confluence 项目事实查询优先读取现有本地快照；
只有无快照且当前会话已登录，或显式调用刷新接口时，才复用
`ConfluenceClient + refresh_project_facts` 获取并保存快照。
