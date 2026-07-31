# SmartTest 按输出格式拆分报告架构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除混合 `run_report.py`，将 JSON、HTML、PDF、Excel 输出能力收敛到 `support/report` 的格式目录，并让 Jira/Confluence Excel 统一复用公共驱动。

**Architecture:** format-neutral 合同进入 `core.py`/`paths.py`；JSON store、HTML run renderer、PDF renderer/run exporter、Excel workbook/table 各自成为单一 owner。业务报告保留内容与布局，所有内部 import 一次性迁移，不保留旧路径 wrapper。

**Tech Stack:** Python、pytest、openpyxl、PySide6 QtWebEngine、pathlib

## Global Constraints

- 严格遵循 `docs/superpowers/specs/2026-07-31-output-format-report-architecture-design.md`。
- 保持 `support.report` 顶层现有业务 API、报告 schema、HTML/CSS、Jira/Confluence Excel 可见输出不变。
- 不新增依赖、兼容 facade、万能声明模型、业务特例、临时诊断或实现形状测试。
- 当前设计/计划文件为用户所有；保护所有非本任务改动。
- TDD 必须先观察新 API/owner 测试因缺失而 RED，再写生产实现。
- Mason 不提交、push、merge 或委派；交付提交由 Atlas 在 Coco 功能确认后执行。

---

### Task 1: 建立新格式包的行为测试

**Files:**
- Modify: `testing/self_tests/support/test_report.py`
- Modify: `testing/self_tests/support/test_confluence_audit_report.py` only if public import changes need direct coverage
- Modify: existing Jira audit workbook tests only when durable output assertions are missing

**Interfaces:**
- Produces expected imports: `support.report.json.ReportStore`、`support.report.html` run APIs、`support.report.pdf` run/renderer APIs、`support.report.excel` workbook/table APIs。

- [ ] 新增公共 Excel Workbook 驱动的真实文件测试：callback 创建两个 Sheet，公共清理函数处理非法字符，输出可被 `openpyxl.load_workbook()` 读取，返回绝对路径。
- [ ] 新增格式 package import 测试，只验证可调用公共行为，不 grep 源码或断言私有文件形状。
- [ ] 运行 focused test，确认 RED 原因是新 package/API 尚不存在。

### Task 2: 迁移 core、paths 和 JSON store

**Files:**
- Create: `support/report/core.py`
- Create: `support/report/paths.py`
- Create: `support/report/pipeline.py`
- Create: `support/report/json/__init__.py`
- Create: `support/report/json/store.py`
- Modify: `support/report/__init__.py`
- Delete: `testing/reporting/store.py`
- Delete: `testing/reporting/__init__.py` only if package becomes empty and has no callers
- Modify direct imports/tests found by scoped `rg`

**Interfaces:**
- `core.py`: existing `REPORT_SCHEMA_VERSION`、`build_run_report`、`duration_text`、`report_file_stem` and private normalization helpers。
- `json/store.py`: `ReportStore.save/list_reports/load/path_for/load_by_path` preserving behavior，且不依赖 HTML/paths。
- `paths.py`: HTML/PDF path functions without rendering side effects。
- `pipeline.py`: `save_run_report()` 的 normalize → JSON save → HTML generate 编排。

- [ ] Move format-neutral functions without changing behavior or names.
- [ ] Move `ReportStore` and update consumers from `testing.reporting.store` to `support.report.json`.
- [ ] Keep the existing JSON serializer owner; do not duplicate read/write implementation.
- [ ] Run report store/model/path focused tests and compile checks.

### Task 3: 迁移 HTML 与 PDF

**Files:**
- Create: `support/report/html/__init__.py`
- Create: `support/report/html/run.py`
- Create: `support/report/pdf/__init__.py`
- Create: `support/report/pdf/renderer.py`
- Create: `support/report/pdf/run.py`
- Modify: `support/report/__init__.py`
- Delete later: `support/report/pdf.py`
- Delete later: `support/report/run_report.py`

**Interfaces:**
- HTML: existing `render_html_report`、`generate_html_report`、`report_html_url` and section render helpers。
- PDF renderer: existing `PdfRenderError`、`render_html_to_pdf` and internal page adapter/render flow。
- PDF run: existing `export_pdf_report` orchestration。

