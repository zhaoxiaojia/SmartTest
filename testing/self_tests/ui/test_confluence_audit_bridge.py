from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QCoreApplication, QObject, Signal

from tool.common.project_weekly_audit.models import (
    AuditBatch, AuditExecutionContext, AuditFinding, AuditPeriod, ProjectAudit,
    ConfluenceProject, ProjectCandidate, ProjectCollection, ProjectCollectionFilter,
)
from tool.common.project_weekly_audit.models import AuditStatus
from tool.common.project_weekly_audit.plans import AuditPlan, AuditPlanStore
from tool.common.project_weekly_audit.scheduler import ScheduledPlanState
from support.account_dynamic_source import DynamicSourceEvent, RefreshState
from ui.example.bridge.ConfluenceAuditBridge import (
    PROJECT_SPACE_URL, ConfluenceAuditBridge,
)

app = QCoreApplication.instance() or QCoreApplication([])

class Auth(QObject):
    authChanged = Signal()
    def __init__(self, ok=True):
        super().__init__(); self.ok = ok
    def isAuthenticated(self): return self.ok
    def hasCredential(self): return self.ok
    def currentUsername(self): return "alice"
    def transientCredential(self): return ("alice", "secret") if self.ok else ("", "")

def test_bridge_rejects_audit_without_transient_ldap():
    bridge = ConfluenceAuditBridge(Auth(False))
    bridge.startAudit()
    assert bridge.viewState["state"] == "failed"
    assert bridge.viewState["canStart"] is True


def test_bridge_has_no_history_state_or_selection_api(tmp_path):
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)

    assert "history" not in bridge.viewState
    assert not hasattr(bridge, "selectHistory")

def test_bridge_runs_all_projects_and_ignores_stale_generation(monkeypatch, tmp_path):
    tz = ZoneInfo("Asia/Shanghai")
    period = AuditPeriod(datetime(2026, 7, 20, tzinfo=tz), datetime(2026, 7, 26, 23, 59, tzinfo=tz))
    project = ProjectCandidate("1", "M1", "One", "https://c/1", "https://c/home")
    batch = AuditBatch("b1", period, datetime(2026, 7, 29, tzinfo=tz), [ProjectAudit(project, [])])
    class Service:
        def run(self, criteria, period, context, progress):
            assert isinstance(criteria, ProjectCollectionFilter)
            assert context == AuditExecutionContext("manual")
            progress("reviewing", 1, 1)
            return batch
    bridge = ConfluenceAuditBridge(Auth(), service_factory=lambda u, p: Service(), history_root=tmp_path)
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    bridge.startAudit()
    assert bridge.viewState["state"] == "completed"
    assert bridge.viewState["summary"]["reviewedCount"] == 1
    assert bridge.viewState["summary"]["followUpCount"] == 0
    old = bridge.viewState.copy()
    bridge._on_worker_finished({"generation": 0, "batch": batch})
    assert bridge.viewState == old


def test_zero_eligible_projects_is_an_explicit_empty_outcome(tmp_path):
    tz = ZoneInfo("Asia/Shanghai")
    batch = AuditBatch(
        "empty",
        AuditPeriod(datetime(2026, 7, 20, tzinfo=tz), datetime(2026, 7, 26, 23, 59, tzinfo=tz)),
        datetime(2026, 7, 29, tzinfo=tz),
        [],
    )
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)
    bridge._generation = 4
    bridge._on_worker_finished({"generation": 4, "batch": batch})
    assert bridge.viewState["state"] == "empty"
    assert bridge.viewState["summary"]["reviewedCount"] == 0
    assert bridge.viewState["summary"]["followUpCount"] == 0
    assert "No eligible" in bridge.viewState["statusText"]


def test_bridge_exposes_safe_specific_auth_and_network_failures(tmp_path):
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)
    bridge._generation = 2
    bridge._on_worker_failed({"generation": 2, "kind": "auth"})
    assert "LDAP" in bridge.viewState["statusText"]
    assert "network" not in bridge.viewState["statusText"].casefold()
    bridge._on_worker_failed({"generation": 2, "kind": "network"})
    assert "network" in bridge.viewState["statusText"].casefold()
    assert "LDAP" not in bridge.viewState["statusText"]


