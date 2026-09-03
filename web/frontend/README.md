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

本目录使用 FAE QA Data Center 自有命名的顶部导航与明暗主题，模板来源和许可说明见 `TEMPLATE_ORIGIN.md`。Dashboard、Projects、Inbox、Analytics、Settings 和 Login 当前保留完整页面内容与交互。`/projects.html` 从 Core 当前项目事实绘制动态筛选、Current Stage 项目看板及 QA 责任汇总，并支持手动周审查与报告下载；`/jira.html` 按 JQL、Issue URL 或 Filter URL 手动启动 Jira 审查，成功后通过统一下载机制获取自动生成的报告。Wi-Fi Data 包含 Peak Throughput、RVR、RVO。图表使用 Chart.js，Excel 导出使用 ExcelJS，PDF 导出使用 jsPDF；依赖及版本由 `package.json` 和 `package-lock.json` 声明。Wi-Fi 筛选状态按 datatype 保存在浏览器会话中；查询前必须选择至少一个 Test Report。Vite 开发服务器将 `/api` 代理到 `http://127.0.0.1:8000`，FastAPI 控制台会打印实际 API 请求。
