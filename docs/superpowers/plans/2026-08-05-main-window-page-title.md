# Main Window Page Title Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every main-navigation page identity into the application title bar as `SmartTest.<page>`, while Home remains `SmartTest`, and remove the standard large page-title header from main-window content.

**Architecture:** `FluPage` retains ownership of its standard header and gains a default-on visibility property. `FluNavigationView` opts hosted pages out of that header and exposes the selected navigation title; `MainWindow` is the only owner of the final product-title composition.

**Tech Stack:** Qt 6, QML, PySide6, FluentUI, pytest runtime probes, QRC resources

## Global Constraints

- Apply header suppression only to pages hosted by the primary `MainWindow.qml` navigation view.
- Standalone windows, dialogs, page windows, and other `FluPage` consumers keep title headers by default.
- Home displays `SmartTest`; every other selected main-navigation page displays `SmartTest.<localized navigation title>`.
- Preserve page `title` values and all business headings inside page content.
- Rebuild both FluentUI and example QRC resources after QML changes.
- Validate source runtime only; do not build the packaged application.

---

### Task 1: Page Header Opt-Out and Navigation Title Contract

**Files:**
- Modify: `ui/FluentUI/imports/FluentUI/Controls/FluPage.qml`
- Modify: `ui/FluentUI/imports/FluentUI/Controls/FluNavigationView.qml`
- Test: `testing/self_tests/ui/test_main_window_page_title.py`

**Interfaces:**
- Produces: `FluPage.showTitleHeader: bool`, default `true`.
- Produces: `FluNavigationView.showPageTitleHeaders: bool`, default `true`.
- Produces: `FluNavigationView.currentPageTitle: string`, derived from current navigation selection.
- Consumes: existing navigation model items with `title`, `_idx`, and `url` properties.

- [ ] **Step 1: Write failing runtime tests for the defaults and navigation contract**

Create `testing/self_tests/ui/test_main_window_page_title.py` with an offscreen PySide6 QML probe. Load a standalone `FluPage { title: "Test" }` and assert its header exists and has positive height. Load a `FluNavigationView` with Home and Test pane items, set `showPageTitleHeaders: false`, navigate to Test, and assert:

```python
assert standalone_header_height > 0
assert navigation.property("currentPageTitle") == "Test"
assert test_page.property("title") == "Test"
assert round(test_page.property("header").height()) == 0
assert warnings == []
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_main_window_page_title.py -q
```

Expected: FAIL because `showTitleHeader`, `showPageTitleHeaders`, and `currentPageTitle` do not exist.

- [ ] **Step 3: Add the page-level opt-out**

In `FluPage.qml`, add:

```qml
property bool showTitleHeader: true
header: FluLoader {
    visible: control.showTitleHeader
    implicitHeight: visible && item ? item.implicitHeight : 0
    sourceComponent: control.showTitleHeader && control.title !== "" ? com_header : undefined
}
```

Keep `title` unchanged when the header is hidden.

- [ ] **Step 4: Add the navigation-level contract and apply it to hosted pages**

In `FluNavigationView.qml`, add:

```qml
property bool showPageTitleHeaders: true
readonly property string currentPageTitle: {
    var index = nav_list.currentIndex
    var rows = nav_list.model || []
    return index >= 0 && index < rows.length && rows[index] ? (rows[index].title || "") : ""
}

function configureHostedPage(page) {
    if(page && page.showTitleHeader !== undefined)
        page.showTitleHeader = showPageTitleHeaders
}
```

Call `configureHostedPage(obj)` immediately after creating a page, and call it for a cached `SingleInstance` page before making it current. Bind footer and back selection through the existing current-index state so `currentPageTitle` always follows the visible navigation item.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_main_window_page_title.py -q
```

Expected: all tests pass with zero QML warnings.

- [ ] **Step 6: Commit the framework contract**

```powershell
git add -f testing/self_tests/ui/test_main_window_page_title.py
git add ui/FluentUI/imports/FluentUI/Controls/FluPage.qml ui/FluentUI/imports/FluentUI/Controls/FluNavigationView.qml
git commit -m "feat: expose navigation page title contract"
```

---

### Task 2: Main Window Product Title and End-to-End Navigation

**Files:**
- Modify: `ui/example/imports/example/qml/window/MainWindow.qml`
- Modify: `testing/self_tests/ui/test_main_window_page_title.py`
- Rebuild: `ui/FluentUI/imports/resource_rc.py`
- Rebuild: `ui/example/imports/resource_rc.py`

**Interfaces:**
- Consumes: `FluNavigationView.currentPageTitle: string` and `showPageTitleHeaders: bool` from Task 1.
- Produces: `MainWindow.applicationDisplayTitle: string` used by both `FluWindow.title` and `FluNavigationView.title`.

- [ ] **Step 1: Extend the runtime test to cover product-title composition**

Load the actual `MainWindow.qml` with the repository context registry. Navigate through the real navigation API and assert:

```python
assert title_after_home == "SmartTest"
assert title_after_test == "SmartTest.Test"
assert title_after_tool == "SmartTest.Tool"
assert title_after_report == "SmartTest.Report"
assert title_after_settings == "SmartTest.Settings"
assert title_after_back == "SmartTest.Report"
assert all(header_height == 0 for header_height in main_page_header_heights)
assert warnings == []
```

The test must use navigation items rather than parsing URLs or assigning the title directly.

- [ ] **Step 2: Run the end-to-end test and verify RED**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_main_window_page_title.py -q
```

Expected: FAIL because `MainWindow` still uses the fixed title `SmartTest` and has not disabled hosted page headers.

- [ ] **Step 3: Compose one title in MainWindow**

In `MainWindow.qml`, add a single presentation property:

```qml
readonly property string applicationDisplayTitle: {
    var pageTitle = nav_view.currentPageTitle || ""
    return pageTitle === "" || pageTitle === qsTr("Home")
            ? "SmartTest"
            : "SmartTest." + pageTitle
}
title: applicationDisplayTitle
```

Configure the primary navigation view with:

```qml
showPageTitleHeaders: false
title: window.applicationDisplayTitle
```

Do not change page-local `title` declarations.

- [ ] **Step 4: Rebuild QRC resources**

Run:

```powershell
pyside6-rcc ui/FluentUI/imports/resource.qrc -o ui/FluentUI/imports/resource_rc.py
pyside6-rcc ui/example/imports/resource.qrc -o ui/example/imports/resource_rc.py
```

Expected: both commands exit 0.

- [ ] **Step 5: Run focused and related UI tests**

Run:

```powershell
python -m pytest testing/self_tests/ui/test_main_window_page_title.py testing/self_tests/ui/test_tool_page.py -q
```

Expected: page-title tests pass. If legacy `test_tool_page.py` cases fail only because they hard-code the removed `.venv` or cannot write sandboxed `%LOCALAPPDATA%` logs, report those environment failures separately and do not change product code to mask them.

- [ ] **Step 6: Perform actual source-window visual validation**

Close only the verified SmartTest `python main.py` process, start the global Python source runtime, navigate to Test, Tool, Report, and Settings, and capture screenshots. Confirm that the former 40px page header is absent, content moves upward, and the visible app-bar label matches the active page.

- [ ] **Step 7: Commit the main-window behavior**

```powershell
git add ui/example/imports/example/qml/window/MainWindow.qml
git add -f testing/self_tests/ui/test_main_window_page_title.py
git commit -m "feat: move page identity into app title"
```
