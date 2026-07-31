# Confluence Project Collection Scheduled Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one Project Space collection and weekly-update audit flow shared by manual runs and visible Windows scheduled plans, with secure LDAP credentials and PDF reports.

**Architecture:** `ProjectCollectionFilter` drives a Project Space parser that produces a `ProjectCollection`; one audit service checks only required-page availability and weekly update timestamps. Manual UI runs and a plan-ID command entry call the same orchestration service. Windows Task Scheduler stores only the plan ID, Windows Credential Manager owns LDAP secrets, and `support/report/` owns reusable HTML-to-PDF conversion.

**Tech Stack:** Python 3.10, dataclasses, requests/Confluence Server REST, PySide6/QML, Qt WebEngine PDF, Windows Task Scheduler, Windows Credential Manager, pytest.

## Global Constraints

- Default collection uses the current and previous calendar year, `Support Mode = A`, and `Current Stage = IN DEVELOPMENT`, excluding POC, pending, and closed projects.
- Audit window is Monday `00:00` inclusive through Friday `00:00` exclusive in `Asia/Shanghai`.
- Default scheduled execution is every Friday at `00:05`.
- Existing QA page ownership from the requirements email remains unchanged.
- Current execution checks only page existence, readability, and weekly update time; content rules and DeepSeek review remain implemented but disabled.
- Manual and scheduled execution must call the same collection, audit, screenshot, history, and PDF owners.
- Jira Format Audit remains XLSX.
- LDAP passwords must never enter JSON, command lines, Windows task arguments, logs, history, frontend persistence, or PDF.
- Screenshot failure must not change a business audit status.
- Preserve all pre-existing and user-owned workspace changes.
- Do not commit until Coco confirms functional completeness; plan checkpoints use `git diff --check` instead of commits.

---

### Task 1: Project collection domain model and pure filter

**Files:**
- Modify: `support/confluence_audit/models.py`
- Create: `support/confluence_audit/project_collection.py`
- Test: `testing/self_tests/support/test_confluence_project_collection.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class ConfluenceProject:
    year: int
    project_id: str
    name: str
    status_page_id: str
    status_url: str
    home_url: str
    project_status: str = ""
    current_stage: str = ""
    support_mode: str = ""
    project_owner: str = ""
    attributes: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class ProjectCollectionFilter:
    source_url: str
    years: tuple[int, ...]
    support_modes: tuple[str, ...] = ()
    project_statuses: tuple[str, ...] = ()
    current_stages: tuple[str, ...] = ()
    included_project_ids: tuple[str, ...] = ()

@dataclass(frozen=True)
class ProjectCollection:
    collection_id: str
    name: str
    filter: ProjectCollectionFilter
    discovered_at: datetime
    projects: tuple[ConfluenceProject, ...]
    excluded_counts: dict[str, int] = field(default_factory=dict)

def default_project_filter(now: datetime, source_url: str) -> ProjectCollectionFilter: ...
def filter_projects(projects: Iterable[ConfluenceProject], criteria: ProjectCollectionFilter) -> ProjectCollection: ...
```

- Existing `ProjectCandidate` remains the audit-facing page-discovery model until Task 3 provides the explicit conversion.

- [ ] **Step 1: Write failing model and filter tests**

Add tests proving:

```python
def test_default_filter_uses_current_and_previous_year():
    criteria = default_project_filter(
        datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
        PROJECT_SPACE_URL,
    )
    assert criteria.years == (2025, 2026)
    assert criteria.support_modes == ("A",)
    assert criteria.current_stages == ("IN DEVELOPMENT",)

def test_filter_normalizes_values_and_applies_explicit_project_selection():
    collection = filter_projects(
        [
            project("P1", year=2026, support_mode=" a ", current_stage="2 IN DEVELOPMENT"),
            project("P2", year=2026, support_mode="B", current_stage="2 IN DEVELOPMENT"),
            project("P3", year=2025, support_mode="A", current_stage="PENDING"),
        ],
        ProjectCollectionFilter(
            PROJECT_SPACE_URL, (2025, 2026), ("A",), (), ("IN DEVELOPMENT",), ("P1",)
        ),
    )
    assert [row.project_id for row in collection.projects] == ["P1"]
    assert collection.excluded_counts == {"support_mode": 1, "current_stage": 1}

def test_collection_id_is_stable_when_input_order_changes():
    assert filter_projects([P1, P2], FILTER).collection_id == filter_projects([P2, P1], FILTER).collection_id
```

