from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from threading import Event, Lock, get_ident
import time
import xml.etree.ElementTree as ET

import pytest

from tool.common.daily_report import PROJECTS, DailyReportService
from tool.common.daily_report.projects import ProjectConfigStore
from tool.common.daily_report.schedule import DailyReportScheduleManager
from tool.common.daily_report.models import DailyReportIssue
from tool.common.daily_report.report import build_intelligence_html, generate_artifacts


def _issue(key="A-1", **changes):
    values = dict(
        summary="Playback blocks",
        status="Resolved",
        assignee="owner",
        priority="P0",
        components=("Player",),
        labels=("BDS_IFPD",),
        created=datetime(2026, 8, 4, 1, tzinfo=timezone.utc),
        updated=datetime(2026, 7, 20, 1, tzinfo=timezone.utc),
        url="https://jira.amlogic.com/browse/A-1",
    )
    values.update(changes)
    return DailyReportIssue(key=key, **values)


def test_fixed_project_contract_preserves_names_jql_and_recipients():
    assert [(item.safe_id, item.name, item.jql) for item in PROJECTS] == [
        ("a9-yocto", "A9 Yocto", "status not in (Closed, Done, Verified) AND labels = Linux-A9_Yocto"),
        ("a9-debian", "A9 Debian", "status not in (Closed, Done, Verified) AND labels = Linux-A9_Armbian"),
        ("a9-android16-ifpd", "A9 Android 16 IFPD", "status not in (Closed, Done, Verified) AND labels = BDS_IFPD"),
        ("a9-gaming-box", "A9 Gaming Box", "status not in (Closed, Done, Verified) AND labels = BDS_Gaming_Box"),
    ]
    assert all(item.to and item.cc for item in PROJECTS)
    assert all(address.lower().endswith("@amlogic.com") for item in PROJECTS for address in item.to + item.cc)


def test_project_store_bootstraps_defaults_and_normalizes_crud(tmp_path):
    store = ProjectConfigStore(tmp_path / "projects.json")
    assert store.list() == PROJECTS
    assert [item.subject for item in PROJECTS] == [
        f"[{item.name}] 公版状态日报" for item in PROJECTS
    ]
    saved = store.save({
        "name": "New Project",
        "jql": "labels = NEW", "to": "owner; second@amlogic.com",
        "cc": ["manager"], "enabled": True,
    })
    assert saved.to == ("owner@amlogic.com", "second@amlogic.com")
    assert saved.safe_id == "new-project"
    assert saved.cc == ("manager@amlogic.com",)
    assert saved.subject == "[New Project] 公版状态日报"
    assert store.load("new-project") == saved
    store.delete("new-project")
    assert len(store.list()) == 4
    assert (tmp_path / "projects.json").is_file()


def test_project_store_migrates_legacy_subject_on_next_write(tmp_path):
    import json
    path = tmp_path / "projects.json"
    payload = ProjectConfigStore.to_payload(PROJECTS[0]); payload.pop("subject")
    path.write_text(json.dumps([payload]), "utf-8")
    store = ProjectConfigStore(path)
    assert store.list()[0].subject == "[A9 Yocto] 公版状态日报"
    store.set_enabled("a9-yocto", False)
    assert json.loads(path.read_text("utf-8"))[0]["subject"] == "[A9 Yocto] 公版状态日报"


@pytest.mark.parametrize("change", [
    {"safe_id": "x", "name": "", "jql": "x", "to": ["a"]},
    {"safe_id": "x", "name": "X", "jql": "", "to": ["a"]},
    {"safe_id": "x", "name": "X", "jql": "x", "to": []},
])
def test_project_store_rejects_invalid_business_config(tmp_path, change):
    with pytest.raises(ValueError):
        ProjectConfigStore(tmp_path / "projects.json").save(change)


def test_project_store_rejects_duplicate_name_and_delete_to_zero(tmp_path):
    store = ProjectConfigStore(tmp_path / "projects.json", defaults=(PROJECTS[0],))
    with pytest.raises(ValueError, match="name"):
        store.save({**store.to_payload(PROJECTS[0]), "safe_id": "other"})
    with pytest.raises(ValueError, match="one project"):
        store.delete(PROJECTS[0].safe_id)


def test_global_schedule_maps_daily_and_weekly_to_public_scheduling(tmp_path):
    calls = []
    scheduler = type("Scheduler", (), {
        "upsert": lambda _self, definition: calls.append(definition) or type("State", (), {"registered": True, "enabled": True, "next_run_at": None, "reconciliation": "ok"})(),
        "delete": lambda _self, task_id: True,
        "list": lambda _self, prefix, definitions=None: [],
    })()
    manager = DailyReportScheduleManager(tmp_path / "schedule.json", scheduler=scheduler)
    manager.save("daily", hour=18, minute=30)
    manager.save("weekly", hour=9, minute=5, weekday=2)
    from support.scheduling import DailyTrigger, WeeklyTrigger
    assert calls[0].trigger == DailyTrigger(18, 30)
    assert calls[1].trigger == WeeklyTrigger(2, 9, 5)
    assert calls[1].launch.arguments[-1] == "--daily-report-run"


