# SmartTest Wi-Fi Database Backend

独立安装与启动：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn smarttest_web.app:app --app-dir web/backend --host 127.0.0.1 --port 8000
```

数据库连接全部来自环境变量：`WIFI_DB_HOST`、`WIFI_DB_PORT`、`WIFI_DB_USER`、`WIFI_DB_PASSWORD`、`WIFI_DB_NAME`、`WIFI_DB_POOL_SIZE`。其中 host、user、password、name 必填，不提供默认凭据。`GET /health` 不访问数据库；数据库配置仅在 Database API 首次使用时解析。

服务只提供 `GET /health`、`GET /api/filters`、`GET /api/performance`。数据库 owner 仅接受单条参数化 `SELECT`/只读 `WITH`，不建表、不迁移或写入数据。