The stage matcher treats prefixed values such as `2 IN DEVELOPMENT` as the normalized semantic value `IN DEVELOPMENT`; it rejects POC, pending and closed values.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_project_collection.py -q
```

Expected: import failure because the model and filter owner do not exist.

- [ ] **Step 3: Implement immutable models and deterministic filtering**

Use one normalization helper for whitespace/case and one stable SHA-256 digest over sorted JSON filter fields. Sort resulting projects by `(year, name.casefold(), project_id)`. Do not put Confluence I/O in this module.

- [ ] **Step 4: Run GREEN tests**

Run Step 2. Expected: PASS.

- [ ] **Step 5: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 2: Project Space and year-page discovery

**Files:**
- Modify: `support/confluence_integration/client.py`
- Modify: `support/confluence_integration/models.py`
- Modify: `support/confluence_audit/discovery.py`
- Test: `testing/self_tests/support/test_confluence_client.py`
- Create: `testing/self_tests/support/test_confluence_project_discovery.py`

**Interfaces:**
- Consumes: `ProjectCollectionFilter`, `ConfluenceProject`, `filter_projects`.
- Produces:

```python
class ProjectCollectionDiscoveryError(RuntimeError): ...

def discover_project_collection(
    client: ConfluenceClient,
    criteria: ProjectCollectionFilter,
    progress: Callable[[int, int], None] = lambda *_: None,
) -> ProjectCollection: ...
```

- `ConfluenceClient.get_page_children(page_id: str) -> list[ConfluencePage]` uses the Confluence Server REST child endpoint with pagination.
- `ConfluenceClient.get_page_by_url(...)` remains the single page-fetch owner.

- [ ] **Step 1: Add failing client pagination tests**

Use fake HTTP responses to prove `get_page_children` follows `start`/`limit`, preserves page IDs, URLs, version and update timestamps, and stops at the reported total.

- [ ] **Step 2: Add failing discovery tests using captured table-shaped HTML fixtures**

Cover:

```python
def test_discovers_projects_from_requested_year_pages_by_header_name(): ...
def test_column_order_does_not_change_project_fields(): ...
def test_missing_requested_year_page_reports_the_year(): ...
def test_missing_project_id_or_support_mode_header_is_a_collection_error(): ...
def test_duplicate_project_id_with_conflicting_status_is_a_collection_error(): ...
```

Fixture headers must include the real Project Space vocabulary: `页面`, `Project ID`, `Project Status`, `Current Stage`, `Support Mode`, and `Project Owner`.

- [ ] **Step 3: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_client.py testing/self_tests/support/test_confluence_project_discovery.py -q
```

Expected: missing child API and discovery function failures.

- [ ] **Step 4: Implement semantic table parsing**

Read the Project Space page, resolve exact `<year> Projects` descendants or links, load only requested years, parse tables by normalized header label, and construct `ConfluenceProject`. Derive `status_page_id` from the row page link when its URL contains a page ID; otherwise retain the canonical status URL and let the existing client resolve it.

Do not rely on fixed table column indexes or the currently expanded sidebar.

- [ ] **Step 5: Run GREEN tests**

Run Step 3. Expected: PASS.

- [ ] **Step 6: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 3: Update-only audit rule set and unified orchestration

**Files:**
- Modify: `support/confluence_audit/rules.py`
- Modify: `support/confluence_audit/service.py`
- Modify: `support/confluence_audit/models.py`
- Modify: `support/confluence_audit/store.py`
- Modify: `support/confluence_audit/evidence.py`
- Test: `testing/self_tests/support/test_confluence_audit_rules.py`
- Test: `testing/self_tests/support/test_confluence_audit_service.py`
- Test: `testing/self_tests/support/test_confluence_audit_evidence.py`

**Interfaces:**
- Consumes: `ProjectCollectionFilter`, `discover_project_collection`.
- Produces:

```python
@dataclass(frozen=True)
class AuditExecutionContext:
    trigger: Literal["manual", "scheduled"]
    plan_id: str = ""

class WeeklyUpdateAuditService:
    def audit(
        self,
        project: ProjectCandidate,
        pages: Mapping[str, ConfluencePage],
        period: AuditPeriod,
        facts: Mapping[str, PageAuditFacts],
        unreadable: set[str] | None = None,
    ) -> list[AuditFinding]: ...

class ConfluenceAuditService:
    def run(
        self,
        criteria: ProjectCollectionFilter,
        period: AuditPeriod,
        context: AuditExecutionContext,
        progress: Callable[[str, int, int], None] = lambda *_: None,
    ) -> AuditBatch: ...
```

- `AuditBatch` schema version increments and stores collection filter summary plus execution context without credentials.
- `StaticAuditService` remains the owner of dormant content rules but is not constructed or called by the active flow.

- [ ] **Step 1: Write failing boundary-time tests**

For every active QA page kind, prove:

```python
@pytest.mark.parametrize("updated_at,expected", [
    ("2026-07-27T00:00:00+08:00", AuditStatus.PASSED),
    ("2026-07-30T23:59:59+08:00", AuditStatus.PASSED),
    ("2026-07-31T00:00:00+08:00", AuditStatus.FAILED),
])
def test_required_page_uses_half_open_weekly_window(updated_at, expected): ...
```

Also prove missing page is `failed`, unreadable page is `unknown`, and unavailable version/update metadata is `unknown`.

- [ ] **Step 2: Write failing content-disable tests**

Inject a reviewer and a `StaticAuditService` sentinel that raises if called. Feed pages containing bad metrics, missing Highlights links, template placeholders, incomplete environment content and no report attachment. Assert the active result depends only on update timestamps and the sentinels are never called.

- [ ] **Step 3: Write failing unified-service tests**

Assert manual and scheduled contexts with the same filter produce identical projects and findings, differing only in context metadata. Assert service discovery receives the supplied filter exactly once.

- [ ] **Step 4: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_rules.py testing/self_tests/support/test_confluence_audit_service.py testing/self_tests/support/test_confluence_audit_evidence.py -q
```

Expected: interface and behavior failures.

- [ ] **Step 5: Implement the update-only owner**

For each required page, use the already resolved version/update fact. Do not parse body text, attachments, tables, task macros or AI prompts. Convert each `ConfluenceProject` to the existing `ProjectCandidate` at the boundary, preserving project identity and URLs.

Update screenshot target mapping so all update failures capture the relevant page main content. Keep capture non-blocking.

- [ ] **Step 6: Add schema migration**

Load older history batches by supplying default collection and execution metadata. Never rewrite existing history files during read.

- [ ] **Step 7: Run GREEN tests**

Run Step 4. Expected: PASS.

- [ ] **Step 8: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 4: Global report package and Project Weekly Audit PDF

**Files:**
- Delete: `support/report.py`
- Create: `support/report/__init__.py`
- Create: `support/report/pdf.py`
- Create: `support/report/run_report.py`
- Create: `support/confluence_audit/report.py`
- Delete: `support/confluence_audit/exporter.py`
- Modify: `ui/example/bridge/RunBridge.py`
- Modify: `ui/example/bridge/ReportBridge.py`
- Modify: `testing/test_context.py`
- Create: `testing/self_tests/support/test_report.py`
- Create: `testing/self_tests/support/test_confluence_audit_pdf.py`

**Interfaces:**
- `support.report.__init__` re-exports all current `support.report` public run-report functions unchanged.
- Produces:

```python
def render_html_to_pdf(
    html: str,
    output_path: Path,
    *,
    base_url: QUrl | None = None,
    timeout_ms: int = 30_000,
) -> Path: ...

def render_project_audit_html(batch: AuditBatch) -> str: ...