def test_bridge_projects_and_details_include_only_actionable_follow_up(tmp_path):
    tz = ZoneInfo("Asia/Shanghai")
    period = AuditPeriod(
        datetime(2026, 7, 27, tzinfo=tz),
        datetime(2026, 7, 31, tzinfo=tz),
    )
    follow = ProjectCandidate("1", "M1", "Needs Follow Up", "https://c/status/1", "https://c/home/1")
    clean = ProjectCandidate("2", "M2", "Fully Reviewed", "https://c/status/2", "https://c/home/2")
    findings = [
        AuditFinding("M1", "Test Plan", "plan.test", AuditStatus.NOT_UPDATED,
                     "Page not updated in audit period.", page_url="https://c/plan"),
        AuditFinding("M1", "Test Information", "test.summary", AuditStatus.INVALID_FORMAT,
                     "PermissionError", page_url="https://c/info", explanation="pageId=42; HTTP 403"),
        AuditFinding("M1", "Report Store", "report.weekly", AuditStatus.UPDATED,
                     "Page updated in audit period.", page_url="https://c/report"),
    ]
    batch = AuditBatch(
        "mixed", period, datetime(2026, 7, 31, tzinfo=tz),
        [
            ProjectAudit(follow, findings),
            ProjectAudit(clean, [
                AuditFinding("M2", "Test Plan", "plan.test", AuditStatus.UPDATED, "Updated."),
            ]),
        ],
    )
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)
    bridge._generation = 9
    bridge._on_worker_finished({"generation": 9, "batch": batch})
    assert bridge.viewState["period"]["end"] == "2026-07-31T00:00:00+08:00"
    assert bridge.viewState["period"]["displayEnd"] == "2026-07-31"
    assert bridge.viewState["summary"]["reviewedCount"] == 2
    assert bridge.viewState["summary"]["followUpCount"] == 1
    assert [row["projectId"] for row in bridge.viewState["projects"]] == ["M1"]
    assert {row["status"] for row in bridge.viewState["findings"]} == {"not_updated", "invalid_format"}
    assert all(row["pageTitle"] and row["reason"] and row["url"]
               for row in bridge.viewState["findings"])


class ImmediateThread:
    def __init__(self, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class ControlledThread:
    pending = []

    def __init__(self, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        self.pending.append((self.target, self.args))

    @classmethod
    def run(cls, index=0):
        target, args = cls.pending.pop(index)
        target(*args)


def _collection(criteria):
    criteria = replace(
        criteria, source_url=PROJECT_SPACE_URL, current_stages=(),
    )
    return ProjectCollection(
        "collection", "Projects", criteria,
        datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
        (
            ConfluenceProject(
                2026, "M1", "One", "1", "https://c/1", "https://c/1",
                "Active", "IN DEVELOPMENT", "A", "Alice",
            ),
            ConfluenceProject(
                2025, "M2", "Two", "2", "https://c/2", "https://c/2",
                "Planning", "POC", "B", "Bob",
            ),
        ),
        {"support_mode": 1},
    )


def test_collection_snapshot_adapter_round_trips_all_business_fields():
    criteria = ProjectCollectionFilter(
        PROJECT_SPACE_URL, (2025, 2026), ("A",), ("ACTIVE",),
        (), ("M1",),
    )
    original = ProjectCollection(
        "catalog-7", "All projects", criteria,
        datetime(2026, 7, 30, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        (
            ConfluenceProject(
                2026, "M1", "One", "page-1", "https://c/status",
                "https://c/home", "ACTIVE", "POC", "A", "Alice",
                {"产品线": "TV", "priority": "P1"}, "One Display",
            ),
        ),
        {"year": 3}, (2024, 2025, 2026), {"permission": 2},
    )
    restored = ConfluenceAuditBridge._collection_from_payload(
        ConfluenceAuditBridge._collection_payload(original),
    )
    assert restored == original


def test_force_refresh_atomically_updates_all_options_and_preserves_valid_selection(
    tmp_path,
):
    pending = []
    first = _collection(ProjectCollectionFilter("https://c", (2026,)))
    refreshed = replace(
        first,
        projects=first.projects + (
            replace(first.projects[0], project_id="M3", support_mode="C"),
        ),
        visible_years=(2024, 2025, 2026),
    )
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        collection_factory=lambda *_args: refreshed,
        dynamic_submit=pending.append,
    )
    bridge._snapshot_cache.save(
        "confluence", bridge._dynamic_source.source, "alice",
        bridge._collection_payload(first),
        fetched_at=datetime.now(timezone.utc),
    )
    bridge.initializeCollection()
    bridge.setFilter({"supportModes": ["A"]})
    bridge.applyCollectionFilter()
    bridge.refreshCollection()
    assert bridge.viewState["catalogStatus"] == "refreshing"
    assert bridge.viewState["candidateProjects"] == []
    assert bridge.viewState["availableFilterValues"] == {
        "years": [], "supportModes": [], "projectStatuses": [],
    }
    pending.pop()()
    assert bridge.viewState["availableFilterValues"] == {
        "years": [2024, 2025, 2026],
        "supportModes": ["A", "B", "C"],
        "projectStatuses": ["ACTIVE", "PLANNING"],
    }
    assert bridge.viewState["filter"]["supportModes"] == ["A"]
    saved = bridge._snapshot_cache.load(
        "confluence", bridge._dynamic_source.source, "alice",
    )
    assert bridge._collection_from_payload(saved.payload) == refreshed


def test_collection_snapshot_adapter_rejects_unknown_or_incomplete_payload():
    for payload in ({}, {"adapterVersion": 4}, {"adapterVersion": 1}, {"adapterVersion": 2}, {"adapterVersion": 3}):
        try:
            ConfluenceAuditBridge._collection_from_payload(payload)
        except (KeyError, TypeError, ValueError):
            pass
        else:
            raise AssertionError("invalid snapshot payload was accepted")


def test_default_filter_uses_rolling_two_years(tmp_path):
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        now_factory=lambda: datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert bridge.viewState["filter"] == {
        "years": [2025, 2026],
        "supportModes": ["A"],
        "projectStatuses": ["NORMAL"],
    }
    assert bridge.viewState["availableFilterValues"] == {
        "years": [2025, 2026],
        "supportModes": ["A"],
        "projectStatuses": ["NORMAL"],
    }


def test_account_catalog_refresh_overwrites_options_without_showing_projects_until_apply(
    monkeypatch, tmp_path,
):
    calls = []

    def discover(username, password, criteria, progress):
        calls.append((username, password, criteria))
        return _collection(replace(
            criteria, years=(2025, 2026),
        ))

    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread,
    )
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, collection_factory=discover,
    )

    bridge.refreshCollection()

    assert calls[0][0:2] == ("alice", "secret")
    assert calls[0][2].years == ()
    assert calls[0][2].support_modes == ()
    assert calls[0][2].project_statuses == ()
    assert calls[0][2].current_stages == ()
    assert bridge.viewState["candidateProjects"] == []
    assert bridge.viewState["availableFilterValues"] == {
        "years": [2025, 2026],
        "supportModes": ["A", "B"],
        "projectStatuses": ["ACTIVE", "PLANNING"],
    }


