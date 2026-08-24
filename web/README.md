# Web 端

`web/` 是 Web 前端与后端的产品边界。后续按实际迁移进度创建 `frontend/`、`backend/` 和临时 `legacy/`，不预建空业务模块。

依赖方向固定为 `web/frontend -> web/backend -> core`：浏览器前端只调用 Web API，不得直接访问 `core/`；Web 后端负责传输和请求编排，核心业务必须复用 `core/`，不得复制实现。

阶段一不包含 Web 业务、API 或旧仓库代码。