def test_new_batch_background_route_has_no_plan_identity():
    from main import _background_command
    calls = []
    assert _background_command(
        ["SmartTest.exe", "--daily-report-run"], daily_runner=lambda: calls.append(True) or 0
    ) == 0
    assert calls == [True]


def test_scheduled_background_reads_credential_and_sends_current_batch():
    from tool.common.daily_report.background import run_scheduled_batch
    batch = type("Batch", (), {"reports": (1,), "failures": ()})()
    service = type("Service", (), {
        "preview": lambda _self, username, password: batch,
        "send_preview": lambda _self, value: (type("Result", (), {"status": "sent"})(),),
    })()
    credentials = type("Credentials", (), {
        "read": lambda _self, ref: ("user", "password")
    })()
    assert run_scheduled_batch(credentials=credentials, service=service) == 0


def test_report_keeps_approved_canvas_yesterday_deltas_and_complete_excel(tmp_path):
    issues = (_issue("A"), _issue("B"), _issue("C"))
    trend = ((date(2026, 8, 3), 3), (date(2026, 8, 4), 3))
    artifacts = generate_artifacts(
        issues,
        trend,
        tmp_path,
        date(2026, 8, 4),
        project=PROJECTS[2],
        previous_keys={"B", "C", "D"},
    )

    html = artifacts.html_path.read_text("utf-8")
    assert "公版状态日报" in html
    assert "昨日未关闭" in html and "进入当前集合" in html and "离开当前集合" in html
    assert "font-size:34px" in html and "class=\"nowrap\"" in html
    assert html.count('class="issue-row"') == 3
    assert artifacts.excel_path.is_file()
    from PIL import Image
    with Image.open(artifacts.status_chart_path) as image:
        assert image.width >= 1200 and image.height >= 700


def test_service_builds_four_projects_with_concurrent_jira_and_safe_phase_logs(tmp_path):
    calls, threads, records = [], set(), []
    lock = Lock()

    class Record:
        key = "A-1"
        fields = {
            "summary": "x", "status": {"name": "Resolved"},
            "assignee": {"displayName": "owner"}, "priority": {"name": "P1"},
            "components": [], "labels": [], "created": None, "updated": None,
        }

    class Jira:
        def search_records(self, jql, **kwargs):
            with lock:
                calls.append((jql, kwargs.get("specs")))
                threads.add(get_ident())
            return [Record()]

    service = DailyReportService(
        issue_service_factory=lambda _username, _password: Jira(),
        project_store=ProjectConfigStore(tmp_path / "projects.json"),
        report_root=tmp_path,
        today=lambda: date(2026, 8, 4),
        logger=lambda message, **kwargs: records.append((message, kwargs.get("extra", {}))),
    )
    batch = service.preview("user", "password")

    assert [item.project for item in batch.reports] == list(PROJECTS)
    assert all(item.artifacts.html_path.is_file() for item in batch.reports)
    assert len(calls) == 4 * 14
    assert all(specs == ("key",) for _jql, specs in calls if " WAS NOT " in _jql)
    assert len(threads) > 1
    logged = repr(records)
    assert "query started" in logged and "history completed" in logged and "artifacts built" in logged
    assert "password" not in logged and "@amlogic.com" not in logged


def test_send_preview_sends_each_project_and_isolates_failure(tmp_path):
    sent = []

    class EmptyJira:
        def search_records(self, *_args, **_kwargs):
            return []

    def sender(**kwargs):
        sent.append(kwargs)
        if "A9 Debian" in kwargs["subject"]:
            raise TimeoutError("timed out")

    service = DailyReportService(
        issue_service_factory=lambda *_args: EmptyJira(),
        project_store=ProjectConfigStore(tmp_path / "projects.json"),
        report_root=tmp_path,
        sender=sender,
        today=lambda: date(2026, 8, 4),
        logger=lambda *_args, **_kwargs: None,
    )
    batch = service.preview("user", "password")
    results = service.send_preview(batch)

    assert [item.status for item in results] == ["sent", "send_failed", "sent", "sent"]
    assert len(sent) == 4
    assert all("公版状态日报" in item["subject"] for item in sent)
    assert [item["subject"] for item in sent] == [
        f"{project.subject} 2026-08-04" for project in PROJECTS
    ]
    assert all(item["to"] == project.to and item["cc"] == project.cc for item, project in zip(sent, PROJECTS))
    assert all(len(item["attachments"]) == 1 for item in sent)


def test_preview_isolates_one_project_query_failure(tmp_path):
    class Jira:
        def search_records(self, jql, **_kwargs):
            if "Linux-A9_Armbian" in jql and " WAS NOT " not in jql:
                raise OSError("offline")
            return []

    service = DailyReportService(
        issue_service_factory=lambda *_args: Jira(),
        project_store=ProjectConfigStore(tmp_path / "projects.json"),
        report_root=tmp_path,
        today=lambda: date(2026, 8, 4),
        logger=lambda *_args, **_kwargs: None,
    )
    batch = service.preview("user", "password")

    assert [item.project.name for item in batch.reports] == [
        "A9 Yocto", "A9 Android 16 IFPD", "A9 Gaming Box"
    ]
    assert [(item.project.name, item.status) for item in batch.failures] == [
        ("A9 Debian", "query_failed")
    ]


