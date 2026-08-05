# Redmine 30% Compact Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Redmine-only 0.70 density trial that preserves the current layout and business behavior while visibly increasing the Issue list/detail viewport.

**Architecture:** Add one QML singleton as the owner of Redmine presentation metrics. `T_Tool.qml` consumes it only while Redmine is selected, and `RedmineWorkspace.qml` explicitly passes the scale into shared Issue components whose default remains `1.0`; this keeps Jira and other tools unchanged.

**Tech Stack:** PySide6 6.7.2, QML/FluentUI, Qt Quick Layouts, pytest source-contract/runtime probes, Qt resource compiler.

## Global Constraints

- Redmine trial density is exactly `0.70`.
- Do not use QML `scale` on a page, subtree, text item, or control.
- Base body font sizes and dynamic business text remain unchanged.
- Shared Issue components default to density `1.0`; only Redmine opts into `0.70`.
- Keep the current Tool navigation, Redmine filter order, SplitView relationship, persistence, and all bridge/business contracts unchanged.
- Do not package the desktop application; validate the source runtime and rebuild only applicable QRC resources.
- Do not modify `AGENTS.md` or promote density globally until the user accepts the Redmine visual result.

---

### Task 1: Define and prove the Redmine density contract

**Files:**
- Create: `ui/example/imports/example/qml/component/redmine/RedmineDensity.qml`
- Modify: `ui/example/imports/example/qml/component/redmine/qmldir`
- Modify: `ui/example/imports/resource.qrc`
- Test: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- Produces: singleton `RedmineDensity` with `scale: real`, `metric(real value, real minimum): real`, and `controlHeight(real value): real`.
- Consumes: no business state; QML presentation values only.

- [ ] **Step 1: Write the failing density-owner test**

Add this focused source-contract test:

```python
def test_redmine_density_owner_is_local_explicit_and_resource_backed():
    root = ROOT / "ui/example/imports"
    density = (root / "example/qml/component/redmine/RedmineDensity.qml").read_text(encoding="utf-8")
    qmldir = (root / "example/qml/component/redmine/qmldir").read_text(encoding="utf-8")
    qrc = (root / "resource.qrc").read_text(encoding="utf-8")
    assert "pragma Singleton" in density
    assert "readonly property real scale: 0.70" in density
    assert "function metric(value, minimum)" in density
    assert "function controlHeight(value)" in density
    assert "singleton RedmineDensity 1.0 RedmineDensity.qml" in qmldir
    assert "example/qml/component/redmine/RedmineDensity.qml" in qrc
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_tool_page.py::test_redmine_density_owner_is_local_explicit_and_resource_backed -q
```

Expected: FAIL because `RedmineDensity.qml` does not exist.

- [ ] **Step 3: Implement the minimal singleton and register it**

Create:

```qml
pragma Singleton
import QtQml 2.15

QtObject {
    readonly property real scale: 0.70
    function metric(value, minimum) {
        return Math.max(minimum || 0, Math.round(value * scale))
    }
    function controlHeight(value) {
        return metric(value, 28)
    }
}
```

Register it in the redmine `qmldir` and add the QML file to `resource.qrc` next to the other Redmine components.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2. Expected: `1 passed`.

- [ ] **Step 5: Commit the density contract**

```powershell
git add testing/self_tests/ui/test_tool_page.py ui/example/imports/example/qml/component/redmine/RedmineDensity.qml ui/example/imports/example/qml/component/redmine/qmldir ui/example/imports/resource.qrc
git commit -m "feat: define Redmine compact density"
```

### Task 2: Apply density to the Tool shell only when Redmine is selected

**Files:**
- Modify: `ui/example/imports/example/qml/page/T_Tool.qml`
- Test: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- Consumes: `RedmineDensity.scale` and `RedmineDensity.metric(value, minimum)`.
- Produces: `page.activeDensity`, `page.metric(value, minimum)`, and object-named geometry for runtime verification.

- [ ] **Step 1: Write failing Tool-shell contract assertions**

