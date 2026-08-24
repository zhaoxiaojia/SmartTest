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

本目录基于 CoreUI Free Bootstrap Admin Template 的最小壳进行迁移，采用 MIT 许可证，详见 `LICENSE`。图表使用 Chart.js，Excel 导出使用 ExcelJS，PDF 导出使用 jsPDF；依赖及版本由 `package.json` 和 `package-lock.json` 声明。产品范围只有空 Home 和 Wi-Fi Database 的 Peak Throughput、RVR、RVO。