def export_project_audit_pdf(batch: AuditBatch, output_dir: Path) -> Path: ...
```

- `support/report/pdf.py` is the only Qt WebEngine HTML-to-PDF owner.
- Project report HTML receives already-safe local screenshot URIs from batch-relative validated paths; it never accepts arbitrary filesystem paths.

- [ ] **Step 1: Write compatibility and PDF RED tests**

Assert existing imports from `support.report` still resolve after package migration. Add Project Audit tests proving the HTML contains:

- collection/filter summary;
- only failed/risk/unknown findings;
- explanation and guidance;
- each valid screenshot as an embedded local or data URI;
- each Confluence URL as an `<a href>`;
- no LDAP value;
- `manual` or `scheduled` metadata.

Add a Qt PDF adapter test with a fake page to prove load failure, print failure and timeout raise actionable errors.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_report.py testing/self_tests/support/test_confluence_audit_pdf.py -q
```

Expected: missing package and Project PDF functions.

- [ ] **Step 3: Move existing report code without changing public behavior**

Move run-report model and HTML code to `run_report.py`; move only generic Qt conversion to `pdf.py`; re-export old names from `__init__.py`. Update internal imports only where needed.

- [ ] **Step 4: Implement Project Audit HTML and PDF**

Use print CSS with A4 margins, page-break-safe finding cards, bounded screenshot dimensions, visible URLs and clickable anchors. Filename:

`project_weekly_audit_<batch-id>.pdf`

Remove the Confluence XLSX dependency and exporter. Do not change Jira audit XLSX.

- [ ] **Step 5: Run GREEN and regression tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_report.py testing/self_tests/support/test_confluence_audit_pdf.py testing/self_tests/support/test_jira_format_audit_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 5: Plan storage and Windows Credential Manager

**Files:**
- Create: `support/confluence_audit/plans.py`
- Create: `support/windows_credentials.py`
- Test: `testing/self_tests/support/test_confluence_audit_plans.py`
- Test: `testing/self_tests/support/test_windows_credentials.py`
- Modify dependency declarations only if repository inspection proves no maintained Credential Manager library is already declared.

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class AuditPlan:
    plan_id: str
    name: str
    collection_filter: ProjectCollectionFilter
    enabled: bool
    credential_ref: str
    task_name: str
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    last_status: str = ""
    last_report_path: str = ""

class AuditPlanStore:
    def save(self, plan: AuditPlan) -> Path: ...
    def load(self, plan_id: str) -> AuditPlan: ...
    def list(self) -> list[AuditPlan]: ...
    def update_result(self, plan_id: str, *, status: str, report_path: str, run_at: datetime) -> AuditPlan: ...

class WindowsCredentialStore:
    def write(self, credential_ref: str, username: str, password: str) -> None: ...
    def read(self, credential_ref: str) -> tuple[str, str]: ...
    def delete(self, credential_ref: str) -> None: ...
```

- Credential target format: `SmartTest/ProjectWeeklyAudit/<credential_ref>`.
- Plan JSON stores `credential_ref`, never username or password.

- [ ] **Step 1: Search and document dependency reuse**

Inspect declared dependencies and environment for `keyring` or `pywin32`. Prefer the maintained existing dependency. If neither exists, use Python's `ctypes` only for the narrow Windows Credential Manager API and record why no existing managed dependency was available.

- [ ] **Step 2: Write failing plan-store tests**

Cover schema round-trip, deterministic list order, invalid plan IDs, atomic writes, result updates, and serialized JSON absence of username/password.

- [ ] **Step 3: Write failing credential-store tests**

Use an injected native adapter so tests do not write real credentials. Prove target naming, Unicode username/password round-trip, missing credential error, and buffer cleanup call.

- [ ] **Step 4: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_plans.py testing/self_tests/support/test_windows_credentials.py -q
```

Expected: missing owner modules.

- [ ] **Step 5: Implement versioned atomic plan storage**

Use one JSON file per plan under the SmartTest application-data plan directory and `Path.replace` for atomic updates. Reject path separators and non `[A-Za-z0-9_-]` plan IDs.

- [ ] **Step 6: Implement Credential Manager adapter**

Credentials are generic credentials scoped to the current Windows user. Never include secret values in exception messages or `repr`.

- [ ] **Step 7: Run GREEN tests**

Run Step 4. Expected: PASS.

- [ ] **Step 8: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 6: Windows Task Scheduler owner and background command

