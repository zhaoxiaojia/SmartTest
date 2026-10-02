# Project Weekly Audit Failure Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Project Weekly Audit 的每条失败项保存网页局部截图和自然语言判定解释，并在 SmartTest 中展示可点击放大的历史证据。

**Architecture:** `support/confluence_audit` 继续拥有规则结论、解释、证据定位和批次资产；现有 `support/browser_automation.BrowserRuntime` 提供唯一 Playwright 生命周期。Bridge 只把本地批次证据转换为安全的图片 URL，QML 复用 FluentUI 图片与弹窗组件展示，不解析网页或重新判断规则。

**Tech Stack:** Python 3.10、dataclasses、atlassian-python-api、Playwright async API、PySide6、QML/FluentUI、pytest、openpyxl。

## Global Constraints

- 只在用户主动审查时为 `failed` finding 截图；不开发 scheduler。
- 截图失败不改变 finding 或项目状态，必须继续完成审查。
- 不依赖 Codex、Chrome 插件或用户浏览器 profile。
- LDAP 密码、Cookie、storage state 和完整 HTML 不落盘、不进日志。
- 同一页面多个失败项只导航一次；一个页面失败不阻塞其他页面。
- 历史 JSON 只保存批次目录内相对路径；旧 schema 必须继续可读。
- XLSX 导出 explanation 与 guidance，本次不嵌入图片。
- 固定前端文字同时维护中英文翻译并重新生成 QRC。
- 保留工作区全部用户改动；Coco 确认功能完整前不提交 Git。

---

## File Structure

- Create: `support/confluence_audit/evidence.py` — 规则级截图定位、页面分组、Playwright 采集和非阻断降级。
- Modify: `support/confluence_audit/models.py` — finding 解释与证据字段。
- Modify: `support/confluence_audit/rules.py` — 从结构化规则事实生成 explanation。
- Modify: `support/confluence_audit/service.py` — 规则审查后调用证据采集器并在采集完成后保存批次。
- Modify: `support/confluence_audit/store.py` — schema v2、相对资产路径和 v1 向后兼容。
- Modify: `support/confluence_audit/exporter.py` — 导出自然语言解释。
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py` — 安全解析批次证据 URL。
- Modify: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml` — explanation、缩略图、放大弹窗和失败占位。
- Modify: `ui/example/example_en_US.ts`, `ui/example/example_zh_CN.ts`, `ui/example/imports/resource_rc.py` — 固定文字与资源。
- Test: `testing/self_tests/support/test_confluence_audit_evidence.py`
- Test: `testing/self_tests/support/test_confluence_audit_rules.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`
- Test: `testing/self_tests/ui/test_tool_page.py`
- Test: `testing/self_tests/ui/test_owned_ui_translations.py`

---

### Task 1: Finding 解释与历史证据合同

**Files:**
- Modify: `support/confluence_audit/models.py`
- Modify: `support/confluence_audit/store.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Produces: `AuditFinding.explanation: str`
- Produces: `AuditFinding.evidence_path: str`
- Produces: `AuditFinding.evidence_status: str`
- Produces: `AuditFinding.evidence_message: str`
- Produces: `AuditHistoryStore.batch_root(batch_id: str) -> Path`
- Produces: `AuditHistoryStore.evidence_root(batch_id: str) -> Path`

- [ ] **Step 1: Write failing schema and compatibility tests**

```python
def test_history_v1_loads_with_empty_evidence_fields(tmp_path):
    store = AuditHistoryStore(tmp_path)
    write_v1_batch(store.root / "old.json")
    finding = store.load("old").projects[0].findings[0]
    assert finding.explanation == ""
    assert finding.evidence_path == ""
    assert finding.evidence_status == "not_requested"
    assert finding.evidence_message == ""

def test_history_v2_keeps_relative_evidence_path(tmp_path):
    store = AuditHistoryStore(tmp_path)
    batch = batch_with_finding(
        explanation="The page was not updated in the audit window.",
        evidence_path="evidence/Muffin314-weekly.update-a1b2.png",
        evidence_status="captured",
    )
    store.save(batch)
    finding = store.load(batch.id).projects[0].findings[0]
    assert finding.evidence_path == "evidence/Muffin314-weekly.update-a1b2.png"
```

- [ ] **Step 2: Run RED tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_service.py -k "history_v1 or history_v2" -q
```

Expected: FAIL because the four fields and batch asset helpers do not exist.

