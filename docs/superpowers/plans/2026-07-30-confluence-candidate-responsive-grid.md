# Confluence Candidate Responsive Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将候选项目改为 1–3 列响应式网格，并让 Project Collection 高度按最多 6 行内容自动调整。

**Architecture:** QML 继续拥有纯展示布局。候选数据和选择契约保持不变；网格根据视口宽度计算列数，根据候选数量和测量行高计算可见高度，超过上限后仅纵向滚动。

**Tech Stack:** QML、PySide6、pytest。

## Global Constraints

- 不修改 Confluence 发现、过滤、缓存、计划、审查和报告逻辑。
- 不产生横向滚动、裁切或重叠。
- QML 资源修改后重建 `resource_rc.py`。
- 当前功能验收前不提交。

---

### Task 1: 响应式网格与动态高度

**Files:**
- Modify: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- Consumes: `view.candidateProjects` 和现有候选选择 slot。
- Produces: `candidateColumnCount`、`candidateVisibleRowCount` 及动态候选区域高度。

- [ ] **Step 1: 写失败的 QML runtime 测试**

覆盖 `520/1000/1500px` 的 `1/2/3` 列，以及 `0/1/6/18/40` 个候选项目的高度、滚动、矩形不相交和选择行为。

- [ ] **Step 2: 运行测试并确认因当前固定单列布局失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -k "confluence and candidate" -q
```

Expected: FAIL，列数或动态高度断言不满足。

- [ ] **Step 3: 实现最小响应式布局**

在 QML 中按 `800/1200px` 断点计算列数；按实际项目高度组织网格行；候选区最多展示 6 行，超过后仅启用纵向滚动。

- [ ] **Step 4: 运行聚焦测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_confluence_audit_bridge.py -q
```

Expected: PASS。

- [ ] **Step 5: 重建资源并完成回归**

Run:

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui/example/imports/resource.qrc -o ui/example/imports/resource_rc.py
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_confluence_audit_bridge.py testing/self_tests/ui/test_owned_ui_translations.py -q
.\.venv\Scripts\python.exe -m compileall -q ui/example/bridge/ConfluenceAuditBridge.py
git diff --check
```

Expected: 全部退出码 `0`。
