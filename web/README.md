# Web 端

`web/` 是 Web 前端与后端的产品边界。当前 `frontend/` 已迁入最小 CoreUI Web 壳和 Wi-Fi Database；后端仍按后续迁移进度建立，不预建空业务模块。

依赖方向固定为 `web/frontend -> web/backend -> core`：浏览器前端只调用 Web API，不得直接访问 `core/`；Web 后端负责传输和请求编排，核心业务必须复用 `core/`，不得复制实现。

前端当前仅包含空 Home，以及 Wi-Fi Database 的 Peak Throughput、RVR、RVO 三个入口。旧首页业务和其他旧页面不属于迁移范围。

开发命令见 `frontend/README.md`。前端默认调用同源 `/api/filters` 与 `/api/performance`；API 未启动时页面会明确显示 unavailable 状态，不生成模拟数据。