def test_catalog_years_are_independent_and_enum_values_are_case_normalized(
    monkeypatch, tmp_path,
):
    collection = _collection(ProjectCollectionFilter("https://c", (2022, 2023, 2024, 2025, 2026)))
    collection = replace(
        collection,
        projects=collection.projects + (
            replace(collection.projects[0], year=2022, support_mode="c"),
        ),
        visible_years=(2022, 2023, 2024, 2025, 2026),
    )
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, collection_factory=lambda *args: collection,
    )

    bridge.refreshCollection()

    assert bridge.viewState["availableFilterValues"]["years"] == [2022, 2023, 2024, 2025, 2026]
    assert bridge.viewState["availableFilterValues"]["supportModes"].count("C") == 1

    bridge.setFilter({
        "years": [2026], "supportModes": ["A"],
        "projectStatuses": ["Active"],
    })
    assert bridge.viewState["candidateProjects"] == []
    bridge.applyCollectionFilter()
    assert [row["projectId"] for row in bridge.viewState["candidateProjects"]] == ["M1"]


def test_catalog_cache_is_isolated_by_current_account(monkeypatch, tmp_path):
    class AccountAuth(Auth):
        def __init__(self):
            super().__init__()
            self.username = "alice"
        def currentUsername(self):
            return self.username
        def transientCredential(self):
            return (self.username, "secret-" + self.username)

    def discover(username, password, criteria, progress):
        project_id = "A1" if username == "alice" else "B1"
        support_mode = "A" if username == "alice" else "B"
        project_status = "Active" if username == "alice" else "Planning"
        project = ConfluenceProject(
            2026, project_id, username, project_id, "https://c/" + project_id,
            "https://c/" + project_id, project_status, "IN DEVELOPMENT",
            support_mode, username,
        )
        return ProjectCollection(
            username, username, replace(criteria, years=(2026,)),
            datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
            (project,), {},
        )

    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread,
    )
    auth = AccountAuth()
    bridge = ConfluenceAuditBridge(
        auth, history_root=tmp_path, collection_factory=discover,
    )
    bridge.refreshCollection()
    bridge.setFilter({
        "years": [2026], "supportModes": ["A"],
        "projectStatuses": ["Active"],
    })
    bridge.applyCollectionFilter()
    assert [row["projectId"] for row in bridge.viewState["candidateProjects"]] == ["A1"]

    auth.username = "bob"
    auth.authChanged.emit()

    assert bridge.viewState["candidateProjects"] == []
    assert bridge.viewState["availableFilterValues"] == {
        "years": [2026],
        "supportModes": ["B"],
        "projectStatuses": ["PLANNING"],
    }
    bridge.applyCollectionFilter()
    assert [row["projectId"] for row in bridge.viewState["candidateProjects"]] == ["B1"]
    assert "secret-alice" not in repr(bridge.viewState)
    assert "secret-bob" not in repr(bridge.viewState)