**Files:**
- Create: `support/confluence_audit/scheduler.py`
- Create: `support/confluence_audit/command.py`
- Modify: `support/packaging/pyinstaller/main.spec`
- Modify packaging/dependency initialization only where required for the chosen Windows scheduler API.
- Test: `testing/self_tests/support/test_confluence_audit_scheduler.py`
- Test: `testing/self_tests/support/test_confluence_audit_command.py`

**Interfaces:**
- Consumes: `AuditPlanStore`, `WindowsCredentialStore`, `ConfluenceAuditService`, Project PDF exporter.
- Produces:

```python
TASK_PREFIX = "SmartTest.ProjectWeeklyAudit."

@dataclass(frozen=True)
class ScheduledPlanState:
    plan_id: str
    task_name: str
    enabled: bool
    registered: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result_code: int | None
    reconciliation: Literal["ok", "config_missing", "task_missing", "invalid_task"]

class WindowsAuditScheduler:
    def upsert(self, plan: AuditPlan, executable: Path) -> ScheduledPlanState: ...
    def set_enabled(self, plan_id: str, enabled: bool) -> ScheduledPlanState: ...
    def list(self, plans: Sequence[AuditPlan]) -> list[ScheduledPlanState]: ...

def run_plan(plan_id: str, dependencies: CommandDependencies | None = None) -> int: ...
```

- Scheduled action arguments contain only the application background-audit switch and `plan_id`.
- Weekly trigger is Friday `00:05` local time.

- [ ] **Step 1: Select the maintained scheduler boundary**

Reuse Windows Task Scheduler COM through existing `pywin32` if declared. If unavailable, use one narrowly injected `schtasks.exe` adapter with argument arrays and XML query parsing; never build shell command strings.

- [ ] **Step 2: Write failing scheduler tests with a fake adapter**

Prove:

- task name uses the fixed prefix and plan ID;
- action contains plan ID but no credentials or filter JSON;
- Friday `00:05` trigger;
- repeated `upsert` updates one task;
- stop disables without deleting;
- enable reuses the same task;
- list reconciles `ok`, `config_missing`, `task_missing`, and `invalid_task`;
- unrelated Windows tasks are ignored.

- [ ] **Step 3: Write failing command tests**

Inject fake plan, credential, audit and PDF owners. Assert:

```python
def test_run_plan_uses_same_audit_service_and_records_pdf(): ...
def test_missing_credential_records_auth_failure_without_deleting_plan(): ...
def test_command_never_logs_or_serializes_password(caplog, tmp_path): ...
```

- [ ] **Step 4: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_scheduler.py testing/self_tests/support/test_confluence_audit_command.py -q
```

Expected: missing scheduler and command modules.

- [ ] **Step 5: Implement scheduler and command**

The command loads a plan, reads credentials, creates the normal service dependencies, calls `service.run(plan.collection_filter, period, scheduled_context)`, exports PDF, updates plan result, and returns:

- `0` success;
- `2` plan/config failure;
- `3` credential/auth failure;
- `4` collection/audit failure;
- `5` PDF/report failure.

Use `smart_log` with plan ID and status only.

- [ ] **Step 6: Wire packaged and source entry**

Add one application argument handled before GUI startup:

```text
SmartTest.exe --project-weekly-audit-plan <plan_id>
```

Source validation uses:

```text
python main.py --project-weekly-audit-plan <plan_id>
```

Do not create a parallel executable unless packaging inspection proves the main executable cannot support the command.

- [ ] **Step 7: Run GREEN tests and compile**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/support/test_confluence_audit_scheduler.py testing/self_tests/support/test_confluence_audit_command.py -q
.\.venv\Scripts\python.exe -m compileall support/confluence_audit support/windows_credentials.py
```

Expected: both commands exit `0`.

- [ ] **Step 8: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 7: Bridge collection filters, manual audit, PDF and plan management

**Files:**
- Modify: `ui/example/bridge/ConfluenceAuditBridge.py`
- Test: `testing/self_tests/ui/test_confluence_audit_bridge.py`

**Interfaces:**
- Consumes: collection discovery, unified audit service, PDF exporter, plan store, credential store and scheduler.
- Extends `viewState` with:

```python
{
    "filter": {
        "sourceUrl": str,
        "years": list[int],
        "supportModes": list[str],
        "projectStatuses": list[str],
        "currentStages": list[str],
    },
    "availableFilterValues": {
        "years": list[int],
        "supportModes": list[str],
        "projectStatuses": list[str],
        "currentStages": list[str],
    },
    "candidateProjects": list[dict],
    "selectedProjectIds": list[str],
    "plans": list[dict],
    "collectionSummary": dict,
    "pdfPath": str,
}
```

- Produces slots:

```python
refreshCollection()
setFilter(object filter_value)
setSelectedProjects(object project_ids)
startAudit()
exportPdf()
saveWeeklyPlan(str plan_id, str name)
setPlanEnabled(str plan_id, bool enabled)
refreshPlans()
```

- [ ] **Step 1: Write failing bridge tests**

Cover:

- default filter uses rolling two years;
- collection refresh is asynchronous and exposes actual candidates/options;
- selected project IDs flow into `included_project_ids`;
- manual audit passes `AuditExecutionContext("manual")`;
- export creates PDF and status text says PDF;
- saving a plan writes credentials through `WindowsCredentialStore`, then upserts one scheduler task;
- view state never contains password or credential secret;
- refreshing plans displays actual reconciled machine state;
- stopping calls scheduler disable and keeps the row/history;
- auth failure asks for LDAP reauthentication.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_confluence_audit_bridge.py -q
```

Expected: missing fields, slots and new service interface.

- [ ] **Step 3: Implement one bridge state owner**

Keep QML presentation-only. Use background threads for Confluence discovery/audit and bounded local scheduler queries. Persist non-sensitive filter preferences through the existing frontend persistence owner only if that owner already supports the page; never persist credentials there.

- [ ] **Step 4: Run GREEN tests**

Run Step 2. Expected: PASS.

- [ ] **Step 5: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 8: QML filter, project selection and visible plan management

**Files:**
- Modify: `ui/example/imports/example/qml/component/confluenceaudit/ConfluenceAuditWorkspace.qml`
- Modify: `ui/example/example_en_US.ts`
- Modify: `ui/example/example_zh_CN.ts`
- Regenerate: `ui/example/imports/resource_rc.py`
- Test: `testing/self_tests/ui/test_tool_page.py`
- Test: `testing/self_tests/ui/test_owned_ui_translations.py`

**Interfaces:**
- Consumes the Task 7 view-state fields and slots.
- Stable object names:
  - `confluenceAuditSourceUrl`
  - `confluenceAuditYearFilter`
  - `confluenceAuditSupportModeFilter`
  - `confluenceAuditProjectStatusFilter`
  - `confluenceAuditCurrentStageFilter`
  - `confluenceAuditRefreshCollectionButton`
  - `confluenceAuditProjectChecklist`
  - `confluenceAuditPlanList`
  - `confluenceAuditSavePlanButton`
  - `confluenceAuditPlanEnabledSwitch`
  - `exportConfluenceAuditPdfButton`

- [ ] **Step 1: Write failing QML and translation contract tests**

Assert every stable object name exists, visible strings use `qsTr`, both translation catalogs contain all new strings without `unfinished`, and no `Export XLSX` remains in the Confluence workspace.

- [ ] **Step 2: Run RED tests**

```powershell
.\.venv\Scripts\python.exe -m pytest testing/self_tests/ui/test_tool_page.py testing/self_tests/ui/test_owned_ui_translations.py -q
```

Expected: missing UI contracts and translations.

- [ ] **Step 3: Implement collection controls**

Use existing FluentUI components. Show compact multi-select filter controls, candidate count, refresh state and a scrollable project checklist. The checklist reflects the current filtered collection and allows selecting all or a subset.

- [ ] **Step 4: Implement plan list**

Each plan row shows:

- name;
- collection summary;
- enabled/stopped/reconciliation state;
- next run;
- last run and result;
- recent report action;
- enable/stop control.

Do not display a delete action in this phase. A stopped plan remains visible.

- [ ] **Step 5: Change Project export wording to PDF**

Button, success, failure and path text refer to PDF. Jira workspace retains `Export XLSX`.

- [ ] **Step 6: Rebuild resources**

```powershell
.\.venv\Scripts\pyside6-rcc.exe ui\example\imports\resource.qrc -o ui\example\imports\resource_rc.py
```

Expected: exit `0`.

- [ ] **Step 7: Run GREEN tests**

Run Step 2. Expected: PASS.

- [ ] **Step 8: Record checkpoint**

Run `git diff --check`; do not commit.

---

### Task 9: Full regression and live Windows acceptance

**Files:**
- Modify only files required by defects reproduced during this task.
- No exploratory scripts or credentials remain in the repository.

**Interfaces:**
- Validates the complete specification; introduces no new production interface.

- [ ] **Step 1: Run the complete focused suite**

```powershell
.\.venv\Scripts\python.exe -m pytest `
  testing/self_tests/support/test_confluence_client.py `
  testing/self_tests/support/test_confluence_project_collection.py `
  testing/self_tests/support/test_confluence_project_discovery.py `
  testing/self_tests/support/test_confluence_audit_rules.py `
  testing/self_tests/support/test_confluence_audit_service.py `
  testing/self_tests/support/test_confluence_audit_evidence.py `
  testing/self_tests/support/test_confluence_audit_pdf.py `
  testing/self_tests/support/test_confluence_audit_plans.py `
  testing/self_tests/support/test_windows_credentials.py `
  testing/self_tests/support/test_confluence_audit_scheduler.py `
  testing/self_tests/support/test_confluence_audit_command.py `
  testing/self_tests/ui/test_confluence_audit_bridge.py `
  testing/self_tests/ui/test_tool_page.py `
  testing/self_tests/ui/test_owned_ui_translations.py -q
