# SmartTest 按输出格式拆分报告架构设计

## 目标

将当前混合在 `support/report/run_report.py`、`pdf.py`、`xlsx.py` 和 `testing/reporting/store.py` 中的报告能力，按 JSON、HTML、PDF、Excel 输出格式收敛到 `support/report/`。测试运行报告、Jira 审查报告和 Confluence 审查报告继续拥有各自业务内容，但底层格式驱动统一由 `support/report` 提供。

本次删除旧混合模块和旧内部导入路径，不保留薄兼容 wrapper；`support.report` 顶层已经对 UI/业务调用方公开的稳定 API 保持不变。

## 目标结构

```text
support/report/
├─ core.py
├─ paths.py
├─ pipeline.py
├─ json/
│  ├─ __init__.py
│  └─ store.py
├─ html/
│  ├─ __init__.py
│  └─ run.py
├─ pdf/
│  ├─ __init__.py
│  ├─ renderer.py
│  └─ run.py
├─ excel/
│  ├─ __init__.py
│  ├─ workbook.py
│  └─ table.py
└─ __init__.py
```

## 职责

### `core.py`

拥有与输出格式无关的报告合同：

- `REPORT_SCHEMA_VERSION`；
- 测试运行报告模型标准化；
- run id、结束时间、状态、统计和 DUT 结果归一；
- duration 文本；
- 安全文件名和报告文件 stem。

`core.py` 不读写文件、不构建 HTML、不依赖 Qt、UI 或测试运行时。

### `paths.py`

拥有报告文件路径组合：HTML、PDF 路径。路径生成依赖 core 的文件 stem 和 JSON store 的读取结果，不渲染内容。

### `pipeline.py`

唯一拥有测试运行报告保存编排：标准化报告、写入 JSON store，再生成对应 HTML。JSON store 不反向依赖 HTML 或 paths。

### `json/store.py`

拥有报告 JSON 的保存、读取、列表和 `run_id` 路径。现有 `testing/reporting/store.py` 的能力迁移至此并删除旧模块。JSON 是报告共享合同；HTML、PDF、Excel 都不是报告输入数据。

JSON store 使用现有稳定 JSON 读写 owner，不复制 serializer，也不依赖 UI Bridge。若当前 `ui/jsonTool.py` 是仓库唯一 JSON owner，则直接复用；本次不新建第二套 JSON 序列化机制。

### `html/run.py`

拥有测试运行报告的 HTML 生成、HTML URL 恢复和所有 HTML section renderer。`report_html_url()` 从 JSON store 加载报告并重新生成缺失的 HTML，然后返回本地 URI。现有 HTML、CSS、颜色、DUT、case、step、log、failure analysis 和 metric 布局只迁移所有权，不改变可见样式、字段、排序和展开规则。

HTML renderer 消费标准化报告 dict，返回字符串或写入指定 HTML 路径；不保存 JSON、不生成 PDF。

### `pdf/renderer.py`

拥有通用 HTML → PDF 的 QtWebEngine 驱动、事件循环、超时和渲染错误。它不理解测试运行报告、Jira 或 Confluence 字段。

### `pdf/run.py`

拥有测试运行报告的 PDF 导出编排：定位或生成对应 HTML，再调用通用 PDF renderer。它不复制 HTML 模板。

### `excel/workbook.py`

拥有通用 Excel Workbook 基础设施：

- 创建 Workbook；
- 清理 Excel 非法字符；
- 在目标目录创建临时文件；
- 原子保存和异常清理；
- 返回解析后的输出路径。

业务填充通过一个小型 callback 完成，不建立通用 Workbook/Sheet/Cell 声明模型。

### `excel/table.py`

拥有现有通用单表和分段表格写入，包括基础表头、对齐、冻结、过滤、链接和通用列宽。它调用 `excel/workbook.py`，不复制保存逻辑。

## 业务报告边界

### 测试运行报告

```text
TestContext / RunBridge
  -> support.report 顶层 API
  -> core
  -> json.store
  -> html.run
  -> pdf.run / pdf.renderer
```

`testing/test_context.py` 继续产生运行快照，不拥有输出格式。`RunBridge` 和 `ReportBridge` 继续只调用 `support.report` 顶层 API。

### Jira 审查报告

```text
JiraAuditBridge
  -> support/jira_integration/audit/exporter.py
  -> Jira 双 Sheet、字段、样式、合并和命名
  -> support.report.excel.workbook
```

Jira exporter 不再直接导入 `Workbook`、`ILLEGAL_CHARACTERS_RE`、`os` 或 `tempfile`，也不再拥有原子保存和字符清理。Jira 专属 Sheet、行列、固定列宽、合并、过滤和文件重名规则留在 Jira business owner。

### Confluence 审查报告