def test_account_switch_rejects_old_async_catalog_before_disk_and_view(
    monkeypatch, tmp_path,
):
    class AccountAuth(Auth):
        def __init__(self):
            super().__init__()
            self.username = "alice"
        def currentUsername(self):
            return self.username
        def transientCredential(self):
            return self.username, "secret-" + self.username

    def discover(username, _password, criteria, _progress):
        project = ConfluenceProject(
            2026, username, username, username, f"https://c/{username}",
            f"https://c/{username}",
        )
        return ProjectCollection(
            username, username, criteria,
            datetime(2026, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            (project,),
        )

    ControlledThread.pending = []
    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.Thread", ControlledThread,
    )
    auth = AccountAuth()
    bridge = ConfluenceAuditBridge(
        auth, history_root=tmp_path, collection_factory=discover,
    )
    bridge.refreshCollection()
    auth.username = "bob"
    auth.authChanged.emit()
    ControlledThread.run(0)
    assert bridge._snapshot_cache.load(
        "confluence", bridge._dynamic_source.source, "alice",
    ) is None
    assert bridge.viewState["candidateProjects"] == []
    ControlledThread.run(0)
    assert bridge._catalog.collection_id == "bob"
    bridge.applyCollectionFilter()
    assert [row["projectId"] for row in bridge.viewState["candidateProjects"]] == ["bob"]


def test_filter_change_invalidates_previously_applied_candidates(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread,
    )
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        collection_factory=lambda *args: _collection(replace(
            args[2], years=(2025, 2026),
        )),
    )
    bridge.refreshCollection()
    bridge.applyCollectionFilter()
    assert bridge.viewState["candidateProjects"]

    bridge.toggleFilterValue("supportModes", "B")

    assert bridge.viewState["candidateProjects"] == []
    assert bridge.viewState["selectedProjectIds"] == []


def test_collection_refresh_is_async_and_exposes_candidates_and_options(monkeypatch, tmp_path):
    calls = []
    logs = []
    def discover(username, password, criteria, progress):
        calls.append((username, password, criteria))
        return _collection(criteria)
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.smart_log",
        lambda message, **kwargs: logs.append((message, kwargs)),
    )
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path, collection_factory=discover)
    bridge.refreshCollection()
    assert calls
    assert bridge.viewState["candidateProjects"] == []
    assert bridge.viewState["availableFilterValues"] == {
        "years": [2025, 2026],
        "supportModes": ["A", "B"],
        "projectStatuses": ["ACTIVE", "PLANNING"],
    }
    bridge.applyCollectionFilter()
    assert [row["projectId"] for row in bridge.viewState["candidateProjects"]] == ["M1"]
    assert bridge.viewState["collectionSummary"]["candidateCount"] == 1
    applied = next(
        kwargs["extra"] for message, kwargs in logs
        if message == "Project catalog filter applied"
    )
    assert applied["source_url"] == PROJECT_SPACE_URL
    assert applied["filtered_project_count"] == 1
    assert applied["candidate_count"] == 1


def test_repeated_manual_refresh_keeps_one_in_flight_job(tmp_path):
    pending = []
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        collection_factory=lambda *args: _collection(args[2]),
        dynamic_submit=pending.append,
    )

    bridge.refreshCollection()
    bridge.refreshCollection()

    assert len(pending) == 1


def test_manual_refresh_clears_stale_options_and_candidates_before_request(tmp_path):
    pending = []
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        collection_factory=lambda *args: _collection(args[2]),
        dynamic_submit=pending.append,
    )
    bridge._set(
        candidateProjects=[{"projectIdentity": "DOPL:1"}],
        selectedProjectIds=["DOPL:1"],
        availableFilterValues={
            "years": [2024], "supportModes": ["OLD"],
            "projectStatuses": ["STALE"],
        },
        collectionSummary={"candidateCount": 1},
    )

    bridge.refreshCollection()

    assert bridge.viewState["candidateProjects"] == []
    assert bridge.viewState["selectedProjectIds"] == []
    assert bridge.viewState["availableFilterValues"] == {
        "years": [], "supportModes": [], "projectStatuses": [],
    }
    assert bridge.viewState["collectionSummary"] == {}


def test_catalog_logs_use_stable_non_reversible_account_ids(monkeypatch, tmp_path):
    entries = []

    def capture(message, **kwargs):
        entries.append((message, kwargs))

    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.smart_log", capture)
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)

    ids = []
    for username in ("alice", "bob"):
        auth = Auth()
        auth.currentUsername = lambda value=username: value
        auth.transientCredential = lambda value=username: (value, "secret-" + value)
        bridge = ConfluenceAuditBridge(
            auth, history_root=tmp_path / username,
            collection_factory=lambda *args: _collection(args[2]),
        )
        bridge.refreshCollection()
        account_ids = {
            kwargs["extra"]["account_id"]
            for _message, kwargs in entries
            if "account_id" in kwargs.get("extra", {})
        }
        serialized_entries = repr(entries)
        assert username not in serialized_entries
        assert ("secret-" + username) not in serialized_entries
        assert len(account_ids) == 1
        ids.append(account_ids.pop())
        entries.clear()

    serialized = repr(ids)
    assert "alice" not in serialized
    assert "bob" not in serialized
    assert "secret" not in serialized
    assert all(value.startswith("acct_") for value in ids)
    assert ids[0] != ids[1]


