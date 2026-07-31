# Confluence 项目周审 Excel 矩阵实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Project Weekly Audit 的活跃报告链路改为 Excel 审查矩阵，每个项目一行、每个邮件关注点一列，单元格仅输出“已更新 / 未更新 / 格式有误”。

**Architecture:** `support/confluence_audit` 继续拥有项目发现和更新时间事实，统一把页面事实归一为三态矩阵；`support/report` 作为全局报告层拥有 XLSX 写出能力；`ConfluenceAuditBridge` 只负责调用导出接口并向 QML 暴露结果。现有内容规则、AI、Playwright 证据和 PDF 实现保留，但不进入当前审查或导出链路。

**Tech Stack:** Python、现有 Confluence 集成、仓库已声明的 Excel 依赖、PySide6/QML、pytest。

## Global Constraints

- 审查窗口保持周一 00:00（含）至周五 00:00（不含），等价于周四 24:00 前。
- 不读取或判断更新内容，不调用静态内容规则、DeepSeek、附件内容检查、Playwright 截图或 PDF 导出。
- 单元格只允许“已更新”“未更新”“格式有误”；页面不存在、级联错误、历史不全、权限/结构/接口原因导致获取不到均为“格式有误”。
- 邮件第 1、2 项不生成关注列；同一页面的多个关注点共享该页面的更新时间状态。
- 保留现有 PDF、HTML、证据和 AI 源码，不删除，仅断开 Project Weekly Audit 的活跃调用入口。
- 复用现有全局报告 owner 和已声明依赖，不另建项目专用 XLSX 底层写出机制。
- 不提交、重置或覆盖工作区已有改动。

---

### Task 1: 三态页面审查矩阵

**Files:**
- Modify: `support/confluence_audit/models.py`
- Modify: `support/confluence_audit/service.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Consumes: `AuditPeriod`、项目页面发现结果及页面版本时间。
- Produces: 每个项目对应固定关注点的审查结果，状态值严格归一为 `updated`、`not_updated`、`invalid_format`，展示文字由报告层映射。

- [ ] **Step 1: 写失败测试**

```python
def test_update_only_matrix_uses_exact_three_states_and_marks_unreadable_as_invalid():
    """覆盖窗口内更新、窗口内未更新、页面不存在/读取失败三种事实。"""
```

断言同一页面的多个关注点状态相同；断言内容正文、AI、附件和证据收集接口没有被调用。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_service.py -q`

Expected: FAIL，现有 finding 状态仍为 passed/failed/unknown 或缺少固定关注点矩阵。

- [ ] **Step 3: 最小实现**

在现有模型 owner 中定义三态枚举和固定关注点描述；在 `ConfluenceAuditService` 的更新时间链路中仅根据页面可获取性与审查窗口内版本时间生成矩阵。不得启用 `rules.py`、`ai_review.py`、附件正文或 evidence collector。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_service.py -q`

Expected: PASS。

### Task 2: 全局 Excel 报告写出

**Files:**
- Create or extend existing owner: `support/report/xlsx.py`
- Modify: `support/report/__init__.py`
- Modify: `support/confluence_audit/report.py`
- Test: `testing/self_tests/support/test_report.py`
- Test: `testing/self_tests/support/test_confluence_audit_pdf.py`

**Interfaces:**
- Consumes: Task 1 的项目矩阵和项目元数据。
- Produces: `export_project_audit_xlsx(batch, output_path) -> Path`。

- [ ] **Step 1: 写失败测试**

```python
def test_project_audit_xlsx_has_one_project_per_row_and_fixed_attention_columns(tmp_path):
    """验证基础列、12 个关注点列、中文三态及项目超链接。"""