Add a test which reads `T_Tool.qml` and asserts:

```python
def test_tool_shell_uses_compact_density_only_for_redmine():
    page = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")
    assert 'readonly property real activeDensity: selectedTool.id === "redmine" ? RedmineDensity.scale : 1.0' in page
    assert 'Layout.preferredHeight: page.metric(118, 72)' in page
    assert 'Layout.preferredWidth: page.metric(216, 150)' in page
    assert 'padding: page.metric(12, 8)' in page
    assert 'spacing: page.metric(8, 5)' in page
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest testing/self_tests/ui/test_tool_page.py::test_tool_shell_uses_compact_density_only_for_redmine -q
```

Expected: FAIL because `activeDensity` and density-derived metrics are absent.

- [ ] **Step 3: Implement minimal conditional Tool density**

In `T_Tool.qml`, define:

```qml
readonly property real activeDensity: selectedTool.id === "redmine" ? RedmineDensity.scale : 1.0
function metric(value, minimum) {
    return Math.max(minimum || 0, Math.round(value * activeDensity))
}
```

Replace only presentation values owned by the Tool shell:

- outer margins `20` -> `page.metric(20, 12)`;
- outer spacing `12` -> `page.metric(12, 8)`;
- Schedule preferred height `118` -> `page.metric(118, 72)`;
- Schedule padding `10` -> `page.metric(10, 7)`;
- Tool sidebar width `216` -> `page.metric(216, 150)`;
- sidebar margins `12` -> `page.metric(12, 8)`;
- separator width `20` -> `page.metric(20, 12)`;
- workspace padding `12` -> `page.metric(12, 8)`;
- workspace column spacing `8` -> `page.metric(8, 5)`.

Do not change titles, visibility, selected tool state, loaders, signals, or bridge calls.

- [ ] **Step 4: Verify Redmine and non-Redmine contracts**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_tool_page.py::test_tool_shell_uses_compact_density_only_for_redmine testing/self_tests/ui/test_tool_page.py -q -k "tool_shell_uses_compact_density_only_for_redmine or tool_page_contains_schedule_area"
```

Expected: selected tests PASS.

- [ ] **Step 5: Commit the Tool-shell density**

```powershell
git add testing/self_tests/ui/test_tool_page.py ui/example/imports/example/qml/page/T_Tool.qml
git commit -m "feat: compact Redmine Tool shell"
```

### Task 3: Pass opt-in density through the shared Issue workspace

**Files:**
- Modify: `ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml`
- Modify: `ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml`
- Modify: `ui/example/imports/example/qml/component/issue/JiraIssueDetailLayout.qml`
- Test: `testing/self_tests/ui/test_tool_page.py`

**Interfaces:**
- `JiraIssueBrowserLayout.densityScale: real` defaults to `1.0`.
- `JiraIssueBrowserLayout.metric(real value, real minimum): real` derives display dimensions.
- `JiraIssueDetailLayout.densityScale: real` defaults to `1.0` and receives the browser scale.
- `RedmineWorkspace` sets `densityScale: RedmineDensity.scale`.

- [ ] **Step 1: Write failing opt-in/default-isolation tests**

Add:

```python
def test_redmine_opts_into_density_without_changing_shared_issue_default():
    redmine = (ROOT / "ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml").read_text(encoding="utf-8")
    browser = (ROOT / "ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml").read_text(encoding="utf-8")
    detail = (ROOT / "ui/example/imports/example/qml/component/issue/JiraIssueDetailLayout.qml").read_text(encoding="utf-8")
    assert "densityScale: RedmineDensity.scale" in redmine
    assert "property real densityScale: 1.0" in browser
    assert "property real densityScale: 1.0" in detail
    assert "densityScale: root.densityScale" in browser
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest testing/self_tests/ui/test_tool_page.py::test_redmine_opts_into_density_without_changing_shared_issue_default -q
```

Expected: FAIL because the density properties are absent.

- [ ] **Step 3: Add the opt-in properties and compact presentation metrics**

Add to both shared components:

```qml
property real densityScale: 1.0
function metric(value, minimum) {
    return Math.max(minimum || 0, Math.round(value * densityScale))
}
```

Set `densityScale: RedmineDensity.scale` at the `RedmineWorkspace` root. Pass `densityScale: root.densityScale` into `JiraIssueDetailLayout`.

In `JiraIssueBrowserLayout`, convert presentation-only values:

- root column spacing `10` -> `metric(10, 6)`;
- filter frame padding `12` -> `metric(12, 8)`;
- filter column spacing `8` -> `metric(8, 5)`;
- filter controls add `Layout.preferredHeight: metric(36, 28)`;
- status row/progress spacing and vertical margins use `metric(...)`;
- Issue list header margins `12` -> `metric(12, 8)`;
- Issue list action-row bottom margin `8` -> `metric(8, 5)`;
- list/detail frame padding and local spacing use the same helper;
- preserve SplitView orientation and business widths, with existing minimum widths unchanged.

In `JiraIssueDetailLayout`, convert only outer content margins and section spacing. Keep base font styles and business field widths unchanged.

- [ ] **Step 4: Verify shared default and Redmine opt-in**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_tool_page.py::test_redmine_opts_into_density_without_changing_shared_issue_default testing/self_tests/ui/test_tool_page.py -q -k "redmine_opts_into_density or redmine_workspace or issue_browser"
```