def test_missing_confluence_dependency_is_actionable(monkeypatch, tmp_path):
    from support.confluence_integration.client import ConfluenceDependencyError

    def fail(*_args):
        raise ConfluenceDependencyError("atlassian-python-api is not installed")

    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, collection_factory=fail,
    )

    bridge.refreshCollection()

    assert bridge.viewState["state"] == "failed"
    assert "project .venv" in bridge.viewState["statusText"]


def test_selected_projects_flow_into_manual_audit_filter(monkeypatch, tmp_path):
    seen = {}
    tz = ZoneInfo("Asia/Shanghai")
    batch = AuditBatch(
        "selected",
        AuditPeriod(datetime(2026, 7, 20, tzinfo=tz), datetime(2026, 7, 27, tzinfo=tz)),
        datetime(2026, 7, 29, tzinfo=tz), [],
    )
    class Service:
        def run(self, criteria, period, context, progress):
            seen["criteria"] = criteria
            seen["context"] = context
            return batch
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, service_factory=lambda *_: Service(),
    )
    bridge.setSelectedProjects(["M2", "M1", "M2"])
    bridge.startAudit()
    assert seen["criteria"].included_project_ids == ("M2", "M1")
    assert seen["context"] == AuditExecutionContext("manual")


def test_export_excel_uses_xlsx_slot(monkeypatch, tmp_path):
    tz = ZoneInfo("Asia/Shanghai")
    batch = AuditBatch(
        "content",
        AuditPeriod(datetime(2026, 7, 20, tzinfo=tz), datetime(2026, 7, 27, tzinfo=tz)),
        datetime(2026, 7, 29, tzinfo=tz), [],
    )
    output = tmp_path / "audit.xlsx"
    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.export_project_audit_xlsx",
        lambda *args, **kwargs: output,
    )
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)
    bridge._batch = batch
    bridge.exportExcel()
    assert bridge.viewState["exportPath"] == str(output)
    assert "Excel" in bridge.viewState["statusText"]


def test_open_report_directory_uses_export_parent_and_handles_missing_path(
    monkeypatch, tmp_path,
):
    opened = []
    report = tmp_path / "reports" / "audit.xlsx"
    report.parent.mkdir()
    report.write_bytes(b"xlsx")
    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)
    bridge._set(exportPath=str(report))
    assert bridge.openReportDirectory() is True
    assert [Path(value) for value in opened] == [report.parent]
    bridge._set(exportPath=str(tmp_path / "missing.xlsx"))
    assert bridge.openReportDirectory() is False
    assert "not found" in bridge.viewState["statusText"].casefold()


class CredentialSpy:
    def __init__(self):
        self.writes = []
    def write(self, *args):
        self.writes.append(args)


class SchedulerSpy:
    def __init__(self):
        self.upserts = []
        self.enabled = []
        self.states = []
    def upsert(self, plan):
        self.upserts.append(plan)
    def set_enabled(self, plan_id, enabled):
        self.enabled.append((plan_id, enabled))
    def list(self, plans):
        return list(self.states)


def test_save_plan_writes_credential_then_upserts_and_never_exposes_secret(monkeypatch, tmp_path):
    events = []
    credentials = CredentialSpy()
    original_write = credentials.write
    credentials.write = lambda *args: (events.append("credential"), original_write(*args))
    scheduler = SchedulerSpy()
    scheduler.upsert = lambda plan: events.append("scheduler")
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, plan_store=AuditPlanStore(tmp_path / "plans"),
        credential_store=credentials, scheduler=scheduler, executable=tmp_path / "SmartTest.exe",
    )
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    assert events == ["credential", "scheduler"]
    assert credentials.writes == [("weekly-a", "alice", "secret")]
    assert "secret" not in repr(bridge.viewState)
    assert "credential_ref" not in repr(bridge.viewState)


def test_simple_weekly_plan_requires_confirmed_selected_projects_and_upserts(
    monkeypatch, tmp_path,
):
    scheduler = SchedulerSpy()
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        plan_store=AuditPlanStore(tmp_path / "plans"),
        credential_store=CredentialSpy(), scheduler=scheduler,
        collection_factory=lambda *args: _collection(args[2]),
    )

    bridge.enableWeeklyPlan()
    assert "Apply" in bridge.viewState["statusText"]
    bridge.refreshCollection()
    bridge.applyCollectionFilter()
    bridge.selectAllProjects()
    bridge.enableWeeklyPlan()
    bridge.enableWeeklyPlan()

    plans = bridge._plan_store.list()
    assert [plan.plan_id for plan in plans] == ["confluence-weekly-audit"]
    assert len(scheduler.upserts) == 2
    assert plans[0].collection_filter.included_project_ids