def test_service_reads_enabled_projects_from_store_each_run(tmp_path):
    store = ProjectConfigStore(tmp_path / "projects.json")
    store.set_enabled("a9-debian", False)
    calls = []
    class Jira:
        def search_records(self, jql, **_kwargs):
            calls.append(jql); return []
    service = DailyReportService(
        issue_service_factory=lambda *_args: Jira(), project_store=store,
        report_root=tmp_path / "reports", today=lambda: date(2026, 8, 4),
        logger=lambda *_args, **_kwargs: None,
    )
    batch = service.preview("user", "password")
    assert [item.project.name for item in batch.reports] == [
        "A9 Yocto", "A9 Android 16 IFPD", "A9 Gaming Box"
    ]
    assert not any("Linux-A9_Armbian" in jql for jql in calls)


def test_bridge_boundary_starts_external_work_on_a_worker_thread():
    from PySide6.QtCore import QCoreApplication
    from ui.example.bridge.DailyReportBridge import DailyReportBridge

    app = QCoreApplication.instance() or QCoreApplication([])
    main_thread = get_ident()
    called = Event()

    class Auth:
        username = "coco"
        def transientCredential(self):
            return "user", "password"

    class Service:
        def preview(self, *_args):
            assert get_ident() != main_thread
            called.set()
            return type("Batch", (), {"reports": (), "failures": ()})()

    projects = ProjectConfigStore(Path("unused-projects.json"), defaults=PROJECTS)
    projects.list = lambda: PROJECTS
    projects.enabled = lambda: PROJECTS
    projects.revision = lambda: ("fixed",)
    schedule = type("Schedule", (), {"load": lambda _self: None})()
    credentials = type("Credentials", (), {})()
    bridge = DailyReportBridge(
        Auth(), service=Service(), projects=projects, schedule=schedule,
        credentials=credentials, allowed=lambda _account: True,
    )
    bridge.generatePreview()
    deadline = time.monotonic() + 2
    while bridge.state == "running" and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert called.is_set()
    assert bridge.state == "success"


def test_bridge_lists_full_project_fields_and_invalidates_preview_on_change(tmp_path):
    from ui.example.bridge.DailyReportBridge import DailyReportBridge
    store = ProjectConfigStore(tmp_path / "projects.json")
    auth = type("Auth", (), {"username": "coco"})()
    schedule = type("Schedule", (), {"load": lambda _self: None})()
    bridge = DailyReportBridge(
        auth, service=object(), projects=store, schedule=schedule,
        credentials=object(), allowed=lambda _account: True,
    )
    bridge._batch = type("Batch", (), {"reports": (), "failures": ()})()
    bridge._preview_revision = store.revision()
    row = bridge.projectRows[0]
    assert {"projectName", "subject", "jql", "to", "cc", "enabled"} <= row.keys()
    payload = store.to_payload(store.list()[0]); payload["name"] = "Renamed"; payload["subject"] = "Custom subject"
    bridge.saveProject(payload)
    assert bridge.previewValid is False
    assert bridge.projectRows[0]["projectName"] == "Renamed"
    assert bridge.projectRows[0]["subject"] == "Custom subject"


def test_managed_qml_has_no_duplicate_title_and_exposes_approved_actions():
    source = Path(
        "ui/example/imports/example/qml/component/dailyreport/DailyReportWorkspace.qml"
    ).read_text("utf-8")
    assert 'qsTr("Daily Report")' not in source
    for text in (
        "New project", "Generate previews", "Send now", "Schedule delivery",
        "Subject: %1", "Email subject", "JQL: %1", "To: %1", "CC: %1", "Save project", "Delete",
    ):
        assert text in source
    assert "property bool editing: root.editingId === modelData.projectId" in source
    assert source.startswith("pragma ComponentBehavior: Bound")
    assert "Manage projects" not in source
    assert "manageSwitch" not in source
    assert "managementMode" not in source
    assert "property bool managing:" not in source
    assert "visible: !editing" in source
    assert "visible: editing" in source
    assert 'text: editing ? qsTr("Save project") : qsTr("Edit")' in source


def test_managed_daily_report_text_is_finished_in_both_catalogs():
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(Path("ui/example") / filename).getroot()
        contexts = [
            context for context in root.findall("context")
            if (context.findtext("name") or "").startswith("DailyReport")
        ]
        assert {context.findtext("name") for context in contexts} == {
            "DailyReportBridge", "DailyReportPreview", "DailyReportWorkspace"
        }
        for message in (
            message for context in contexts for message in context.findall("message")
        ):
            translation = message.find("translation")
            assert translation is not None
            assert translation.get("type") != "unfinished"
            assert (translation.text or "").strip()