```

Expected: zero failures.

- [ ] **Step 2: Run source and compile validation**

```powershell
.\.venv\Scripts\python.exe -m compileall support/confluence_audit support/report ui/example/bridge/ConfluenceAuditBridge.py
.\.venv\Scripts\python.exe main.py
```

Confirm source startup reaches the Tool page without stderr errors. Do not rebuild the desktop package.

- [ ] **Step 3: Perform real Project Space read-only validation**

With LDAP credentials:

1. refresh the default collection from the real Project Space;
2. verify years are 2025 and 2026;
3. sample the parsed row values against visible Confluence columns;
4. confirm every included project is A and IN DEVELOPMENT;
5. confirm POC, pending and closed rows are excluded;
6. run a manual audit;
7. verify content quality does not create findings;
8. verify missing, unreadable and not-updated pages do create findings;
9. verify failure screenshots open and enlarge;
10. export PDF and verify embedded screenshots and clickable links.

- [ ] **Step 4: Perform real plan lifecycle validation**

Use one explicitly named acceptance plan:

`SmartTest Project Weekly Audit Acceptance`

1. save it with current LDAP credentials;
2. verify Credential Manager contains the SmartTest target and plan JSON contains no password;
3. verify exactly one Windows task exists with the SmartTest prefix;
4. save again and verify no duplicate task;
5. verify trigger is Friday `00:05`;
6. stop it and verify the task is disabled while the plan remains visible;
7. re-enable it and verify the same task is reused;
8. run the background command manually by plan ID while the GUI is closed;
9. verify history and PDF are produced and plan last-result fields update;
10. stop the acceptance plan before handoff unless Coco explicitly asks to leave it enabled.

- [ ] **Step 5: Security inspection**

Search the plan directory, history, logs, generated PDF text and Windows task action for the test password. Expected: zero matches. Do not print the password in command output; use a test-only sentinel known to the validation process and report only the match count.

- [ ] **Step 6: Final quality review**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Review scoped differences for:

- one collection/filter owner;
- one audit execution chain;
- one scheduler owner;
- one Credential Manager owner;
- one PDF conversion owner;
- no active content/AI review calls;
- no temporary diagnostics or exploratory artifacts;
- no unrelated user-owned changes.

- [ ] **Step 7: Functional handoff without commit**

Report changed files, exact test commands and exit codes, real collection/project counts, plan lifecycle evidence, PDF path, limitations and relevant dirty status. Wait for Coco's functional confirmation before cleanup review and commit.
