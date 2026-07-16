# Reusable Issue Detail Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable FluentUI QML Issue detail view that closely matches the approved Jira reference while exposing only display, comment, attachment, drag-confirmation, and navigation signals.

**Architecture:** `IssueDetailView.qml` is the public composition root and vertical scroll/drop owner. Focused child components own header, field sections, description, comments, attachments, and attachment cards; they consume stable display objects and never import Jira, Redmine, or Bridges.

**Tech Stack:** PySide6, Qt Quick/QML, QtQuick.Layouts, QtQuick.Dialogs, repository FluentUI controls, pytest/QTest, Qt resource and translation tools.

## Global Constraints

- This phase implements layout and signal contracts only; no Jira/Redmine REST, LDAP, browser opening, comment submission, attachment transfer, or file-byte reading.
- Preserve a two-column 68/32 detail/sidebar layout without responsive stacking or horizontal scrolling.
- Omit Jira edit/action toolbar and Activity/All/Work Log/History tabs.
- SmartTest fixed text is complete in both `example_en_US.ts` and `example_zh_CN.ts`; dynamic external text is displayed raw.
- Custom theme-sensitive colors define explicit readable light and dark values.
- Child components contain no Jira/Redmine field IDs, Bridge imports, page-specific stores, or business decisions.
- Comment draft is retained after signal emission; the future business owner calls public `clearCommentDraft()` only after confirmed success.

---

### Task 1: Create the read-only Jira-style detail composition

**Files:**
- Create: `ui/example/imports/example/qml/component/issue/IssueDetailView.qml`
- Create: `ui/example/imports/example/qml/component/issue/IssueHeader.qml`
- Create: `ui/example/imports/example/qml/component/issue/IssueFieldSection.qml`
- Create: `ui/example/imports/example/qml/component/issue/IssueDescription.qml`
- Modify: `ui/example/imports/resource.qrc`
- Test: `testing/self_tests/ui/test_issue_detail_view.py`

**Interfaces:**
- Produces `IssueDetailView.issue`, `comments`, `attachments`, loading/submitting/uploading/error properties from the design.
- Produces `openIssueRequested(issueKey, webUrl)` and `externalLinkRequested(url)`.
- Child field rows consume display-only `{label, value, kind, url, values}` objects.

- [ ] **Step 1: Write failing independent-load and geometry tests**

Create an offscreen `QGuiApplication`/FluentUI/QRC test fixture that loads a visible QML Window containing only `IssueDetailView`. Seed a representative issue with long Chinese/English title, Details, People, Dates, tags, links, description, comments, and attachments. Assert before implementation that the QRC component cannot load.

Add geometry expectations at a wide and supported narrow width:

```python
ratio = left_width / (left_width + right_width)
assert ratio == pytest.approx(0.68, abs=0.02)
assert detail.contentWidth <= detail.width
assert right_column.y == left_column.y
```

Add static assertions that reject `Qt.openUrlExternally`, Bridge/Jira/Redmine imports, Jira action labels, and Activity-tab controls.

- [ ] **Step 2: Run RED verification**

Run: `.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_issue_detail_view.py -q`

Expected: collection/runtime failure because `IssueDetailView.qml` is not registered in QRC.

- [ ] **Step 3: Implement the minimal composition and field components**

Use one vertical `Flickable`/content `ColumnLayout`; subtract column spacing before assigning 68/32 preferred widths. Use `FluTheme` semantic colors and explicit light/dark link colors. Long title and values use wrapping; links only emit signals.

Expose stable test hooks through `objectName` for the detail root, left/right columns, Issue Key/title links, field links, Description, Comments, and Attachments sections. Do not add user-visible test text.

- [ ] **Step 4: Run GREEN verification**

Run the exact test module. Expected: independent load, two-column geometry, link signals, dynamic raw content, no forbidden owners, and zero QML warnings pass.

### Task 2: Add reusable Comments layout and signal state

**Files:**
- Create: `ui/example/imports/example/qml/component/issue/IssueComments.qml`
- Modify: `ui/example/imports/example/qml/component/issue/IssueDetailView.qml`
- Modify: `testing/self_tests/ui/test_issue_detail_view.py`

**Interfaces:**
- Produces `commentSubmitRequested(string issueKey, string content)`.
- Produces public `IssueDetailView.clearCommentDraft()` delegated to the Comments component.
- Consumes `comments`, `commentsLoading`, `commentSubmitting`, and `commentError`.

- [ ] **Step 1: Write failing Comment interaction tests**

