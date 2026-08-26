# Web 端

`web/` 是 Web 前端与后端的产品边界。`frontend/` 提供 SmartTest 顶部导航、主题体系和 Wi-Fi Data；`backend/` 提供对应的 FastAPI 只读 API。

依赖方向固定为 `web/frontend -> web/backend -> core`：浏览器前端只调用 Web API，不得直接访问 `core/`；Web 后端负责传输和请求编排，核心业务必须复用 `core/`，不得复制实现。

前端保留完整的 Dashboard、Projects、Inbox、Analytics、Settings 和 Login 模板页面；顶部导航新增 Wi-Fi Data 入口，进入后提供 Peak Throughput、RVR、RVO 三个直接入口。模板页面当前保留示例内容，后续按模块接入 SmartTest 真实业务。开发服务器会将前端 `/api` 请求代理到本机 FastAPI `8000` 端口。

开发命令分别见 `frontend/README.md` 和 `backend/README.md`。前端默认调用同源 `/api/filters` 与 `/api/performance`；API 未启动或数据库未配置时页面会明确显示 unavailable 状态，不生成模拟数据。