- [ ] **Step 3: Add minimal model fields and schema-v2 loader**

```python
@dataclass(frozen=True)
class AuditFinding:
    # existing fields remain in their current order
    explanation: str = ""
    evidence_path: str = ""
    evidence_status: str = "not_requested"
    evidence_message: str = ""

class AuditHistoryStore:
    VERSION = 2

    def batch_root(self, batch_id: str) -> Path:
        return self.root / str(batch_id)

    def evidence_root(self, batch_id: str) -> Path:
        return self.batch_root(batch_id) / "evidence"

    @staticmethod
    def _finding(row: dict) -> AuditFinding:
        values = {
            "explanation": "",
            "evidence_path": "",
            "evidence_status": "not_requested",
            "evidence_message": "",
            **row,
        }
        values["status"] = AuditStatus(values["status"])
        return AuditFinding(**values)
```

Validate `batch_id` with the existing generated ID format before joining paths; reject separators and traversal.

- [ ] **Step 4: Run GREEN tests**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Record diff checkpoint**

Run:

```powershell
git diff --check
git status --short
```

Do not commit before Coco confirms functional completeness.

---

### Task 2: Rule-owned natural-language explanations

**Files:**
- Modify: `support/confluence_audit/rules.py`
- Modify: `support/confluence_audit/service.py`
- Modify: `support/confluence_audit/exporter.py`
- Test: `testing/self_tests/support/test_confluence_audit_rules.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Consumes: `AuditFinding.explanation`
- Produces: every `failed` finding has non-empty `reason`, `explanation`, `guidance`, and `page_url`
- Produces: XLSX Findings columns `Reason`, `Explanation`, `Guidance`

- [ ] **Step 1: Write failing explanation contract tests**

```python
def test_report_weekly_failure_explains_period_and_page_fact():
    finding = audit_report_store(
        period=period("2026-07-27T00:00:00+08:00", "2026-07-31T00:00:00+08:00"),
        page_updated_at="2026-07-11T10:00:00+08:00",
        attachments=[],
    )
    assert finding.status is AuditStatus.FAILED
    assert "2026-07-27" in finding.explanation
    assert "2026-07-30" in finding.explanation
    assert "2026-07-11" in finding.explanation
    assert "no new attachment or report link" in finding.explanation.casefold()
    assert "N/A" in finding.guidance

def test_metric_failure_explains_named_row_and_formula():
    finding = audit_live_metric_row(
        name="Stability", passed=3, failed=2, pending=16, total=21, rate=14.29
    )
    assert "Stability" in finding.explanation
    assert "14.29%" in finding.explanation
    assert "60.00%" in finding.explanation
    assert "Pass / (Pass + Fail)" in finding.explanation
```

Add representative tests for `weekly.update`, `status.highlights`, `status.impact`, `test.failures`, `plan.weekly`, and `environment.complete`.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_rules.py testing/self_tests/support/test_confluence_audit_service.py -k "explain or explanation" -q
```

Expected: FAIL because rules do not populate explanation.

- [ ] **Step 3: Extend the existing rule `add` owner**

Use one helper in `rules.py`; do not add a second post-processing explanation map:

```python
def add(kind, rule, status, reason, guidance="", explanation=""):
    page = pages.get(kind)
    findings.append(AuditFinding(
        project.project_id,
        page.title if page else DISPLAY[kind],
        rule,
        status,
        reason,
        guidance or RULE_GUIDANCE.get(rule, ""),
        page_url=page.url if page else project.home_url,
        explanation=explanation or reason,
    ))
```

Construct explanations from existing `period`, `PageAuditFacts`, parsed metric rows, attachment timestamps and extracted section state. Do not parse the same HTML a second time.

For report archive:

```python
explanation = (
    f"The audit window is {period.start:%Y-%m-%d} through "
    f"{(period.end - timedelta(days=1)):%Y-%m-%d}. "
    f"{report.title} was last updated on {report.updated_at:%Y-%m-%d}, "
    "and no new attachment or report link was archived in that window."
)
```

Use an explicit alternative when `updated_at` is unavailable.

- [ ] **Step 4: Preserve the service exit guarantee**

In `service.py`, keep one fallback only for external-I/O/AI findings:

```python
replace(
    finding,
    explanation=finding.explanation or finding.reason,
    guidance=finding.guidance or DEFAULT_ACTION_GUIDANCE,
)
```

Static rule-specific guidance remains owned by `RULE_GUIDANCE`.