def test_dopl_and_sdpl_catalog_union_flows_into_selection_and_weekly_plan(
    monkeypatch, tmp_path,
):
    scheduler = SchedulerSpy()
    catalog = ProjectCollection(
        "both-spaces", "Projects",
        ProjectCollectionFilter(PROJECT_SPACE_URL, ()),
        datetime(2026, 7, 29, tzinfo=ZoneInfo("Asia/Shanghai")),
        (
            ConfluenceProject(
                2026, "SHARED", "DOPL Project", "1", "https://c/dopl",
                "https://c/dopl", "ACTIVE", support_mode="A",
                space_key="DOPL", page_identity="1",
            ),
            ConfluenceProject(
                2026, "SHARED", "SDPL Project", "1", "https://c/sdpl",
                "https://c/sdpl", "PLANNING", support_mode="B",
                space_key="SDPL", page_identity="1",
            ),
        ),
        visible_years=(2026,),
    )
    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread,
    )
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        plan_store=AuditPlanStore(tmp_path / "plans"),
        credential_store=CredentialSpy(), scheduler=scheduler,
        collection_factory=lambda *_args: catalog,
    )

    bridge.refreshCollection()
    assert bridge.viewState["availableFilterValues"] == {
        "years": [2026],
        "supportModes": ["A", "B"],
        "projectStatuses": ["ACTIVE", "PLANNING"],
    }
    bridge.setFilter({
        "years": [2026], "supportModes": [], "projectStatuses": [],
    })
    bridge.applyCollectionFilter()
    bridge.selectAllProjects()
    assert set(bridge.viewState["selectedProjectIds"]) == {
        "DOPL:1", "SDPL:1",
    }

    bridge.enableWeeklyPlan()

    plan = bridge._plan_store.load("confluence-weekly-audit")
    assert set(plan.collection_filter.included_project_ids) == {
        "DOPL:1", "SDPL:1",
    }


def test_simple_weekly_plan_reenables_a_previously_disabled_plan(
    monkeypatch, tmp_path,
):
    scheduler = SchedulerSpy()
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        plan_store=AuditPlanStore(tmp_path / "plans"),
        credential_store=CredentialSpy(), scheduler=scheduler,
        collection_factory=lambda *args: _collection(args[2]),
    )
    bridge.refreshCollection()
    bridge.applyCollectionFilter()
    bridge.selectAllProjects()
    bridge.enableWeeklyPlan()
    bridge.setPlanEnabled("confluence-weekly-audit", False)
    assert bridge._plan_store.load("confluence-weekly-audit").enabled is False

    bridge.enableWeeklyPlan()

    assert bridge._plan_store.load("confluence-weekly-audit").enabled is True
    assert scheduler.upserts[-1].enabled is True


def test_candidates_render_collection_owned_matching_years(tmp_path):
    rows = [
        ConfluenceProject(
            2026, "P1", "Current", "2", "https://c/2", "https://c/2",
            matching_years=(2025, 2026),
            space_key="DOPL", page_identity="2",
        ),
    ]

    candidates = ConfluenceAuditBridge._candidate_rows(rows)

    assert len(candidates) == 1
    assert candidates[0]["name"] == "Current"
    assert candidates[0]["projectIdentity"] == "DOPL:2"
    assert candidates[0]["matchingYears"] == [2025, 2026]


def test_candidates_with_duplicate_project_ids_use_space_qualified_selection_keys():
    rows = [
        ConfluenceProject(
            2026, "SAME", "Same", "1", "https://c/d", "https://c/d",
            space_key="DOPL", page_identity="1",
        ),
        ConfluenceProject(
            2026, "SAME", "Same", "1", "https://c/s", "https://c/s",
            space_key="SDPL", page_identity="1",
        ),
    ]

    candidates = ConfluenceAuditBridge._candidate_rows(rows)

    assert [row["projectIdentity"] for row in candidates] == [
        "DOPL:1", "SDPL:1",
    ]


def test_applied_candidate_count_uses_collection_project_identity(
    monkeypatch, tmp_path,
):
    collection = replace(
        _collection(ProjectCollectionFilter("https://c", (2025, 2026))),
        projects=(
            ConfluenceProject(
                2026, "P1", "Current", "2", "https://c/2", "https://c/2",
                matching_years=(2025, 2026),
            ),
        ),
        visible_years=(2025, 2026),
    )
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, collection_factory=lambda *args: collection,
    )

    bridge.refreshCollection()
    bridge.setFilter({"years": [2025, 2026], "supportModes": [], "projectStatuses": []})
    bridge.applyCollectionFilter()

    assert bridge.viewState["collectionSummary"]["candidateCount"] == 1
    assert len(bridge.viewState["candidateProjects"]) == 1
    assert bridge.viewState["candidateProjects"][0]["matchingYears"] == [2025, 2026]