- [ ] Move HTML/CSS and renderer helpers verbatim except required imports; no visible or semantic redesign.
- [ ] Move generic QtWebEngine PDF driver without adding run-report knowledge.
- [ ] Move run PDF orchestration and reuse HTML generation; no template duplication.
- [ ] Update top-level re-exports and internal imports.
- [ ] Run HTML rendering, PDF adapter/orchestration, path and public API tests.

### Task 4: 建立 Excel owner 并收敛 Jira/Confluence

**Files:**
- Create: `support/report/excel/__init__.py`
- Create: `support/report/excel/workbook.py`
- Create: `support/report/excel/table.py`
- Modify: `support/report/__init__.py`
- Modify: `support/jira_integration/audit/exporter.py`
- Modify: `support/confluence_audit/report.py`
- Delete later: `support/report/xlsx.py`
- Modify durable report/Jira/Confluence tests as required

**Interfaces:**
- `workbook.py`: `clean_excel_value(value)` and `write_excel_workbook(output_path, populate) -> Path`。
- `table.py`: preserve `write_xlsx_table()` and `write_xlsx_sections()` signatures/output。
- Jira exporter consumes workbook driver and cleaner; business layout remains local。

- [ ] Implement Workbook driver minimally to pass Task 1 RED test, with one atomic-save owner and exception cleanup.
- [ ] Move common table/sections code; preserve styles, freeze panes, filters, hyperlinks and widths.
- [ ] Change Confluence import to `support.report.excel`.
- [ ] Refactor Jira exporter to callback-populate its two Sheets and call common driver; remove direct `Workbook`、`ILLEGAL_CHARACTERS_RE`、`os`、`tempfile` and private clean/save code.
- [ ] Run Excel common, Jira reader-visible contract and Confluence report tests.

### Task 5: 删除旧模块并完成全量迁移

**Files:**
- Delete: `support/report/run_report.py`
- Delete: `support/report/pdf.py`
- Delete: `support/report/xlsx.py`
- Delete: `testing/reporting/store.py`
- Delete empty `testing/reporting/__init__.py` when applicable
- Modify all remaining internal imports

- [ ] Use `rg` to prove no internal import references old modules or `testing.reporting.store`.
- [ ] Verify no Jira exporter direct ownership of Workbook construction, illegal-character cleaning, temp files or atomic save.
- [ ] Verify public `support.report` imports used by RunBridge、ReportBridge、TestContext remain stable.
- [ ] Remove empty packages, stale `__pycache__` only if untracked/ignored and generated during validation; do not touch unrelated caches.

### Task 6: 最终验证与质量审查

- [ ] Run report, Jira audit, Confluence audit, RunBridge and ReportBridge focused suites.
- [ ] Run `compileall -q support/report support/jira_integration/audit support/confluence_audit testing/test_context.py ui/example/bridge/RunBridge.py ui/example/bridge/ReportBridge.py`.
- [ ] Run `git diff --check`.
- [ ] Review scoped diff for duplicate helpers, thin re-export layers beyond explicit package APIs, HTML/CSS changes, test implementation-shape assertions and unrelated edits.
- [ ] Report changed/deleted files、RED/GREEN commands and exit codes、functional/quality verdict、reuse decision、net production code、relevant git status、limitations and task identity。
- [ ] Do not commit; wait for Coco functional confirmation.

### Task 7: 增加通用图片折线图格式

**Files:**
- Create: `support/report/image/__init__.py`
- Create: `support/report/image/style.py`
- Create: `support/report/image/line.py`
- Modify: `support/report/__init__.py`
- Modify: `support/scripts/script-init-venv.py`
- Modify: `support/packaging/pyinstaller/main.spec`
- Modify: `testing/self_tests/support/test_report.py`

- [x] 先以真实 PNG、输入校验和 `rcParams` 隔离测试建立 RED。
- [x] 实现 `LineSeries`、集中样式 owner 和 `render_line_chart()`。
- [x] 以 Artist 行为测试保护左侧标题、右侧 KPI 和高亮 series 末点强调。
- [x] 固定 Matplotlib 3.10.5，并同步开发环境与 PyInstaller 依赖入口。
- [x] 保持图片能力独立，不修改 Jira、Confluence 或 Excel 业务行为。
- [ ] 运行 focused 与相关报告回归、compile/import smoke 和 `git diff --check`。