- [ ] **Step 5: Extend XLSX export**

```python
findings.append([
    "Project", "Page", "Rule", "Status",
    "Reason", "Explanation", "Guidance", "URL", "Source",
])
```

Write `row.explanation` between reason and guidance. Do not embed images.

- [ ] **Step 6: Run GREEN tests**

Run the Step 2 command plus:

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Record diff checkpoint**

Run `git diff --check`; do not commit.

---

### Task 3: Playwright failure evidence collector

**Files:**
- Create: `support/confluence_audit/evidence.py`
- Modify: `support/confluence_audit/service.py`
- Test: `testing/self_tests/support/test_confluence_audit_evidence.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`

**Interfaces:**
- Consumes: `BrowserRuntime.context(system_id, account_id) -> BrowserSession`
- Consumes: `BrowserSession.new_page()`
- Produces:

```python
class ConfluenceEvidenceCollector:
    async def collect(
        self,
        batch: AuditBatch,
        *,
        username: str,
        password: str,
        evidence_root: Path,
        progress: Callable[[str, int, int], None],
    ) -> AuditBatch: ...
```

- Produces: failed findings replaced with evidence fields; other findings unchanged.

- [ ] **Step 1: Write failing collector tests with fake runtime/pages**

```python
async def test_same_url_is_navigated_once_for_multiple_failures(tmp_path):
    runtime = FakeRuntime()
    collector = ConfluenceEvidenceCollector(runtime, base_url="https://confluence.amlogic.com")
    result = await collector.collect(
        batch_with_two_failed_findings_same_url(),
        username="ldap-user",
        password="secret",
        evidence_root=tmp_path,
        progress=lambda *_: None,
    )
    assert runtime.page.goto_urls == ["https://confluence.amlogic.com/page/1"]
    assert all(row.evidence_status == "captured" for row in result.projects[0].findings)

async def test_capture_failure_does_not_change_business_status(tmp_path):
    collector = ConfluenceEvidenceCollector(FailingRuntime(), base_url="https://confluence.amlogic.com")
    result = await collector.collect(
        batch_with_failed_finding(),
        username="ldap-user",
        password="secret",
        evidence_root=tmp_path,
        progress=lambda *_: None,
    )
    finding = result.projects[0].findings[0]
    assert finding.status is AuditStatus.FAILED
    assert finding.evidence_status == "unavailable"
    assert finding.evidence_path == ""
    assert finding.evidence_message
```

Also test non-failed findings are not requested, output names contain only project/rule/digest, paths cannot escape evidence root, locator failure falls back to main content, and passwords never enter logs/file names.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_evidence.py -q
```

Expected: collection error because `evidence.py` does not exist.

- [ ] **Step 3: Implement one collector using existing BrowserRuntime**

```python
RULE_TARGETS = {
    "weekly.update": ("metadata",),
    "status.highlights": ("heading", "Highlights"),
    "status.impact": ("heading", "Impact issues"),
    "test.metrics": ("table_row_from_explanation",),
    "test.failures": ("test_result_table",),
    "plan.weekly": ("current_week_table",),
    "environment.complete": ("main_content",),
    "report.weekly": ("metadata_and_attachment_list",),
}
```

Implementation requirements:

- Create exactly one `BrowserRuntime(headless=True)`.
- Use `await runtime.context("confluence-audit", username)` and one page.
- Authenticate through the Confluence login page with locator-based username/password fields; never persist storage state.
- Group findings by canonical URL and navigate once per URL.
- Prefer semantic headings/table rows; fall back to `#main-content` or `main`.
- Use element screenshots when supported; otherwise use a bounded main-content screenshot.
- Write PNG atomically inside `evidence_root`.
- Catch errors at runtime, login, page and rule boundaries; return `unavailable`.
- Always close context/runtime in `finally`.

- [ ] **Step 4: Add a synchronous service adapter without a second event loop owner**

The audit worker already runs in a background thread. Add one adapter:

```python
def collect_failure_evidence(collector, batch, **kwargs):
    return asyncio.run(collector.collect(batch, **kwargs))
```

Extend `ConfluenceAuditService.__init__` with optional `evidence_collector`,
`evidence_username`, and `evidence_password` parameters. The bridge supplies the LDAP
credentials only while constructing the short-lived service for the current run; no
credential may be logged or serialized.

`ConfluenceAuditService.run` must build the batch, collect evidence, then save the final batch once. Do not save a pre-evidence batch.