def test_bridge_keeps_only_current_account_catalog_in_memory(monkeypatch, tmp_path):
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    auth = Auth()
    bridge = ConfluenceAuditBridge(
        auth, history_root=tmp_path,
        collection_factory=lambda *args: _collection(args[2]),
    )
    for account in ("a", "b", "c", "d", "e"):
        auth.currentUsername = lambda value=account: value
        auth.transientCredential = lambda value=account: (value, "secret")
        bridge.refreshCollection()

    assert not hasattr(bridge, "_catalogs")
    assert bridge._catalog_account_hash == bridge._snapshot_cache.identity("e")


def test_partial_catalog_warning_is_actionable_without_page_details(
    monkeypatch, tmp_path,
):
    collection = replace(
        _collection(ProjectCollectionFilter("https://c", (2026,))),
        discovery_errors={"permission": 2, "parse": 1},
    )
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, collection_factory=lambda *args: collection,
    )

    bridge.refreshCollection()

    assert "3" in bridge.viewState["statusText"]
    assert "inaccessible or unreadable" in bridge.viewState["statusText"]
    assert "permission" not in bridge.viewState["statusText"]


def test_refresh_plans_uses_reconciled_machine_state(monkeypatch, tmp_path):
    store = AuditPlanStore(tmp_path / "plans")
    scheduler = SchedulerSpy()
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, plan_store=store, scheduler=scheduler,
        credential_store=CredentialSpy(),
    )
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    scheduler.states = [
        ScheduledPlanState(
            "weekly-a", "task", False, False, None, None, None, "task_missing",
        ),
    ]
    bridge.refreshPlans()
    row = bridge.scheduleRows[0]
    assert "plans" not in bridge.viewState
    assert row["provider"] == "confluence"
    assert row["businessTitle"] == "Project Weekly Audit"
    assert row["title"] == "Weekly A"
    assert row["targetToolId"] == "confluence_audit"
    assert row["enabled"] is False
    assert row["registered"] is False
    assert row["reconciliation"] == "task_missing"


def test_stopping_plan_disables_scheduler_and_keeps_plan_row(monkeypatch, tmp_path):
    store = AuditPlanStore(tmp_path / "plans")
    scheduler = SchedulerSpy()
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, plan_store=store, scheduler=scheduler,
        credential_store=CredentialSpy(),
    )
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    scheduler.states = [
        ScheduledPlanState("weekly-a", "task", False, True, None, None, 0, "ok"),
    ]
    bridge.setPlanEnabled("weekly-a", False)
    assert scheduler.enabled[-1] == ("weekly-a", False)
    assert store.load("weekly-a").enabled is False
    assert bridge.scheduleRows[0]["planId"] == "weekly-a"


def test_refresh_collection_does_not_cancel_running_audit(monkeypatch, tmp_path):
    ControlledThread.pending = []
    tz = ZoneInfo("Asia/Shanghai")
    batch = AuditBatch(
        "audit-wins",
        AuditPeriod(datetime(2026, 7, 20, tzinfo=tz), datetime(2026, 7, 27, tzinfo=tz)),
        datetime(2026, 7, 29, tzinfo=tz), [],
    )
    discoveries = []
    class Service:
        def run(self, criteria, period, context, progress):
            return batch
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ControlledThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, service_factory=lambda *_: Service(),
        collection_factory=lambda *args: discoveries.append(args),
    )
    bridge.startAudit()
    assert len(ControlledThread.pending) == 1
    bridge.refreshCollection()
    assert len(ControlledThread.pending) == 1
    ControlledThread.run()
    assert bridge.viewState["state"] == "empty"
    assert bridge._batch is batch
    assert discoveries == []


def test_catalog_refresh_completion_cannot_orphan_running_audit(
    monkeypatch, tmp_path,
):
    ControlledThread.pending = []
    tz = ZoneInfo("Asia/Shanghai")
    batch = AuditBatch(
        "audit-terminal",
        AuditPeriod(
            datetime(2026, 7, 27, tzinfo=tz),
            datetime(2026, 7, 31, tzinfo=tz),
        ),
        datetime(2026, 7, 31, tzinfo=tz), [],
    )

    class Service:
        def run(self, criteria, period, context, progress):
            return batch

    monkeypatch.setattr(
        "ui.example.bridge.ConfluenceAuditBridge.Thread", ControlledThread,
    )
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, service_factory=lambda *_: Service(),
    )
    bridge.startAudit()
    account_hash = bridge._snapshot_cache.identity("alice")
    bridge._on_catalog_event(DynamicSourceEvent(
        RefreshState.UPDATED,
        _collection(ProjectCollectionFilter("https://c", (2025, 2026))),
        1,
        account_hash,
    ))
    ControlledThread.run()

    assert bridge.viewState["state"] == "empty"
    assert bridge.viewState["canStart"] is True
    assert bridge._batch is batch


class SequenceScheduler(SchedulerSpy):
    def __init__(self, state_sequences):
        super().__init__()
        self.state_sequences = list(state_sequences)

    def list(self, plans):
        return self.state_sequences.pop(0)