```

关注点列固定为：

```text
Project Status Report.Highlights
Project Status Report.Impact Issue
Test Information.每周信息
Test Information.测试结果Summary
Test Information.Task完成情况
Test Information.Block QA问题状态
Test Plan.测试计划
Test Environment Setup and Precautions.环境搭建方式
Test Environment Setup and Precautions.常用Log信息
Summary of Experience and Typical Cases.经验总结
Summary of Experience and Typical Cases.典型案例
Test Report Store.测试报告
```

基础列固定为：年份、项目名、Support Mode、Project Status、审查周期、项目链接。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_report.py testing/self_tests/support/test_confluence_audit_pdf.py -q`

Expected: FAIL，尚无 Project Audit XLSX 导出接口，旧测试仍以 PDF 为活跃出口。

- [ ] **Step 3: 最小实现**

扩展 `support/report` 中现有 Excel owner；使用仓库已声明并可打包的成熟依赖写出单工作表 `Project Weekly Audit`。首行冻结、启用筛选、标题自动换行、状态使用稳定颜色，并为项目链接写入可点击超链接。`support/confluence_audit/report.py` 只组装业务矩阵并调用全局 XLSX owner；保留 PDF 函数但不再作为活跃入口。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_report.py testing/self_tests/support/test_confluence_audit_pdf.py -q`

Expected: PASS。

### Task 3: UI 导出入口切换为 Excel

**Files:**
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Modify: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`
- Test: `testing/self_tests/ui/test_owned_ui_translations.py`

**Interfaces:**
- Consumes: `export_project_audit_xlsx(...)`。
- Produces: QML 可调用的 `exportExcel()` slot，以及成功/失败状态文字。

- [ ] **Step 1: 写失败测试**

```python
def test_export_excel_uses_xlsx_slot_and_never_calls_pdf(monkeypatch, tmp_path):
    """导出按钮必须调用 XLSX 接口，且当前路径不触发 PDF/Playwright。"""
```

同时断言 QML 显示 `Export Excel`，不再显示活跃的 `Export PDF` 按钮。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_confluence_audit_bridge.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: FAIL，当前 bridge/QML 仍暴露 PDF 导出。

- [ ] **Step 3: 最小实现**

把 bridge 活跃 slot 和 QML 按钮切换到 Excel；固定 UI 文案同步维护中英文翻译。旧 PDF 函数可保留为未调用兼容实现，不在 QML 暴露。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_confluence_audit_bridge.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: PASS。

### Task 4: 回归、样例工作簿与清理

**Files:**
- Modify only if required by prior tasks: `support/packaging/pyinstaller/main.spec`
- Test: `testing/self_tests/support/test_confluence_audit_command.py`
- Test: `testing/self_tests/support/test_confluence_audit_scheduler.py`

**Interfaces:**
- Consumes: Task 1–3 的完整链路。
- Produces: 可打开的样例 XLSX 和无 PDF/内容审阅活跃调用的验证证据。

- [ ] **Step 1: 运行 Project Audit 范围回归**

Run: `.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_*.py testing/self_tests/ui/test_confluence_audit_bridge.py testing/self_tests/ui/test_owned_ui_translations.py -q`

Expected: PASS。

- [ ] **Step 2: 生成最小样例并检查工作簿**

使用测试 fixture 导出包含三种状态的 XLSX，重新读取后验证工作表名、列顺序、行数、状态集合和项目超链接；再用可用表格渲染能力做一次视觉检查，确认标题和项目名不截断。

- [ ] **Step 3: 清理并检查差异**

Run: `git diff --check`

Expected: exit code 0；无临时打印、无新内容审阅调用、无删除 PDF/Playwright 实现、无无关文件。

## 自审结论

- 需求覆盖：三态、获取不到归入格式有误、邮件第 1/2 项排除、每项目一行、关注点列、Excel、旧 PDF/截图/内容审阅闲置均有对应任务。
- 占位符检查：无 TBD、TODO 或未定义的“后续处理”。
- 接口一致性：Task 2 产出 `export_project_audit_xlsx`，Task 3 仅消费该接口；业务三态由 Task 1 统一拥有。