- [ ] **Step 5: Run GREEN tests**

Run Step 2 and:

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Record diff checkpoint**

Run `git diff --check`; do not commit.

---

### Task 4: Bridge evidence URLs and safe history loading

**Files:**
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`

**Interfaces:**
- Consumes: finding evidence fields and `AuditHistoryStore.batch_root`
- Produces finding row fields:

```python
{
    "explanation": str,
    "evidenceUrl": str,
    "evidenceStatus": str,
    "evidenceMessage": str,
}
```

- [ ] **Step 1: Write failing bridge tests**

```python
def test_bridge_exposes_captured_batch_evidence_as_local_file_url(tmp_path):
    bridge, batch = bridge_with_captured_evidence(tmp_path)
    bridge._apply_batch(batch)
    row = bridge.viewState["findings"][0]
    assert row["explanation"]
    assert row["evidenceStatus"] == "captured"
    assert row["evidenceUrl"].startswith("file:///")

def test_bridge_rejects_evidence_path_outside_batch_root(tmp_path):
    bridge, batch = bridge_with_evidence_path(tmp_path, "../secret.png")
    bridge._apply_batch(batch)
    row = bridge.viewState["findings"][0]
    assert row["evidenceUrl"] == ""
    assert row["evidenceStatus"] == "unavailable"

def test_bridge_maps_evidence_progress_without_failing_the_run():
    bridge = make_bridge()
    bridge._on_progress("evidence", 1, 2)
    assert "evidence" in bridge.viewState["stage"]
```

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_confluence_audit_bridge.py -k evidence -q
```

Expected: FAIL because the fields are absent.

- [ ] **Step 3: Implement one safe resolver**

```python
def _evidence_url(self, batch_id: str, relative_path: str) -> str:
    root = self._store.batch_root(batch_id).resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents or not target.is_file():
        return ""
    return QUrl.fromLocalFile(str(target)).toString()
```

Use this resolver only when `evidence_status == "captured"`. Never expose arbitrary paths supplied by JSON.

- [ ] **Step 4: Surface the non-blocking evidence stage**

Map the service's `evidence` progress stage to a concise user-visible status such as
`Capturing failure evidence...`. Evidence capture failure remains a per-finding
availability message and must not switch the overall run to an error state.

- [ ] **Step 5: Run GREEN tests**

Run Step 2. Expected: PASS.

- [ ] **Step 6: Record diff checkpoint**

Run `git diff --check`; do not commit.

---

### Task 5: Thumbnail, explanation and image dialog

**Files:**
- Modify: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Regenerate: `ui/example/imports/resource_rc.py`
- Test: `testing/self_tests/ui/test_tool_page.py`
- Test: `testing/self_tests/ui/test_owned_ui_translations.py`

**Interfaces:**
- Consumes: `explanation`, `evidenceUrl`, `evidenceStatus`, `evidenceMessage`
- Produces stable object names:
  - `confluenceAuditExplanation`
  - `confluenceAuditEvidenceThumbnail`
  - `confluenceAuditEvidenceDialog`
  - `confluenceAuditEvidenceUnavailable`

- [ ] **Step 1: Write failing QML contract tests**

```python
def test_confluence_audit_failure_card_has_explanation_thumbnail_and_dialog():
    qml = confluence_workspace_text()
    for name in (
        "confluenceAuditExplanation",
        "confluenceAuditEvidenceThumbnail",
        "confluenceAuditEvidenceDialog",
        "confluenceAuditEvidenceUnavailable",
    ):
        assert f'objectName: "{name}"' in qml
    assert "modelData.explanation" in qml
    assert "modelData.evidenceUrl" in qml
```

Add a QRC load test that supplies a captured finding and an unavailable finding without QML warnings.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py -k "confluence_audit and evidence" -q
```

Expected: FAIL because UI controls do not exist.

- [ ] **Step 3: Add explanation and unavailable state**

Inside the finding delegate:

```qml
FluText {
    objectName: "confluenceAuditExplanation"
    Layout.fillWidth: true
    text: qsTr("Why it failed") + ": " + modelData.explanation
    wrapMode: Text.WordWrap
}
FluText {
    objectName: "confluenceAuditEvidenceUnavailable"
    visible: modelData.evidenceStatus === "unavailable"
    text: modelData.evidenceMessage
    wrapMode: Text.WordWrap
    color: FluTheme.fontSecondaryColor
}
```

- [ ] **Step 4: Add thumbnail and one shared dialog**

Use one dialog at workspace scope, not one dialog per delegate. Clicking a thumbnail sets `root.previewUrl` and opens it:

```qml
property string previewUrl: ""