Expected: selected tests PASS with no assertion failures.

- [ ] **Step 5: Commit shared presentation density support**

```powershell
git add testing/self_tests/ui/test_tool_page.py ui/example/imports/example/qml/component/redmine/RedmineWorkspace.qml ui/example/imports/example/qml/component/issue/JiraIssueBrowserLayout.qml ui/example/imports/example/qml/component/issue/JiraIssueDetailLayout.qml
git commit -m "feat: compact Redmine issue workspace"
```

### Task 4: Build resources and validate the visual trial

**Files:**
- Regenerate ignored local file: `ui/example/imports/resource_rc.py`
- Verify: all files changed in Tasks 1-3

**Interfaces:**
- Consumes: source QML and `ui/example/imports/resource.qrc`.
- Produces: source runtime loading the new Redmine density QML.

- [ ] **Step 1: Rebuild the main QRC with system Python tooling**

```powershell
pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

Expected: exit code `0`; generated resource timestamp is newer than changed QML.

- [ ] **Step 2: Verify QRC import and focused tests**

```powershell
python -c "import sys; sys.path.insert(0, 'ui'); from example.imports import resource_rc; print('qrc-import-ok')"
python -m pytest testing\self_tests\ui\test_tool_page.py -q -k "density or redmine_workspace or issue_browser or schedule_area"
```

Expected: QRC import succeeds and selected tests pass. If tests that spawn `.venv` fail, run the density source-contract tests explicitly with system `python` and record the unrelated harness limitation.

- [ ] **Step 3: Start the source application and inspect current logs**

Run `python .\main.py`, open Tool -> Redmine, and verify:

- title `SmartTest` appears;
- no new QML warning references the changed density files;
- filter/search/selection controls remain clickable;
- Issue list and detail retain the existing left/right relationship;
- non-Redmine Tool pages retain current density.

- [ ] **Step 4: Capture the same-screen comparison**

At the user's current resolution/DPI, capture Tool -> Redmine with the same window state as the supplied screenshot. Compare:

- Schedule height;
- Tool sidebar width;
- workspace outer padding;
- filter-area height;
- Issue list/detail visible height.

The trial passes only if the Issue list/detail viewport is visibly larger without shrinking body text or changing the layout structure.

- [ ] **Step 5: Run final repository checks**

```powershell
git diff --check
git status --short
```

Expected: only scoped source/test changes and the existing untracked `debug.log`; ignored `resource_rc.py` does not appear as a tracked change.

- [ ] **Step 6: Request user visual acceptance**

Present the before/after evidence. Do not modify `AGENTS.md`, the UI skill, or other pages until the user explicitly accepts the Redmine result.
