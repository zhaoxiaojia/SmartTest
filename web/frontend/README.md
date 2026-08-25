# SmartTest Web Frontend

独立开发：

```powershell
npm install
npm run dev
```

质量检查：

```powershell
npm test
npm run lint
npm run build
```

浏览器前端默认调用同源 `/api/filters` 和 `/api/performance`，延续旧 Wi-Fi Database 的查询参数契约。部署时可在加载入口前设置 `globalThis.SMARTTEST_API_BASE` 指向 Web API 根路径。API 不可用时页面显示明确状态，不使用模拟数据。

本目录基于 CoreUI Free Bootstrap Admin Template 的最小壳进行迁移，采用 MIT 许可证，详见 `LICENSE`。图表使用 Chart.js，Excel 导出使用 ExcelJS，PDF 导出使用 jsPDF；依赖及版本由 `package.json` 和 `package-lock.json` 声明。Home 内容区留空，侧栏仅显示 Wi-Fi Database 入口；进入后侧栏显示 Peak Throughput、RVR、RVO。筛选状态按 datatype 保存在浏览器会话中；查询前必须选择至少一个 Test Report。Vite 开发服务器将 `/api` 代理到 `http://127.0.0.1:8000`，FastAPI 控制台会打印实际 API 请求。