Image {
    objectName: "confluenceAuditEvidenceThumbnail"
    visible: modelData.evidenceStatus === "captured" && modelData.evidenceUrl.length > 0
    source: modelData.evidenceUrl
    fillMode: Image.PreserveAspectFit
    sourceSize.width: 720
    Layout.preferredHeight: visible ? 180 : 0
    Layout.fillWidth: true
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.previewUrl = parent.source
            evidenceDialog.open()
        }
    }
}
```

The shared `FluContentDialog` contains a `Flickable` and `Image` with `PreserveAspectFit`; it closes without changing report state.

- [ ] **Step 5: Update translations and resources**

Add exact translations for:

- `Why it failed`
- `Evidence screenshot`
- `Screenshot unavailable`
- `Close`
- `Capturing failure evidence...`

Run:

```powershell
.\.venv\Scripts\pyside6-lupdate.exe ui\example -ts ui\example\example_en_US.ts ui\example\example_zh_CN.ts
.\.venv\Scripts\pyside6-lrelease.exe ui\example\example_en_US.ts
.\.venv\Scripts\pyside6-lrelease.exe ui\example\example_zh_CN.ts
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

- [ ] **Step 6: Run GREEN UI tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_confluence_audit_bridge.py testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q
```

Expected: PASS.

- [ ] **Step 7: Record diff checkpoint**

Run `git diff --check`; do not commit.

---

### Task 6: Full regression and real Muffin314 acceptance

**Files:**
- Review only the files listed in this plan.

**Interfaces:**
- Consumes all preceding contracts.
- Produces final functional and code-quality evidence.

- [ ] **Step 1: Run complete scoped tests**

```powershell
.\.venv\Scripts\python.exe -m pytest `
  testing/self_tests/support/test_confluence_client.py `
  testing/self_tests/support/test_confluence_audit_rules.py `
  testing/self_tests/support/test_confluence_audit_service.py `
  testing/self_tests/support/test_confluence_audit_evidence.py `
  testing/self_tests/ui/test_confluence_audit_bridge.py `
  testing/self_tests/ui/test_tool_page.py `
  testing/self_tests/ui/test_owned_ui_translations.py `
  testing/self_tests/ui/test_frontend_persistence_contract.py -q
```

Expected: all tests pass; only existing ldap3/pyasn1 deprecation warnings are allowed.

- [ ] **Step 2: Run compilation and diff checks**

```powershell
.\.venv\Scripts\python.exe -m compileall -q support\browser_automation support\confluence_integration support\confluence_audit ui\example\bridge\ConfluenceAuditBridge.py
git diff --check
```

Expected: exit 0.

- [ ] **Step 3: Validate source startup**

Start `.\.venv\Scripts\python.exe main.py` from repository root with existing repository/UI Python paths. Confirm it remains alive for 10 seconds without QML warnings, then terminate only that validated process.

- [ ] **Step 4: Run one real read-only Muffin314 audit**

Using the existing AuthBridge transient LDAP credential:

- confirm exactly one project is reviewed;
- confirm every failed finding has explanation, guidance and page URL;
- confirm every failed finding has `captured` or a non-empty unavailable message;
- confirm at least Highlights, Stability, Test Plan, Environment and Report Store screenshots are readable;
- confirm one Confluence URL is navigated once even with multiple findings;
- confirm no password, Cookie or storage state is written.

Do not print credentials or page body.

- [ ] **Step 5: Validate UI interaction**

- load the new batch in Project Weekly Audit;
- confirm thumbnails render without truncating text;
- click a thumbnail and confirm the shared dialog displays a readable enlarged image;
- close the dialog and confirm selection/history remains unchanged;
- reload the batch from History and confirm the image still renders;
- run with evidence collector disabled/failing and confirm audit results remain unchanged.

- [ ] **Step 6: Final quality review**

Review:

```powershell
git status --short
git diff --stat
git diff --check
```

Reject duplicate Playwright launchers, duplicate storage flows, page-specific credentials, temporary diagnostics, raw secrets, unrelated changes and screenshots outside batch roots.

- [ ] **Step 7: Delivery gate**

Report Functional Acceptance and Code Quality separately. Do not commit, merge or push until Coco confirms functional completeness and requests delivery.