```text
support/confluence_audit/report.py
  -> Confluence 分组和业务行
  -> support.report.excel.table
```

Confluence 只更新内部 import，输出内容和布局不变。

## API 与迁移

`support/report/__init__.py` 继续导出当前业务调用方使用的稳定 API，包括运行报告构建、保存、加载、列表、路径、HTML、PDF 和通用 XLSX table 能力。顶层只做明确公共 API re-export，不包含业务实现。

仓库内部 import 一次性迁移到新 owner：

- `.pdf` → `.pdf.renderer` 或 `.pdf` 明确导出；
- `support.report.xlsx` → `support.report.excel`；
- `testing.reporting.store.ReportStore` → `support.report.json.ReportStore`。

删除以下旧文件：

- `support/report/run_report.py`；
- `support/report/pdf.py`；
- `support/report/xlsx.py`；
- `testing/reporting/store.py`。

若 `testing/reporting/__init__.py` 删除旧 store 后为空且没有稳定外部职责，则一并删除空 package；不保留旧路径 facade。

## 错误处理

- JSON 读取损坏或非 dict 时沿用当前返回 `None` 的合同。
- 文件系统和保存错误不吞掉，由现有 Bridge 边界展示可操作错误。
- Excel callback 或保存失败时清理临时文件并原样传播异常。
- PDF 缺失 HTML 时先从 JSON 报告生成；报告不存在时保持现有 `FileNotFoundError`。
- PDF QtWebEngine 缺失、加载失败、打印失败或超时继续使用明确的 `PdfRenderError`。

## 依赖与复用

继续复用现有 `openpyxl`、PySide6 QtWebEngine 和 JSON owner，不新增第三方依赖。所有格式只保留一个底层驱动；业务 exporter 不复制 formatter、serializer、临时文件或原子保存机制。

## 测试与验收

实施遵循 TDD。先以新包 import 和公共 Workbook 驱动行为测试建立 RED，再移动最小实现并保持既有输出契约。

验收条件：

1. 目标目录结构存在，四个旧模块删除，仓库无旧内部 import。
2. `support.report` 既有顶层业务 API 可导入且行为不变。
3. 测试运行报告 JSON/HTML/PDF 的模型、路径、文件名和渲染输出不变。
4. Jira Excel reader-visible 契约、双 Sheet、样式、合并、列宽、冻结、过滤和重名行为不变。
5. Confluence Excel 分组、字段、链接和样式不变。
6. Jira exporter 不拥有 Workbook 创建、非法字符清理、临时文件或原子保存。
7. 报告、Jira audit、Confluence audit、Bridge 相关测试通过；变更模块 compileall 和 `git diff --check` 通过。
8. 不新增薄 wrapper、重复 helper、万能声明模型、临时诊断或实现形状测试。
9. 评审净生产代码增长；拆文件不应造成明显净增长，删除的重复 Excel 机制应抵消 package `__init__` 成本。

## 范围外

- 不改变任何报告视觉设计、字段、业务统计或 schema version。
- 不新增 CSV、Word 或新的业务导出按钮；图片仅提供独立的通用折线图格式能力。
- 不修改 Jira、Confluence 审查规则和数据模型。
- 不重建桌面安装包。

## 图片折线图扩展

`support/report/image/` 是通用图片输出 owner：`style.py` 集中管理以 `#4F8EF7`、`#2CB67D`、`#F59E0B` 开始的调色板、白色背景、无边框坐标区、alpha 0.15 的浅色虚线纵轴网格、2.8/3.0 的普通/高亮线宽、标记、无边框水平图例、20 度横轴旋转、11x5 英寸画布、220 绘制/保存 DPI，以及优先 Segoe UI 的跨平台字体回退；`line.py` 只负责校验折线数据并渲染 PNG。

公开接口为 `LineSeries(label, values, color=None, fill=False)` 与 `render_line_chart(labels, series, output_path, *, title="", highlight_series=None, kpi_label=None, style=DEFAULT_LINE_CHART_STYLE) -> Path`。标题位于顶部左侧；高亮 series 的最后一点使用更大的圆点和白色描边，其最新值与 `kpi_label` 一起显示在顶部右侧。为避免 KPI 值来源含糊，提供 `kpi_label` 但未指定 `highlight_series` 时抛出 `ValueError`。渲染器使用 Matplotlib `rc_context()` 隔离样式，不显示交互窗口，保存后始终关闭 figure。空标签、空 series、长度不一致或不存在的高亮 series 均抛出 `ValueError`。

该能力不接入 Jira、Confluence、Excel 或现有运行报告业务流。运行环境固定使用 `matplotlib==3.10.5`，沿用 `numpy==2.1.3` 和现有 Pillow，并在 PyInstaller 入口声明 Matplotlib。