Use QTest mouse/key interaction against real visible controls. Verify:

```text
Comment button -> editor visible
typed draft -> Submit -> exactly one (issueKey, content) signal
signal emission -> draft remains
commentSubmitting=true -> controls disabled and repeated click emits nothing
commentError -> raw error visible and draft remains
clearCommentDraft() -> editor content becomes empty
empty/loading/comment-list states render without Activity tabs
```

- [ ] **Step 2: Run RED verification**

Run the focused Comment tests; expected failure is missing Comments component/signals.

- [ ] **Step 3: Implement minimal Comments UI**

Render author/avatar placeholder/time/body from raw comment objects. Keep only a `Comments` section title, Jira-like Comment button, multiline editor, Submit, and Cancel. Fixed labels use `qsTr`; external comment/error content remains raw. Guard empty/whitespace submission and duplicate submission.

- [ ] **Step 4: Run GREEN verification**

Run the full Issue detail test module; expected result PASS with no QML warnings.

### Task 3: Add attachment cards, file selection, and drag confirmation

**Files:**
- Create: `ui/example/imports/example/qml/component/issue/IssueAttachments.qml`
- Create: `ui/example/imports/example/qml/component/issue/IssueAttachmentCard.qml`
- Modify: `ui/example/imports/example/qml/component/issue/IssueDetailView.qml`
- Modify: `testing/self_tests/ui/test_issue_detail_view.py`

**Interfaces:**
- Produces `attachmentFilesSelected(issueKey, fileUrls)`.
- Produces `attachmentUploadConfirmed(issueKey, fileUrls)`.
- Produces `attachmentOpenRequested(issueKey, attachment)`.
- Consumes `attachments`, `attachmentsLoading`, `attachmentUploading`, and `attachmentError`.

- [ ] **Step 1: Write failing attachment and drag tests**

Verify FileDialog multi-file selection emits the unchanged local URLs once. Verify attachment-card click emits the original object once. Route native DropArea and tests through one presentational staging function and assert:

```text
local file URLs staged -> confirmation visible -> zero upload signals
positive confirmation -> one upload-confirmed signal -> pending cleared
negative confirmation -> zero upload signals -> pending cleared
non-file URLs rejected
attachmentUploading=true -> duplicate select/drop/confirm disabled
```

- [ ] **Step 2: Run RED verification**

Run the focused attachment tests; expected failure is missing attachment components/signals.

- [ ] **Step 3: Implement minimal attachment UI**

Use Jira-style dashed drop surface and responsive card grid. Display thumbnail URL when supplied, otherwise a Fluent file/image icon; show raw filename/time/size. Never read local file contents. Use Qt 6 `FileDialog.OpenFiles`/`selectedFiles` after validating the installed PySide API. Confirmation uses existing `FluContentDialog` patterns.

- [ ] **Step 4: Run GREEN verification**

Run the complete Issue detail test module; expected result PASS with exact signal counts and no pre-confirm upload emission.

### Task 4: Complete translations, resources, and source acceptance

**Files:**
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Modify: `ui/example/imports/resource.qrc`
- Regenerate: `ui/example/imports/resource_rc.py`
- Modify: `testing/self_tests/ui/test_issue_detail_view.py`

**Interfaces:**
- Consumes all new `qsTr(...)` sources.
- Produces an independently loadable `qrc:/example/qml/component/issue/IssueDetailView.qml`.

- [ ] **Step 1: Add failing translation/resource contract checks**

Parse both TS catalogs and require every new fixed source to have a finished, nonempty translation. Require all seven QML files in QRC. Assert dynamic fixture values are absent from translation sources.

- [ ] **Step 2: Run RED verification**

Run the contract tests; expected failure identifies missing catalog/QRC entries.

- [ ] **Step 3: Add bilingual text and regenerate resources**

Update both catalogs together, run `pyside6-lrelease` for both languages, then:

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

- [ ] **Step 4: Run final focused acceptance**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing\self_tests\ui\test_issue_detail_view.py -q
.\.venv\Scripts\python.exe -m compileall ui\example\imports\example\qml\component\issue
git diff --check
```

Expected: all focused tests pass, compilation and diff check exit `0`, and both light/dark runtime probes load without QML warnings.

- [ ] **Step 5: Commit the layout**

```powershell
git add ui\example\imports\example\qml\component\issue ui\example\imports\resource.qrc ui\example\example_en_US.ts ui\example\example_zh_CN.ts testing\self_tests\ui\test_issue_detail_view.py
git commit -m "feat: add reusable Issue detail layout"
```