def test_stale_plan_refresh_cannot_overwrite_newer_save(monkeypatch, tmp_path):
    ControlledThread.pending = []
    stale = ScheduledPlanState(
        "weekly-a", "task", False, False, None, None, None, "task_missing",
    )
    current = ScheduledPlanState(
        "weekly-a", "task", True, True, None, None, 0, "ok",
    )
    scheduler = SequenceScheduler([[stale], [current]])
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ControlledThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, plan_store=AuditPlanStore(tmp_path / "plans"),
        credential_store=CredentialSpy(), scheduler=scheduler,
    )
    bridge.refreshPlans()
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    assert len(ControlledThread.pending) == 1
    ControlledThread.run()
    assert bridge.scheduleRows[0]["registered"] is True
    assert bridge.scheduleRows[0]["reconciliation"] == "ok"


def test_overlapping_save_and_disable_are_serialized_in_request_order(monkeypatch, tmp_path):
    ControlledThread.pending = []
    enabled = ScheduledPlanState(
        "weekly-a", "task", True, True, None, None, 0, "ok",
    )
    disabled = ScheduledPlanState(
        "weekly-a", "task", False, True, None, None, 0, "ok",
    )
    scheduler = SequenceScheduler([[enabled], [disabled]])
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ControlledThread)
    store = AuditPlanStore(tmp_path / "plans")
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, plan_store=store,
        credential_store=CredentialSpy(), scheduler=scheduler,
    )
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    bridge.setPlanEnabled("weekly-a", False)
    assert len(ControlledThread.pending) == 1
    ControlledThread.run()
    assert store.load("weekly-a").enabled is False
    assert scheduler.enabled == [("weekly-a", False)]
    assert bridge.scheduleRows[0]["enabled"] is False


def test_refresh_requested_after_save_cannot_read_pre_save_rows(monkeypatch, tmp_path):
    ControlledThread.pending = []
    current = ScheduledPlanState(
        "weekly-a", "task", True, True, None, None, 0, "ok",
    )
    scheduler = SequenceScheduler([[current], [current]])
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ControlledThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path,
        plan_store=AuditPlanStore(tmp_path / "plans"),
        credential_store=CredentialSpy(), scheduler=scheduler,
    )
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    bridge.refreshPlans()
    assert len(ControlledThread.pending) == 1
    ControlledThread.run()
    assert bridge.scheduleRows[0]["planId"] == "weekly-a"
    assert bridge.scheduleRows[0]["registered"] is True


def test_plan_row_exposes_collection_summary_from_saved_filter(monkeypatch, tmp_path):
    store = AuditPlanStore(tmp_path / "plans")
    scheduler = SchedulerSpy()
    monkeypatch.setattr("ui.example.bridge.ConfluenceAuditBridge.Thread", ImmediateThread)
    bridge = ConfluenceAuditBridge(
        Auth(), history_root=tmp_path, plan_store=store, scheduler=scheduler,
        credential_store=CredentialSpy(),
    )
    bridge.setFilter({
        "years": [2025, 2026],
        "supportModes": ["A"],
        "projectStatuses": ["Active"],
    })
    bridge.setSelectedProjects(["M1", "M2"])
    bridge.saveWeeklyPlan("weekly-a", "Weekly A")
    summary = bridge.scheduleRows[0]["collectionSummary"]
    for value in ("2025", "2026", "A", "Active", "2"):
        assert value in summary
    assert "current stages" not in summary.casefold()


def test_bridge_owns_filter_and_project_selection_mapping(tmp_path):
    bridge = ConfluenceAuditBridge(Auth(), history_root=tmp_path)
    bridge._set(candidateProjects=[
        {"projectId": "M1", "projectIdentity": "DOPL:1", "name": "One"},
        {"projectId": "M2", "projectIdentity": "SDPL:2", "name": "Two"},
    ])
    bridge.toggleFilterValue("supportModes", "B")
    assert bridge.viewState["filter"]["supportModes"] == ["A", "B"]
    bridge.toggleFilterValue("supportModes", "A")
    assert bridge.viewState["filter"]["supportModes"] == ["B"]
    bridge.toggleFilterValue("years", 2024)
    assert bridge.viewState["filter"]["years"][-1] == 2024
    bridge._set(candidateProjects=[
        {"projectId": "M1", "projectIdentity": "DOPL:1", "name": "One"},
        {"projectId": "M2", "projectIdentity": "SDPL:2", "name": "Two"},
    ])
    bridge.toggleProject("SDPL:2")
    assert bridge.viewState["selectedProjectIds"] == ["SDPL:2"]
    bridge.selectAllProjects()
    assert bridge.viewState["selectedProjectIds"] == ["DOPL:1", "SDPL:2"]
    bridge.clearSelectedProjects()
    assert bridge.viewState["selectedProjectIds"] == []
