import asyncio
import time
from pathlib import Path
from threading import Event

import pytest

from PySide6.QtCore import QCoreApplication, QObject, Signal

from support.jira_integration.core import UnifiedIssue
from tool.SmartHome.redmine.models import AuthResult, AuthState
from support.jira_integration.core.create_schema import CreateFieldControl, CreateFieldOption, CreateFieldSchema
from support.jira_integration.core.models import (
    AttachmentSyncResult,
    AttachmentTransferResult,
    CreateIssueAttachment,
    CreateIssueResult,
    ExistingIssue,
    JiraAttachmentMetadata,
)
from tool.SmartHome.redmine.clone_draft import RedmineCloneDraftService
from tool.SmartHome.redmine.issue_controller import RedmineIssueController
from tool.SmartHome.redmine.models import RedmineAttachment, RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineJournal, RedmineProject
from tool.SmartHome.redmine.view_model import view
from ui.example.bridge.RedmineBridge import RedmineBridge, _AsyncLoopWorker, _download_redmine_attachments, _native_query
from ui.example.bridge.ToolBridge import build_tool_groups


def _issue_record(
    issue_id,
    *,
    title="",
    web_url="",
    description=None,
    clone_state="not_cloned",
    clone_key="",
    clone_url="",
):
    return UnifiedIssue(
        id=str(issue_id),
        key=str(issue_id),
        source_system="redmine",
        source_url=web_url,
        title=title,
        web_url=web_url,
        description=description or "",
        detail_state="loaded" if description is not None else "unloaded",
        clone={
            "state": clone_state,
            "issue_key": clone_key,
            "issue_url": clone_url,
            "checked": clone_state == "cloned",
        },
    )


def _set_bridge_records(bridge, records, *, selected_id="", context=None, filters=None):
    bridge._issue_controller._replace_records(records, selected_id)
    if context is not None:
        bridge._issue_controller._source_context = context
    if filters is not None:
        bridge._issue_controller._filters = bridge._issue_controller._filters | filters


def _set_bridge_projection(bridge, context, projected):
    controller = bridge._issue_controller
    controller._source_context = context
    controller._filters = dict(projected["filters"])
    controller._project_filter_labels = tuple(projected["projectFilterLabels"])
    controller._replace_records(
        projected["issue_list"], projected.get("selectedIssueId")
    )


def test_bridge_resolves_tracker_label_through_native_metadata():
    class Collector:
        async def collect_filter_metadata(self, *, project=""):
            assert project == "p"
            return {"Bug": "1", "Support": "3"}
    query = asyncio.run(_native_query(Collector(), {"project": "p", "status": "Open", "type": "Bug"}))
    params = query.branches()[0].params(1, 100)
    assert ("op[status_id]", "o") in params
    assert ("v[tracker_id][]", "1") in params
    assert not any(value == "Bug" for _key, value in params)


def test_bridge_rejects_unknown_tracker_label_without_sending_it_as_id():
    import pytest
    class Collector:
        async def collect_filter_metadata(self, *, project=""):
            return {"Bug": "1"}
    with pytest.raises(ValueError, match="unavailable"):
        asyncio.run(_native_query(Collector(), {"type": "Support"}))


def test_native_query_projects_use_only_synced_business_project_ids_for_clone_mapping():
    known_issue = RedmineIssueListItem(id="1", url="u1", tracker="Bug", subject="known")
    unknown_issue = RedmineIssueListItem(id="2", url="u2", tracker="Bug", subject="unknown")
    context = RedmineContext(projects=(
        RedmineProject(name="Known", identifier="known", url="p1", project_id="", issues=(known_issue,)),
        RedmineProject(name="Unknown", identifier="unknown", url="p2", project_id="", issues=(unknown_issue,)),
    ))
    controller = RedmineIssueController(
        all_projects="All projects",
    )
    reconciled = controller.reconcile_project_ids(
        context, [{"id": "known", "projectId": "REAL-PID"}]
    )
    assert [project.project_id for project in reconciled.projects] == ["REAL-PID", ""]


def test_watched_all_syntactically_invalid_preserves_old_state_without_network(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    bridge._watched_issue_text = "60371"
    _set_bridge_records(bridge, [_issue_record("60371")], selected_id="60371")
    launched = []
    monkeypatch.setattr(bridge, "_launch_watched_query", lambda *args, **kwargs: launched.append((args, kwargs)))
    bridge.saveWatchedIssueIds("6037l")
    assert launched == []
    assert bridge.watchedIssueText == "6037l"
    assert "6037l" in bridge.watchedIssueError
    assert [row["id"] for row in bridge.issueRows] == ["60371"]
    bridge.close()


def test_watched_mixed_tokens_queries_numeric_candidates_and_keeps_token_order(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    launched = []
    monkeypatch.setattr(bridge, "_load_quick_view_cache", lambda *_args: None)
    monkeypatch.setattr(bridge, "_launch_watched_query", lambda ids, **kwargs: launched.append((tuple(ids), kwargs)))
    bridge.saveWatchedIssueIds("60371 abc 999999")
    assert launched == [(('60371', '999999'), {'validate': True, 'submitted_terms': ('60371', 'abc', '999999')})]
    assert bridge.watchedIssueText == "60371 abc 999999"
    bridge.close()


def test_watched_mixed_result_saves_valid_numeric_and_reports_all_invalid_in_input_order(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    bridge._data_generation = 4
    bridge._data_loading = True
    bridge._data_operation_kind = "watched"
    issue = RedmineIssueListItem(id="60371", url="u", tracker="Bug", status="New", subject="valid")
    context = RedmineContext(projects=(RedmineProject(name="P", identifier="p", url="p", project_id="PID", issues=(issue,)),))
    saved = []
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_watched_issue_ids", lambda _account, ids: saved.append(ids))
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_quick_view", lambda *_args, **_kwargs: None)
    bridge._apply_data(4, (context, "", None, {}, {}, ("60371", "999999"), ("60371", "abc", "999999"), True))
    assert saved == [["60371"]]
    assert bridge.watchedIssueText == "60371"
    assert bridge.watchedIssueError.endswith("abc, 999999")
    bridge.close()


def test_watched_only_separators_clears_saved_ids(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    saved = []
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_watched_issue_ids", lambda _account, ids: saved.append(ids))
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_quick_view", lambda *_args, **_kwargs: None)
    bridge.saveWatchedIssueIds(" ,，；; \n")
    assert saved == [[]]
    assert bridge.watchedIssueText == "" and bridge.issueRows == []
    bridge.close()


class FakeAuth(QObject):
    authChanged = Signal()
    username = "alice"
    def transientCredential(self): return ("alice", "ldap-secret")


class MutableAuth(QObject):
    authChanged = Signal()
    def __init__(self, username="alice", password="alice-secret"):
        super().__init__(); self.username = username; self.password = password
    def transientCredential(self): return self.username, self.password


class FakeService:
    def __init__(self, result): self.result = result; self.credential = None; self.closed = False
    async def login(self, credential): self.credential = credential; return self.result
    async def close(self): self.closed = True


class LoopRecordingService(FakeService):
    def __init__(self): super().__init__(AuthResult(AuthState.VERIFICATION_REQUIRED)); self.loops = []; self.closed = False
    async def login(self, credential): self.loops.append(asyncio.get_running_loop()); return await super().login(credential)
    async def submit_verification(self, _code): self.loops.append(asyncio.get_running_loop()); return AuthResult(AuthState.AUTHENTICATED)
    async def close(self): self.loops.append(asyncio.get_running_loop()); self.closed = True


def wait_for(predicate):
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert predicate()


def test_bridge_uses_transient_ldap_and_routes_only_explicit_prompt():
    service = FakeService(AuthResult(AuthState.CREDENTIALS_REQUIRED))
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service)
    credentials = []; verification = []
    bridge.credentialsRequired.connect(lambda: credentials.append(1))
    bridge.verificationRequired.connect(lambda: verification.append(1))
    bridge.startLogin()
    wait_for(lambda: bool(credentials))
    assert service.credential.password == "ldap-secret"
    assert credentials == [1] and verification == []
    bridge.close()


def test_smarthome_catalog_contains_redmine():
    personnel = {"employees": [{"account": "alice", "assignments": [{"product_line_id": "SmartHome"}]}], "product_lines": [{"id": "SmartHome", "active": True}]}
    smart_home = next(group for group in build_tool_groups(personnel, "alice") if group["id"] == "SmartHome")
    assert [tool["id"] for tool in smart_home["tools"]] == ["redmine"]


def test_all_operations_and_shutdown_use_one_owned_loop():
    service = LoopRecordingService(); bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service)
    verification = []; bridge.verificationRequired.connect(lambda: verification.append(1))
    bridge.startLogin(); wait_for(lambda: bool(verification))
    bridge.submitVerification("123456"); wait_for(lambda: bridge.state == "authenticated")
    bridge.close()
    assert service.closed and len({id(loop) for loop in service.loops}) == 1


def test_cancel_invalidates_late_completion_and_prompts():
    class SlowService(FakeService):
        async def login(self, credential):
            self.credential = credential
            await asyncio.sleep(10)
            return AuthResult(AuthState.CREDENTIALS_REQUIRED)
    service = SlowService(AuthResult(AuthState.CREDENTIALS_REQUIRED)); bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service)
    prompts = []; bridge.credentialsRequired.connect(lambda: prompts.append(1))
    bridge.startLogin(); bridge.cancelLogin(); time.sleep(0.05); (QCoreApplication.instance() or QCoreApplication([])).processEvents()
    assert bridge.state == "idle" and prompts == []
    bridge.close()


def test_qml_clears_transient_password_and_verification_inputs():
    source = Path("ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")
    login = Path("ui/example/imports/example/qml/component/redmine/RedmineLoginView.qml").read_text(encoding="utf-8")
    assert 'if (state !== "credentials_required") passwordInput.text = ""' in login
    assert 'if (state !== "verification_required") verificationInput.text = ""' in login
    assert 'passwordInput.text = ""' in login
    assert 'verificationInput.text = ""' in login
    assert "RedmineBridge.password" not in source and "RedmineBridge.code" not in source


def test_worker_does_not_close_loop_while_thread_is_still_alive():
    class ThreadStillRunning:
        def join(self, timeout): self.timeout = timeout
        def is_alive(self): return True
    class RecordingLoop:
        def __init__(self): self.closed = False
        def call_soon_threadsafe(self, callback): self.callback = callback
        def stop(self): pass
        def is_closed(self): return False
        def close(self): self.closed = True
    worker = _AsyncLoopWorker.__new__(_AsyncLoopWorker)
    worker.loop = RecordingLoop(); worker._thread = ThreadStillRunning()
    assert worker.stop(timeout=0.01) is False
    assert worker.loop.closed is False


def test_incorrect_verification_reason_is_localized_by_bridge():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._generation = 7
    bridge._apply(7, AuthResult(AuthState.VERIFICATION_REQUIRED, reason="incorrect_verification_code"))
    assert bridge.statusText == "The verification code was rejected. Enter the latest code from your phone."
    bridge.close()


def test_dynamic_external_status_text_remains_raw():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._generation = 3
    bridge._apply(3, AuthResult(AuthState.FAILED, message="External Redmine maintenance notice"))
    assert bridge.statusText == "External Redmine maintenance notice"
    bridge.close()


def test_bridge_marks_cloned_redmine_rows_and_detail_with_jira_link():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    _set_bridge_records(
        bridge,
        [
            _issue_record(
                "61043",
                title="panel",
                web_url="https://support/issues/61043",
            )
        ],
        selected_id="61043",
    )

    bridge._issue_controller.record_clone_results(
        {"61043": ExistingIssue(key="SH-26384", web_url="https://jira/browse/SH-26384")}
    )

    assert bridge.issueRows[0]["clonedIssueKey"] == "SH-26384"
    assert bridge.selectedIssue["clonedIssueUrl"] == "https://jira/browse/SH-26384"
    bridge.close()


def test_bridge_remembers_opened_web_urls_to_avoid_duplicate_windows(monkeypatch):
    opened = []
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.QDesktopServices.openUrl", lambda url: opened.append(url.toString()))
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))

    bridge.openWebUrl("https://support/issues/61043")
    bridge.openWebUrl("https://support/issues/61043")

    assert bridge._opened_urls == {"https://support/issues/61043"}
    assert opened == ["https://support/issues/61043"]
    bridge.close()


def test_clone_batch_selection_rejects_cloned_rows_and_preserves_source_order():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    _set_bridge_records(
        bridge,
        [
            _issue_record("3"),
            _issue_record("1", clone_state="cloned", clone_key="SH-1"),
            _issue_record("2"),
        ],
    )

    bridge.beginCloneSelection()
    bridge.toggleCloneSelection("2", True)
    bridge.toggleCloneSelection("1", True)
    bridge.toggleCloneSelection("3", True)

    assert bridge.cloneSelectionMode is True
    assert bridge.cloneBatchState == "selecting"
    assert bridge.cloneSelectedIds == ["3", "2"]
    bridge.cancelCloneSelection()
    assert bridge.cloneBatchState == "idle" and bridge.cloneSelectedIds == []
    bridge.close()


CLONE_SCHEMA = (
    CreateFieldSchema("project", "Project", True, CreateFieldControl.SINGLE, value="SH"),
    CreateFieldSchema("issuetype", "Issue Type", True, CreateFieldControl.SINGLE, value="Bug"),
    CreateFieldSchema("summary", "Summary", True, CreateFieldControl.TEXT),
    CreateFieldSchema("description", "Description", True, CreateFieldControl.MULTILINE),
    CreateFieldSchema("reporter", "Reporter", True, CreateFieldControl.USER),
    CreateFieldSchema("customfield_10409", "FAE Coworker", True, CreateFieldControl.USER),
    CreateFieldSchema("labels", "Labels", False, CreateFieldControl.MULTI),
    CreateFieldSchema("customfield_attachment_real", "Attachment links", False, CreateFieldControl.TEXT),
)


class CloneJiraClient:
    def __init__(self, account="defeng.zhai"):
        self.account = account
        self.search_calls = []
        self.current_user_calls = 0

    def current_user(self):
        self.current_user_calls += 1
        return {"account": self.account, "display_name": "Current User", "avatar_url": "avatar"}

    def search_users(self, query, *, project_key="SH"):
        self.search_calls.append((query, project_key))
        return [{"account": self.account, "display_name": "Current User", "avatar_url": "avatar"}]


class CloneSchemaService:
    def __init__(self, schema=CLONE_SCHEMA):
        self.schema_value = schema
        self.calls = []

    def schema(self, project_key, issue_type):
        self.calls.append((project_key, issue_type))
        return self.schema_value


class CloneCreateService:
    def __init__(self):
        self.rechecks = []
        self.creates = []
        self.requests = []
        self.synced = []
        self.duplicates = {}
        self.fail_once = set()

    def check_issue_by_external_url(self, *, project_key, external_url):
        self.rechecks.append((project_key, external_url))
        return self.duplicates.get(external_url)

    def create_issue(self, request):
        self.creates.append(request.source_id)
        self.requests.append(request)
        if request.source_id in self.fail_once:
            self.fail_once.remove(request.source_id)
            raise RuntimeError(f"failed {request.source_id}")
        return CreateIssueResult(
            created=True,
            issue_key=f"SH-{request.source_id}",
            issue_url=f"https://jira/browse/SH-{request.source_id}",
        )

    def attachment_metadata(self):
        return JiraAttachmentMetadata(
            available=True, enabled=True, upload_limit=1024
        )

    def sync_attachments(
        self,
        issue_key,
        attachments,
        *,
        metadata,
        prior_results=(),
        cancellation=None,
    ):
        self.synced.extend(
            (
                issue_key,
                item.filename,
                item.path.read_bytes(),
                item.size,
            )
            for item in attachments
        )
        results = tuple(prior_results) + tuple(
            AttachmentTransferResult(
                source_id=item.source_id,
                filename=item.filename,
                size=item.size,
                state="uploaded",
            )
            for item in attachments
        )
        return AttachmentSyncResult(
            state="complete" if results else "none",
            results=results,
        )


class RecordingDraftService:
    def __init__(self):
        self.calls = []
        self.owner = RedmineCloneDraftService()

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return self.owner.build(**kwargs)


def clone_bridge(*, issue_ids=("1",), schema=CLONE_SCHEMA, persist=False):
    auth = MutableAuth("defeng.zhai")
    bridge = RedmineBridge(auth, service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    items = tuple(
        RedmineIssueListItem(id=issue_id, url=f"https://redmine/issues/{issue_id}", tracker="Bug", subject=f"Issue {issue_id}")
        for issue_id in issue_ids
    )
    project = RedmineProject(name="SmartHome", identifier="sh", url="project", project_id="PID", issues=items)
    details = tuple(
        RedmineIssueDetail(id=item.id, url=item.url, project_identifier="sh", tracker="Bug", subject=item.subject, description="desc", list_item=item)
        for item in items
    )
    context = RedmineContext(account=auth.username, projects=(project,), issues=details)
    _set_bridge_projection(
        bridge,
        context,
        view(
            context,
            all_projects="All projects",
            selected_detail=details[0] if details else None,
        )
    )
    bridge._jira_client = CloneJiraClient(auth.username)
    bridge._jira_schema_service = CloneSchemaService(schema)
    bridge._jira_create_service = CloneCreateService()
    bridge._batch_controller._draft_service = RecordingDraftService()
    bridge.beginCloneSelection()
    for issue_id in issue_ids:
        bridge.toggleCloneSelection(issue_id, True)
    return bridge


def test_prepare_clone_drafts_has_no_create_calls_and_uses_identity_department_and_plain_order():
    bridge = clone_bridge(issue_ids=("2", "1"))
    states = []
    bridge.changed.connect(lambda: states.append(bridge.cloneBatchState))

    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")

    assert "loading" in states and states[-1] == "editing"
    assert bridge._jira_create_service.creates == []
    assert [item["issueId"] for item in bridge.cloneDrafts] == ["2", "1"]
    assert [item["fieldId"] for item in bridge.cloneDrafts[0]["fields"]] == [
        item.field_id for item in CLONE_SCHEMA
        if item.required or item.field_id == "priority" or item.name.casefold() == "attachment links"
    ]
    assert bridge._batch_controller._draft_service.calls[0]["account"] == "defeng.zhai"
    assert bridge._batch_controller._draft_service.calls[0]["department"] == "FAE-SW"
    assert bridge.cloneDrafts[0]["fields"][4]["value"] == "defeng.zhai"
    assert bridge._jira_client.current_user_calls == 1
    assert bridge._jira_client.search_calls == []
    bridge.close()


def test_prepare_clone_uses_deterministic_jira_template_without_ai():
    bridge = clone_bridge()
    detail = bridge._issue_controller._source_context.issues[0]
    enriched_detail = RedmineIssueDetail(
        id=detail.id,
        url=detail.url,
        project_identifier=detail.project_identifier,
        tracker=detail.tracker,
        subject=detail.subject,
        description=detail.description,
        attributes={"Board": "A", "Version": "1.0"},
        comments=(RedmineJournal(id="j1", header="Updated by Alice", note="复现评论", details=("Status changed", "补充信息")),),
        list_item=detail.list_item,
    )
    bridge._issue_controller._source_context = RedmineContext(
        account=bridge._issue_controller._source_context.account,
        projects=bridge._issue_controller._source_context.projects,
        issues=(enriched_detail,),
    )
    assert not hasattr(bridge, "_description_service")
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")
    description = next(
        item
        for item in bridge.cloneDrafts[0]["fields"]
        if item["fieldId"] == "description"
    )["value"]
    assert description.startswith("[Steps to reproduce]:")
    assert "[Actual results]:" in description
    assert "[Expected results]:" in description
    assert "[Reproducibility rate]:" in description
    assert "[Comparision]:" in description
    assert "[Notes]:" in description
    assert "HW info:" in description
    assert "SW info:" in description
    assert "[Notes]:\ndesc\nHW info:" in description
    for excluded in (
        "Source:",
        "Source ID:",
        "Source URL:",
        "Title:",
        "Board:",
        "Version:",
        "Updated by Alice",
        "复现评论",
        "Status changed",
        "补充信息",
    ):
        assert excluded not in description
    bridge.close()


def test_authenticated_redmine_attachment_download_returns_hidden_jira_data():
    class Response:
        ok = True
        status = 200

        async def body(self):
            return b"downloaded"

    class Request:
        def __init__(self):
            self.urls = []

        async def get(self, url):
            self.urls.append(url)
            return Response()

    class Page:
        request = Request()

    attachment = RedmineAttachment(
        id="1",
        filename="trace.log",
        download_url="https://redmine/attachments/download/1/trace.log",
    )
    result = asyncio.run(
        _download_redmine_attachments(
            Page(),
            (attachment,),
            JiraAttachmentMetadata(
                available=False, enabled=None, upload_limit=None
            ),
        )
    )
    assert Page.request.urls == [attachment.download_url]
    assert [
        (item.filename, item.path.read_bytes(), item.size)
        for item in result.attachments
    ] == [
        ("trace.log", b"downloaded", 10)
    ]
    directory = result.directory
    result.close()
    assert not directory.exists()


def test_submit_downloads_attachment_through_authenticated_page_and_hands_off_file():
    class Response:
        ok = True
        status = 200

        async def body(self):
            return b"jira attachment"

    class Request:
        async def get(self, url):
            assert url.endswith("/trace.log")
            return Response()

    class Page:
        request = Request()

    bridge = clone_bridge()
    bridge._service = type("Service", (), {"page": Page()})()
    detail = bridge._issue_controller._source_context.issues[0]
    bridge._issue_controller._source_context = RedmineContext(
        account=bridge._issue_controller._source_context.account,
        projects=bridge._issue_controller._source_context.projects,
        issues=(
            RedmineIssueDetail(
                **{
                    **detail.__dict__,
                    "attachments": (
                        RedmineAttachment(
                            id="1",
                            filename="trace.log",
                            download_url="https://redmine/download/trace.log",
                        ),
                    ),
                }
            ),
        ),
    )
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")
    bridge.submitCloneBatch()
    wait_for(lambda: bridge.cloneBatchState == "completed")

    assert bridge._jira_create_service.requests[0].attachments == ()
    assert bridge._jira_create_service.synced == [
        ("SH-1", "trace.log", b"jira attachment", 15)
    ]
    assert "attachments" not in bridge.cloneDrafts[0]
    bridge.close()


def test_bridge_close_cancels_active_upload_before_temp_cleanup(tmp_path):
    entered = Event()
    released = Event()
    cleaned = Event()
    timed_out = Event()

    class BlockingCreateService(CloneCreateService):
        def sync_attachments(
            self,
            issue_key,
            attachments,
            *,
            metadata,
            prior_results=(),
            cancellation=None,
        ):
            entered.set()
            deadline = time.monotonic() + 2
            while cancellation is None or not cancellation.cancelled:
                if time.monotonic() >= deadline:
                    timed_out.set()
                    break
                time.sleep(0.01)
            released.set()
            return AttachmentSyncResult(
                state="partial_failed",
                results=tuple(prior_results),
            )

    class Batch:
        def __init__(self):
            path = tmp_path / "active-upload.log"
            path.write_bytes(b"x" * 128)
            self.attachments = (
                CreateIssueAttachment(
                    source_id="1",
                    filename="active-upload.log",
                    path=path,
                ),
            )
            self.results = ()
            self._path = path

        def close(self):
            self._path.unlink(missing_ok=True)
            cleaned.set()

    async def download(
        _attachments, _metadata, *, duplicate_filenames
    ):
        assert duplicate_filenames == set()
        return Batch()

    bridge = clone_bridge()
    bridge._jira_create_service = BlockingCreateService()
    bridge._batch_controller._download_attachments = download
    detail = bridge._issue_controller._source_context.issues[0]
    bridge._issue_controller._source_context = RedmineContext(
        account=bridge._issue_controller._source_context.account,
        projects=bridge._issue_controller._source_context.projects,
        issues=(
            RedmineIssueDetail(
                **{
                    **detail.__dict__,
                    "attachments": (
                        RedmineAttachment(
                            id="1",
                            filename="active-upload.log",
                            download_url="https://redmine/active-upload.log",
                        ),
                    ),
                }
            ),
        ),
    )
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")
    bridge.submitCloneBatch()
    assert entered.wait(timeout=1)

    started = time.monotonic()
    bridge.close()
    elapsed = time.monotonic() - started

    assert elapsed < 1
    assert released.is_set()
    assert cleaned.is_set()
    assert not timed_out.is_set()
    assert not (tmp_path / "active-upload.log").exists()


def test_bridge_close_timeout_defers_cleanup_until_upload_thread_finishes(
    tmp_path, monkeypatch
):
    entered = Event()
    release = Event()
    cleaned = Event()
    early_cleanup = Event()
    logs = []
    monkeypatch.setattr(
        "tool.SmartHome.redmine.clone_controller.smart_log",
        lambda message, **kwargs: logs.append((message, kwargs)),
    )

    class IgnoringCancelCreateService(CloneCreateService):
        def sync_attachments(
            self,
            issue_key,
            attachments,
            *,
            metadata,
            prior_results=(),
            cancellation=None,
        ):
            entered.set()
            release.wait(timeout=2)
            return AttachmentSyncResult(
                state="complete",
                results=tuple(prior_results),
            )

    class Batch:
        def __init__(self):
            self._path = tmp_path / "deferred-upload.log"
            self._path.write_bytes(b"x" * 128)
            self.attachments = (
                CreateIssueAttachment(
                    source_id="1",
                    filename="deferred-upload.log",
                    path=self._path,
                ),
            )
            self.results = ()

        def close(self):
            if not release.is_set():
                early_cleanup.set()
            self._path.unlink(missing_ok=True)
            cleaned.set()

    async def download(
        _attachments, _metadata, *, duplicate_filenames
    ):
        assert duplicate_filenames == set()
        return Batch()

    bridge = clone_bridge()
    bridge._jira_create_service = IgnoringCancelCreateService()
    bridge._batch_controller._download_attachments = download
    bridge._batch_controller._attachment_cancel_wait = 0.02
    detail = bridge._issue_controller._source_context.issues[0]
    bridge._issue_controller._source_context = RedmineContext(
        account=bridge._issue_controller._source_context.account,
        projects=bridge._issue_controller._source_context.projects,
        issues=(
            RedmineIssueDetail(
                **{
                    **detail.__dict__,
                    "attachments": (
                        RedmineAttachment(
                            id="1",
                            filename="deferred-upload.log",
                            download_url="https://redmine/deferred-upload.log",
                        ),
                    ),
                }
            ),
        ),
    )
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")
    bridge.submitCloneBatch()
    assert entered.wait(timeout=1)

    started = time.monotonic()
    bridge.close()
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert not cleaned.is_set()
    assert not early_cleanup.is_set()
    assert (tmp_path / "deferred-upload.log").exists()
    assert any("cancellation reached timeout" in item[0] for item in logs)

    release.set()
    assert cleaned.wait(timeout=1)
    assert not early_cleanup.is_set()
    assert not (tmp_path / "deferred-upload.log").exists()


def test_clone_editor_exposes_required_fields_and_priority_but_hides_optional_extras():
    bridge = clone_bridge()
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")

    field_ids = [item["fieldId"] for item in bridge.cloneDrafts[0]["fields"]]
    assert "labels" not in field_ids
    assert "customfield_attachment_real" in field_ids
    assert field_ids == [
        item.field_id for item in CLONE_SCHEMA
        if item.required or item.field_id == "priority" or item.name.casefold() == "attachment links"
    ]
    bridge.close()


def test_prepare_clone_fails_when_attachment_links_schema_field_is_missing():
    schema = tuple(item for item in CLONE_SCHEMA if item.name.casefold() != "attachment links")
    bridge = clone_bridge(schema=schema)
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "prepare_failed")
    assert "Attachment links" in bridge.cloneBatchError
    assert bridge.cloneDrafts == []
    bridge.close()


def test_prepare_failure_keeps_zero_drafts_out_of_editing_and_can_retry():
    bridge = clone_bridge()
    original = bridge._jira_client.current_user
    bridge._jira_client.current_user = lambda: (_ for _ in ()).throw(RuntimeError("Jira identity unavailable"))

    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "prepare_failed")

    assert bridge.cloneDrafts == []
    assert bridge.cloneBatchError == "Jira identity unavailable"
    bridge.submitCloneBatch()
    assert bridge._jira_create_service.creates == []

    bridge._jira_client.current_user = original
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")
    assert len(bridge.cloneDrafts) == 1
    bridge.close()


def test_required_draft_error_blocks_every_create_and_user_update_revalidates():
    required = CLONE_SCHEMA + (
        CreateFieldSchema("customfield_required", "Required", True, CreateFieldControl.TEXT),
    )
    bridge = clone_bridge(schema=required)
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")

    bridge.submitCloneBatch()

    assert bridge.cloneBatchState == "editing"
    assert bridge.firstInvalidIssueId == "1"
    assert bridge.firstInvalidFieldId == "customfield_required"
    assert bridge._jira_create_service.creates == []
    bridge.updateCloneDraft("1", "customfield_required", "reviewed")
    assert bridge.firstInvalidIssueId == ""
    assert next(item for item in bridge.cloneDrafts[0]["fields"] if item["fieldId"] == "customfield_required")["error"] == ""
    bridge.close()


def test_submit_continues_updates_clone_owner_and_retry_sends_failed_only():
    bridge = clone_bridge(issue_ids=("1", "2", "3"))
    creator = bridge._jira_create_service
    creator.duplicates["https://redmine/issues/2"] = ExistingIssue(key="SH-existing", web_url="existing-url")
    creator.fail_once.add("3")
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")

    bridge.submitCloneBatch(); wait_for(lambda: bridge.cloneBatchState == "partial_failed")

    assert creator.creates == ["1", "3"]
    assert [item["state"] for item in bridge.cloneDrafts] == ["created", "duplicate", "failed"]
    assert [row["cloneStatus"] for row in bridge.issueRows] == ["cloned", "cloned", "not_cloned"]
    bridge.retryFailedClones(); wait_for(lambda: bridge.cloneBatchState == "completed")
    assert creator.creates == ["1", "3", "3"]
    assert all(row["cloneStatus"] == "cloned" for row in bridge.issueRows)
    bridge.close()


def test_attachment_link_edit_changes_payload_but_duplicate_identity_stays_fixed_source_url():
    bridge = clone_bridge()
    creator = bridge._jira_create_service
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")
    bridge.updateCloneDraft("1", "customfield_attachment_real", "https://edited.example/link")
    bridge.submitCloneBatch(); wait_for(lambda: bridge.cloneBatchState == "completed")
    assert creator.rechecks == [("SH", "https://redmine/issues/1")]
    assert creator.requests[0].source_url == "https://redmine/issues/1"
    assert creator.requests[0].extra_fields["customfield_attachment_real"] == "https://edited.example/link"
    bridge.close()


def test_clone_account_and_user_search_generations_reject_late_results():
    bridge = clone_bridge()
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")
    old_clone_generation = bridge._batch_controller.generation
    old_account_generation = bridge._generation
    bridge.searchCloneUsers("1", "reporter", "fred")
    current_generation = bridge._batch_controller.generation
    bridge._apply_clone_result(old_clone_generation, old_account_generation, "users", ("1", "reporter", [{"account": "old", "display_name": "Old"}]))
    assert all(item.get("value") != "old" for item in bridge.cloneDrafts[0]["fields"][4]["options"])
    bridge._apply_clone_result(current_generation, old_account_generation, "users", ("1", "reporter", [{"account": "fred", "display_name": "Fred", "avatar_url": "a"}]))
    assert bridge.cloneDrafts[0]["fields"][4]["options"][0]["value"] == "fred"

    bridge._auth.username = "other"; bridge._auth.authChanged.emit()
    assert bridge.cloneBatchState == "idle" and bridge.cloneDrafts == []
    bridge._apply_clone_result(current_generation, old_account_generation, "prepare", [])
    assert bridge.cloneBatchState == "idle"
    bridge.close()


def test_clone_batch_close_returns_loading_preview_to_selection_but_not_submission():
    class Pending:
        def __init__(self): self.cancelled = False
        def cancel(self): self.cancelled = True

    bridge = clone_bridge()
    pending = Pending()
    bridge._batch_future = pending
    bridge._batch_controller._state = "loading"
    bridge._batch_controller._selected_ids = ["1"]
    bridge.closeCloneBatch()
    assert pending.cancelled and bridge.cloneBatchState == "selecting"
    assert bridge.cloneSelectedIds == ["1"]

    bridge._batch_controller._state = "submitting"
    bridge.closeCloneBatch()
    assert bridge.cloneBatchState == "submitting"
    bridge._batch_controller._state = "idle"
    bridge.close()


def test_failed_auth_result_logs_state_reason_without_credentials(monkeypatch):
    logs = []
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.smart_log",
        lambda message, *args, **kwargs: logs.append((message, kwargs)),
    )
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._generation = 4

    bridge._apply(4, AuthResult(AuthState.FAILED, reason="login_failed", username="alice"))

    message, kwargs = logs[-1]
    assert message == "[REDMINE_AUTH] login failure"
    assert kwargs["extra"] == {"state": "failed", "reason": "login_failed", "error_type": ""}
    assert "ldap-secret" not in repr(logs)
    bridge.close()


def test_auth_operation_exception_keeps_reason_and_error_type(monkeypatch):
    class RaisingService(FakeService):
        async def login(self, credential):
            raise PermissionError("browser state is unavailable")

    logs = []
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.smart_log",
        lambda message, *args, **kwargs: logs.append((message, kwargs)),
    )
    bridge = RedmineBridge(
        FakeAuth(), service_factory=lambda _account: RaisingService(AuthResult(AuthState.IDLE))
    )

    bridge.startLogin()
    wait_for(lambda: bridge.state == "failed")

    auth_log = next(item for item in logs if item[0] == "[REDMINE_AUTH] login failure")
    assert auth_log[1]["extra"] == {
        "state": "failed",
        "reason": "operation_exception",
        "error_type": "PermissionError",
    }
    assert bridge.statusText == "Redmine sign-in failed."
    assert "browser state is unavailable" not in repr(logs)
    assert "ldap-secret" not in repr(logs)
    bridge.close()


def test_account_change_immediately_invalidates_old_redmine_state_and_late_results():
    auth = MutableAuth()
    bridge = RedmineBridge(auth, service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._generation = 8; bridge._data_generation = 5
    bridge._state = AuthState.AUTHENTICATED; bridge._account = "alice"
    old_service = FakeService(AuthResult(AuthState.AUTHENTICATED, username="alice"))
    bridge._service = old_service
    _set_bridge_records(bridge, [_issue_record("1")], selected_id="1")
    bridge._issue_controller._project_filter_labels = ("All projects", "Alice project")
    bridge._clone_checker = object()

    auth.username = "bob"; auth.password = "bob-secret"; auth.authChanged.emit()

    assert bridge.state == "idle" and bridge.account == ""
    assert bridge.projectFilterLabels == ["All projects"]
    assert bridge.issueRows == [] and bridge._clone_checker is None
    wait_for(lambda: old_service.closed)
    bridge._apply(8, AuthResult(AuthState.AUTHENTICATED, username="alice"))
    assert bridge.state == "idle"
    bridge.close()


def test_login_after_account_change_uses_current_ldap_credential():
    auth = MutableAuth()
    accounts = []; services = []
    def factory(account):
        service = FakeService(AuthResult(AuthState.CREDENTIALS_REQUIRED, username=account))
        accounts.append(account); services.append(service); return service
    bridge = RedmineBridge(auth, service_factory=factory)
    auth.username = "bob"; auth.password = "bob-secret"; auth.authChanged.emit()

    bridge.startLogin()
    wait_for(lambda: bridge.state == "credentials_required")

    assert accounts == ["bob"]
    assert services[0].credential.username == "bob" and services[0].credential.password == "bob-secret"
    bridge.close()


def test_authenticated_default_starts_my_page_and_projects_not_search(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    calls = []
    monkeypatch.setattr(bridge, "activateQuickView", lambda quick_view_id: calls.append(quick_view_id))
    monkeypatch.setattr(bridge, "refreshProjects", lambda: calls.append("projects"))
    monkeypatch.setattr(bridge, "refreshData", lambda: calls.append("search"))
    bridge._generation = 3
    bridge._apply(3, AuthResult(AuthState.AUTHENTICATED, username="alice"))
    assert calls == ["my_assigned", "projects"]
    bridge.close()


def test_my_assigned_uses_unified_issue_operation_and_is_not_search_cancellable(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    launched = []
    monkeypatch.setattr(bridge, "_load_quick_view_cache", lambda quick_view_id: launched.append(("cache", quick_view_id)))
    def launch(operation, *, status, kind):
        assert callable(operation)
        launched.append((kind, status))
    monkeypatch.setattr(bridge, "_launch_data_load", launch)
    bridge.activateQuickView("my_assigned")
    assert launched == [("cache", "my_assigned"), ("my_assigned", "Loading issues assigned to me...")]
    assert bridge.activeQuickViewId == "my_assigned"
    assert not hasattr(bridge, "_my_page_future")
    bridge._data_loading = True; bridge._data_operation_kind = "my_assigned"; bridge._data_future = object()
    assert bridge.searchLoading is False and bridge.searchCanCancel is False
    bridge._data_future = None
    bridge.close()


def test_my_assigned_projects_reuse_synced_project_id_and_leave_unknown_empty():
    known = RedmineIssueListItem(id="1", url="u1", subject="known")
    unknown = RedmineIssueListItem(id="2", url="u2", subject="unknown")
    rows = [
        {"project_identifier": "an40bf", "project_name": "AN40BF", "project_url": "p1", "issue": known},
        {"project_identifier": "new-project", "project_name": "New", "project_url": "p2", "issue": unknown},
    ]

    controller = RedmineIssueController(
        account="alice",
        all_projects="All projects",
    )
    projects = controller.assigned_context(
        rows,
        [{"id": "an40bf", "label": "AN40BF", "projectId": "AN40BF-A311D2"}],
    ).projects

    assert projects[0].identifier == "an40bf"
    assert projects[0].project_id == "AN40BF-A311D2"
    assert projects[1].identifier == "new-project"
    assert projects[1].project_id == ""
    legacy = controller.assigned_context(
        rows[:1], [{"id": "an40bf", "label": "AN40BF"}]
    ).projects
    assert legacy[0].project_id == ""

    draft = RedmineCloneDraftService().build(
        issue=RedmineIssueDetail(id="1", url="u1", project_identifier="an40bf", subject="known", list_item=known),
        project=projects[0],
        schema=(CreateFieldSchema(
            "customfield_project", "Project ID", True, CreateFieldControl.MULTI,
            options=(CreateFieldOption("pid", "AN40BF-A311D2"),),
        ),),
        account="subing.xu",
        department="FAE-SW",
        prepared_description="prepared description",
    )
    assert draft.value("customfield_project") == ["pid"]


def test_project_refresh_cache_keeps_project_id_without_extra_collection(monkeypatch):
    project = RedmineProject(name="AN40BF", identifier="an40bf", url="p", project_id="AN40BF-A311D2")
    calls = []
    class Collector:
        def __init__(self, _page, **_kwargs): pass
        async def collect_projects(self): calls.append("projects"); return (project,)
    class Service(FakeService):
        page = object()
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: Service(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._account = "alice"
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.RedmineContextCollector", Collector)
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.load_project_options", lambda _account: [])
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_project_options", lambda _account, options: calls.append(list(options)))

    bridge.refreshProjects()
    wait_for(lambda: bridge.projectsReadyState)

    assert calls == ["projects", [{"id": "an40bf", "label": "AN40BF", "projectId": "AN40BF-A311D2"}]]
    bridge.close()


def test_late_project_metadata_reconciles_loaded_my_page_without_losing_state(monkeypatch):
    from tool.SmartHome.redmine.view_model import view
    item = RedmineIssueListItem(id="1", url="u", tracker="Bug", status="New", subject="known")
    detail = RedmineIssueDetail(id="1", url="u", project_identifier="an40bf", subject="known", description="body", list_item=item)
    context = RedmineContext(
        account="alice",
        projects=(RedmineProject(name="AN40BF", identifier="an40bf", url="p", project_id="", issues=(item,)),),
        issues=(detail,),
        raw={"issue_analysis": {"1": {"risk": "red", "age_text": "8 days"}}},
    )
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    bridge._issue_controller.activate_view("my_assigned")
    bridge._projects_generation = 4
    _set_bridge_projection(
        bridge,
        context,
        view(
            context,
            all_projects="All projects",
            filters={"status": "Open"},
            selected_detail=detail,
        )
    )
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_project_options", lambda *_args: None)

    bridge._apply_projects(4, [{"id": "an40bf", "label": "AN40BF", "projectId": "AN40BF-A311D2"}])

    reconciled = bridge._issue_controller._source_context
    project, found = reconciled.item_for_issue("1")
    assert found == item and project.project_id == "AN40BF-A311D2"
    assert reconciled.issues == (detail,)
    assert reconciled.raw == context.raw
    assert bridge.filters["status"] == "Open"
    assert bridge.selectedIssue["id"] == "1"
    draft = RedmineCloneDraftService().build(
        issue=detail,
        project=project,
        schema=(CreateFieldSchema("pid", "Project ID", True, CreateFieldControl.MULTI, options=(CreateFieldOption("mapped", "AN40BF-A311D2"),)),),
        account="alice",
        department="FAE-SW",
        prepared_description="prepared description",
    )
    assert draft.value("pid") == ["mapped"]
    bridge.close()


def test_project_refresh_never_replaces_cached_rows_or_detail(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    bridge._issue_controller.activate_view("my_assigned")
    bridge._projects_generation = 3
    _set_bridge_records(
        bridge,
        [_issue_record("cached", title="Cached", description="body")],
        selected_id="cached",
    )
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_project_options", lambda *_args: None)

    bridge._apply_projects(3, [{"id": "p", "label": "P", "projectId": "P1"}])

    assert [(row["id"], row["title"]) for row in bridge.issueRows] == [("cached", "Cached")]
    assert bridge.selectedIssue["description"] == "body"
    bridge.close()


def test_cancel_clone_preview_preserves_selection_and_can_prepare_again():
    bridge = clone_bridge()
    bridge.beginCloneSelection()
    bridge.toggleCloneSelection("1", True)
    selected = bridge.cloneSelectedIds
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")

    bridge.closeCloneBatch()

    assert bridge.cloneBatchState == "selecting"
    assert bridge.cloneSelectedIds == selected
    assert bridge.cloneDrafts == []
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")
    assert bridge.cloneSelectedIds == selected
    bridge.close()


def test_project_metadata_first_is_used_when_my_page_rows_arrive(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_project_options", lambda *_args: None)
    bridge._projects_generation = 2
    bridge._apply_projects(2, [{"id": "an40bf", "label": "AN40BF", "projectId": "AN40BF-A311D2"}])
    item = RedmineIssueListItem(id="1", url="u", subject="known")

    projects = bridge._issue_controller.assigned_context(
        [{"project_identifier": "an40bf", "project_name": "AN40BF", "project_url": "p", "issue": item}],
        bridge._project_options,
    ).projects

    assert projects[0].project_id == "AN40BF-A311D2"
    bridge.close()


def test_explicit_search_clears_active_quick_view(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._projects_ready = True
    bridge._issue_controller.activate_view("my_assigned")
    monkeypatch.setattr(bridge, "_launch_data_load", lambda operation, **kwargs: None)
    bridge.applyFilters({"status": "Open"})
    assert bridge.activeQuickViewId == ""
    bridge.close()


def test_clone_draft_projection_localizes_attachment_warning_in_bridge():
    bridge = clone_bridge()
    warning = {
        "sourceId": "a",
        "filename": "外部-trace.log",
        "size": 9,
        "state": "failed",
        "reasonCode": "jira_upload_failed",
        "reasonArgs": {"detail": "server 原文"},
        "retryable": True,
    }

    projected = bridge._localized_clone_drafts(
        ({"issueId": "1", "attachmentWarnings": [warning]},)
    )

    localized = projected[0]["attachmentWarnings"][0]
    assert localized["attachmentWarningText"] == (
        "Attachment upload failed for 外部-trace.log: server 原文"
    )
    assert localized["reasonCode"] == "jira_upload_failed"
    assert localized["filename"] == "外部-trace.log"
    bridge.close()


def test_search_operation_executes_canonical_plan_projection_to_completion(monkeypatch):
    from contextlib import asynccontextmanager

    item = RedmineIssueListItem(
        id="search",
        url="https://redmine/issues/search",
        tracker="Bug",
        status="New",
        subject="Search result",
    )
    context = RedmineContext(
        account="alice",
        projects=(
            RedmineProject(
                name="P",
                identifier="p",
                url="https://redmine/projects/p",
                project_id="P1",
                issues=(item,),
            ),
        ),
    )

    class Collector:
        def __init__(self, *_args, **_kwargs):
            pass

        async def collect_query(self, _query):
            return context

    @asynccontextmanager
    async def operation_page(_service):
        yield object()

    async def service_for(_account):
        return object()

    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._state = AuthState.AUTHENTICATED
    bridge._projects_ready = True
    captured = []
    logs = []
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.RedmineContextCollector", Collector
    )
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.smart_log",
        lambda message, *args, **kwargs: logs.append((message, kwargs)),
    )
    monkeypatch.setattr(bridge, "_service_for", service_for)
    monkeypatch.setattr(bridge, "_operation_page", operation_page)
    monkeypatch.setattr(
        bridge,
        "_enrich_issue_context",
        lambda *_args, **_kwargs: asyncio.sleep(
            0, result=(context, "p", None, {}, None)
        ),
    )
    monkeypatch.setattr(
        bridge,
        "_launch_data_load",
        lambda operation, **_kwargs: captured.append(operation),
    )

    bridge.refreshData()
    result = asyncio.run(captured[0]())

    assert result == (context, "p", None, {}, None)
    plan = next(kwargs["extra"] for message, kwargs in logs if message == "[REDMINE_LOAD] plan")
    assert plan["filtered_rows"] == 1
    bridge.close()


def test_search_waits_for_projects_and_cancel_invalidates_only_search():
    class Future:
        def __init__(self): self.cancelled = False
        def cancel(self): self.cancelled = True
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge.applyFilters({"project": "P"})
    assert bridge._pending_filters is None
    future = Future(); bridge._data_future = future; bridge._data_loading = True
    bridge._data_operation_kind = "search"
    bridge._projects_future = object()
    generation = bridge._data_generation
    bridge.cancelSearch()
    assert future.cancelled and bridge._data_generation == generation + 1
    assert bridge._projects_future is not None
    assert bridge.searchLoading is False
    bridge._projects_future = None
    bridge.close()


def test_bridge_formats_redmine_loading_progress():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._data_loading = True

    bridge._apply_data_progress(100, 138, "BDS")

    assert bridge.dataLoaded == 100
    assert bridge.dataTotal == 138
    assert bridge.dataStatusText == "Loading Redmine data... 100/138"
    bridge.close()


def test_bridge_clone_check_progress_extends_total_work(monkeypatch):
    class FakeCloneChecker:
        def check_many(self, rows, *, progress_callback=None, progress_base=0, progress_total=None):
            for index, _row in enumerate(rows, start=1):
                progress_callback(progress_base + index, progress_total, "Checking cloned Jira issues")
            return {}

    logs = []
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.smart_log", lambda message, *args, **kwargs: logs.append((message, kwargs)))
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)), clone_checker=FakeCloneChecker())
    bridge._data_loading = True

    bridge._check_clone_status([{"id": "1"}, {"id": "2"}], progress_base=101, progress_total=103)

    assert bridge.dataLoaded == 103
    assert bridge.dataTotal == 103
    assert bridge.dataStatusText == "Checking cloned Jira issues... 103/103"
    assert [message for message, _kwargs in logs] == ["[REDMINE_LOAD] clone progress", "[REDMINE_LOAD] clone progress", "[REDMINE_LOAD] clone finished"]
    bridge.close()


def test_bridge_discovery_is_indeterminate_then_plan_denominator_is_stable():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._data_loading = True
    bridge._apply_data_progress(0, 0, "discovery")
    assert bridge.dataTotal == 0
    assert bridge.dataStatusText == "Discovering Redmine projects and issues..."
    totals = []
    for loaded, phase in ((0, "analysis"), (3, "analysis"), (5, "clone"), (8, "clone")):
        bridge._apply_data_progress(loaded, 8, phase)
        totals.append(bridge.dataTotal)
    assert totals == [8, 8, 8, 8]
    bridge.close()


def test_detail_selection_during_search_is_deferred_without_replacing_search_lifecycle(monkeypatch):
    from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueListItem, RedmineProject
    from tool.SmartHome.redmine.view_model import view
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    item = RedmineIssueListItem(id="closed", url="u", tracker="Bug", status="Closed", subject="closed")
    context = RedmineContext(projects=(RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=(item,)),))
    _set_bridge_projection(
        bridge,
        context,
        view(context, all_projects="All projects")
    )
    bridge._data_loading = True
    bridge._data_operation_kind = "search"
    launched = []
    monkeypatch.setattr(bridge, "_launch_data_load", lambda *args, **kwargs: launched.append(kwargs))
    bridge.selectIssue("closed")
    assert launched == []
    assert bridge._pending_detail_issue_id == "closed"
    assert bridge.dataLoading is True
    bridge.close()


def test_existing_analysis_detail_keeps_full_panel_content_without_refetch(monkeypatch):
    from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineJournal, RedmineProject
    from tool.SmartHome.redmine.view_model import view
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    item = RedmineIssueListItem(id="open", url="u", tracker="Bug", status="New", subject="full")
    detail = RedmineIssueDetail(id="open", url="u", project_identifier="p", subject="full", description="full description", attributes={"Status": "New", "Priority": "High"}, comments=(RedmineJournal(id="1", author="Alice", note="comment"),), list_item=item)
    context = RedmineContext(projects=(RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=(item,)),), issues=(detail,))
    _set_bridge_projection(
        bridge,
        context,
        view(context, all_projects="All projects")
    )
    launched = []
    monkeypatch.setattr(bridge, "_launch_data_load", lambda *args, **kwargs: launched.append(kwargs))
    bridge.selectIssue("open")
    assert launched == []
    assert bridge.selectedIssue["description"] == "full description"
    assert bridge.selectedIssue["comments"][0]["body"] == "comment"
    bridge.close()


def test_search_completion_with_closed_filter_has_no_monitor_selection(monkeypatch):
    from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueListItem, RedmineProject
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._data_generation = 4
    bridge._data_loading = True
    bridge._data_operation_kind = "search"
    item = RedmineIssueListItem(id="closed", url="u", tracker="Bug", status="Closed", subject="closed")
    context = RedmineContext(projects=(RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=(item,)),))
    selected = []
    monkeypatch.setattr(bridge, "selectIssue", lambda issue_id: selected.append(issue_id))
    bridge._apply_data(4, (context, "p", None, {"status": "Closed"}, {}))
    assert selected == []
    assert bridge.issueRows == []
    assert bridge.dataLoading is False
    assert bridge._data_operation_kind == ""
    bridge.close()


def test_all_invalid_watched_result_without_cache_replaces_old_membership(monkeypatch):
    from tool.SmartHome.redmine import context_store

    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._account = "alice"
    bridge._watched_issue_text = "999999"
    bridge._issue_controller.activate_view("watched")
    _set_bridge_records(
        bridge,
        [_issue_record("old", title="Old watched issue")],
        selected_id="old",
    )
    bridge._data_generation = 3
    bridge._data_loading = True
    bridge._data_operation_kind = "watched"
    monkeypatch.setattr(context_store, "load_quick_view", lambda *_args: None)
    monkeypatch.setattr(
        context_store,
        "reconcile_issue_records",
        lambda _account, records, **_kwargs: list(records),
    )
    monkeypatch.setattr(
        context_store, "save_quick_view", lambda *_args, **_kwargs: None
    )

    bridge._apply_data(
        3,
        (
            RedmineContext(account="alice"),
            "",
            None,
            {},
            {},
            ("999999",),
            ("999999",),
            True,
        ),
    )

    assert bridge.issueRows == []
    assert bridge.selectedIssue == {}
    assert bridge.watchedIssueText == "999999"
    assert bridge.watchedIssueError == "No valid watched issue IDs were found: 999999"
    assert bridge.dataStatusText == "Redmine data loaded."
    bridge.close()


def test_apply_filters_requests_fresh_search_instead_of_finalizing_cached_view(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._projects_ready = True
    requested = []
    monkeypatch.setattr(bridge, "refreshData", lambda: requested.append(dict(bridge._pending_filters or {})))
    bridge.applyFilters({"project": "P", "status": "Open", "type": "Bug", "text": "needle"})
    assert requested == [{"project": "P", "status": "Open", "type": "Bug", "subject": "", "text": "needle"}]
    bridge.close()


def test_search_is_disabled_until_project_discovery_succeeds(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    requested = []
    monkeypatch.setattr(bridge, "refreshData", lambda: requested.append("search"))
    bridge.applyFilters({"text": "needle"})
    assert requested == []
    assert bridge._pending_filters is None
    bridge.close()


def test_cancel_search_invalidates_only_search_generation():
    class Pending:
        def __init__(self): self.cancelled = False
        def cancel(self): self.cancelled = True
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    pending = Pending()
    bridge._data_future = pending
    bridge._data_generation = 4
    bridge._projects_generation = 7
    bridge._data_loading = True
    bridge._data_operation_kind = "search"
    bridge.cancelSearch()
    assert pending.cancelled is True
    assert bridge._data_generation == 5
    assert bridge._projects_generation == 7
    assert bridge.dataLoading is False
    bridge.close()


def test_detail_loading_is_not_exposed_as_cancellable_search():
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._data_loading = True
    bridge._data_future = object()
    bridge._data_operation_kind = "detail"
    generation = bridge._data_generation
    assert bridge.searchLoading is False
    assert bridge.searchCanCancel is False
    bridge.cancelSearch()
    assert bridge._data_generation == generation
    bridge._data_future = None
    bridge.close()


def test_default_my_page_cache_loader_never_reads_search_cache(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._account = "alice"
    cached = {
        "issue_list": [_issue_record("mine")],
        "selected_issue_id": "mine",
        "filters": {},
    }
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.load_quick_view", lambda *args, **kwargs: cached)
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.load_view", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("search cache read")))
    bridge._load_quick_view_cache("my_assigned")
    assert [row["id"] for row in bridge.issueRows] == ["mine"]
    bridge.close()


def test_search_and_my_page_apply_identical_enriched_detail_overdue_and_clone(monkeypatch):
    from types import SimpleNamespace
    from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineProject
    item = RedmineIssueListItem(id="1", url="u", tracker="Bug", status="New", subject="issue")
    project = RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=(item,))
    detail = RedmineIssueDetail(id="1", url="u", project_identifier="p", subject="issue", description="body", list_item=item)
    context = RedmineContext(projects=(project,), issues=(detail,), raw={"issue_analysis": {"1": {"risk": "red", "age_text": "8 days"}}})
    clone = {"1": SimpleNamespace(key="SH-1", web_url="jira")}
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_view", lambda *args, **kwargs: None)
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_quick_view", lambda *args, **kwargs: None)
    search = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    search._data_generation = 1; search._data_loading = True; search._data_operation_kind = "search"
    search._apply_data(1, (context, "p", detail, {}, clone))
    mine = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    mine._data_generation = 1; mine._data_loading = True; mine._data_operation_kind = "my_assigned"
    mine._apply_data(1, (context, "p", detail, {}, clone))
    for bridge in (search, mine):
        assert bridge.selectedIssue["description"] == "body"
        assert bridge.issueRows[0]["updateRisk"] == "red"
        assert bridge.issueRows[0]["cloneStatus"] == "cloned"
        assert bridge.issueRows[0]["clonedIssueKey"] == "SH-1"
    search.close(); mine.close()


def test_fresh_view_preserves_cached_clone_when_checker_is_unavailable(monkeypatch):
    item = RedmineIssueListItem(
        id="1",
        url="https://redmine/issues/1",
        tracker="Bug",
        status="New",
        subject="Fresh title",
    )
    project = RedmineProject(
        name="P",
        identifier="p",
        url="https://redmine/projects/p",
        project_id="PID",
        issues=(item,),
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    _set_bridge_records(
        bridge,
        [
            _issue_record(
                "1",
                title="Cached title",
                clone_state="cloned",
                clone_key="SH-1",
                clone_url="https://jira/browse/SH-1",
            )
        ],
        selected_id="1",
    )
    bridge._data_generation = 1
    bridge._data_loading = True
    bridge._data_operation_kind = "search"
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.context_store.save_view",
        lambda *_args, **_kwargs: None,
    )

    bridge._apply_data(
        1,
        (RedmineContext(projects=(project,)), "p", None, {}, None),
    )

    assert bridge._issue_controller._store.get("1").title == "Fresh title"
    assert bridge._issue_controller._store.get("1").clone == {
        "state": "cloned",
        "issue_key": "SH-1",
        "issue_url": "https://jira/browse/SH-1",
        "checked": True,
    }
    bridge.close()


def test_fresh_quick_view_reconciles_global_canonical_record_before_apply(
    monkeypatch, tmp_path
):
    from support.jira_integration.core import IssueStore
    from tool.SmartHome.redmine import context_store

    monkeypatch.setattr(
        context_store,
        "cache_path",
        lambda _account: tmp_path / "alice.json",
    )
    cached_store = IssueStore(
        [
            _issue_record(
                "1",
                title="Cached title",
                description="Cached rich detail",
                clone_state="cloned",
                clone_key="SH-1",
                clone_url="https://jira/browse/SH-1",
            )
        ]
    )
    cached_store.select("1")
    context_store.save_view("alice", cached_store, filters={"text": "cached"})
    assert context_store.load_quick_view("alice", "my_assigned") is None

    item = RedmineIssueListItem(
        id="1",
        url="https://redmine/issues/1",
        tracker="Bug",
        status="New",
        subject="Fresh title",
    )
    project = RedmineProject(
        name="P",
        identifier="p",
        url="https://redmine/projects/p",
        project_id="PID",
        issues=(item,),
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._account = "alice"
    bridge._issue_controller.activate_view("my_assigned")
    assert bridge._issue_controller._store.issue_list == ()
    bridge._data_generation = 1
    bridge._data_loading = True
    bridge._data_operation_kind = "my_assigned"

    bridge._apply_data(
        1,
        (RedmineContext(projects=(project,)), "p", None, {}, None),
    )

    bridge_issue = bridge._issue_controller._store.get("1")
    quick_view = context_store.load_quick_view("alice", "my_assigned")
    cached_issue = quick_view["issue_list"][0]
    assert bridge_issue.to_dict() == cached_issue.to_dict()
    assert bridge_issue.title == "Fresh title"
    assert bridge_issue.detail_state == "loaded"
    assert bridge_issue.description == "Cached rich detail"
    assert bridge_issue.clone["state"] == "cloned"
    assert bridge_issue.clone["issue_key"] == "SH-1"
    assert [issue.id for issue in quick_view["issue_list"]] == ["1"]
    assert bridge._issue_controller._store.selected_id == quick_view["selected_issue_id"] == "1"
    bridge.close()


@pytest.mark.parametrize(
    ("fresh_ids", "expected_selected_id"),
    [
        (("1", "2"), "2"),
        (("1",), "1"),
    ],
)
def test_quick_view_refresh_preserves_cached_selection_only_while_still_present(
    monkeypatch, tmp_path, fresh_ids, expected_selected_id
):
    from support.jira_integration.core import IssueStore
    from tool.SmartHome.redmine import context_store

    monkeypatch.setattr(
        context_store,
        "cache_path",
        lambda _account: tmp_path / "alice.json",
    )
    cached_store = IssueStore(
        [_issue_record("1", title="Cached 1"), _issue_record("2", title="Cached 2")]
    )
    cached_store.select("2")
    context_store.save_quick_view(
        "alice",
        "my_assigned",
        cached_store,
        filters={},
    )

    items = tuple(
        RedmineIssueListItem(
            id=issue_id,
            url=f"https://redmine/issues/{issue_id}",
            tracker="Bug",
            status="New",
            subject=f"Fresh {issue_id}",
        )
        for issue_id in fresh_ids
    )
    project = RedmineProject(
        name="P",
        identifier="p",
        url="https://redmine/projects/p",
        project_id="PID",
        issues=items,
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._account = "alice"
    bridge._issue_controller.activate_view("my_assigned")
    bridge._load_quick_view_cache("my_assigned")
    assert bridge._issue_controller._store.selected_id == "2"
    bridge._data_generation = 1
    bridge._data_loading = True
    bridge._data_operation_kind = "my_assigned"

    bridge._apply_data(
        1,
        (RedmineContext(projects=(project,)), "p", None, {}, None),
    )

    persisted = context_store.load_quick_view("alice", "my_assigned")
    assert bridge._issue_controller._store.selected_id == expected_selected_id
    assert persisted["selected_issue_id"] == expected_selected_id
    assert [issue.id for issue in persisted["issue_list"]] == list(fresh_ids)
    bridge.close()


def test_empty_my_assigned_refresh_clears_and_persists_active_quick_view(
    monkeypatch, tmp_path
):
    from support.jira_integration.core import IssueStore
    from tool.SmartHome.redmine import context_store

    monkeypatch.setattr(
        context_store,
        "cache_path",
        lambda _account: tmp_path / "alice.json",
    )
    cached_store = IssueStore([_issue_record("stale", title="Stale issue")])
    cached_store.select("stale")
    context_store.save_quick_view(
        "alice",
        "my_assigned",
        cached_store,
        filters={},
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._account = "alice"
    bridge._issue_controller.activate_view("my_assigned")
    bridge._load_quick_view_cache("my_assigned")
    assert bridge._issue_controller._store.selected_id == "stale"
    bridge._data_generation = 1
    bridge._data_loading = True
    bridge._data_operation_kind = "my_assigned"

    bridge._apply_data(1, ("quick_view_empty",))

    persisted = context_store.load_quick_view("alice", "my_assigned")
    assert bridge._issue_controller._store.issue_list == ()
    assert bridge._issue_controller._store.selected_id is None
    assert bridge.dataStatusText == "Issues assigned to me loaded."
    assert persisted["issue_list"] == []
    assert persisted["selected_issue_id"] == ""
    bridge.close()


def test_filter_request_during_search_is_queued_without_overlapping_refresh(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._projects_ready = True
    bridge._data_loading = True
    bridge._data_operation_kind = "search"
    calls = []
    monkeypatch.setattr(bridge, "refreshData", lambda: calls.append("refresh"))
    bridge.applyFilters({"status": "Open"})
    assert calls == []
    assert bridge._refresh_after_search is True
    assert bridge._pending_filters["status"] == "Open"
    bridge.close()


def test_fresh_search_result_applies_requested_filters_not_cached_filters(monkeypatch):
    from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineProject
    from tool.SmartHome.redmine.view_model import view
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._data_generation = 2
    bridge._data_loading = True
    bridge._data_operation_kind = "search"
    bridge._active_search_filter_requested = True
    bug = RedmineIssueListItem(id="b", url="ub", tracker="Bug", status="New", subject="bug")
    support = RedmineIssueListItem(id="s", url="us", tracker="Support", status="New", subject="support")
    project = RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=(support,))
    context = RedmineContext(projects=(project,), issues=(RedmineIssueDetail(id="s", url="us", project_identifier="p", tracker="Support", subject="support", list_item=support),))
    previous_context = RedmineContext(projects=(project,))
    _set_bridge_projection(
        bridge,
        previous_context,
        view(
            previous_context,
            all_projects="All projects",
            filters={"type": "Bug"},
        )
    )
    monkeypatch.setattr("ui.example.bridge.RedmineBridge.context_store.save_view", lambda *args, **kwargs: None)
    bridge._apply_data(2, (context, "p", context.issues[0], {"type": "Support"}, {}))
    assert bridge.filters["type"] == "Support"
    assert [row["id"] for row in bridge.issueRows] == ["s"]
    bridge.close()


def test_clone_work_uses_preanalysis_plan_when_due_row_becomes_hidden():
    from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueListItem, RedmineProject
    from tool.SmartHome.redmine.view_model import view
    class RecordingChecker:
        def __init__(self): self.ids = []
        def check_many(self, rows, *, progress_callback=None, progress_base=0, progress_total=None):
            self.ids = [row["id"] for row in rows]
            for index, _row in enumerate(rows, 1): progress_callback(progress_base + index, progress_total, "clone")
            return {}
    issues = (RedmineIssueListItem(id="ok", url="u1", tracker="Bug", status="New", subject="ok"), RedmineIssueListItem(id="due", url="u2", tracker="Bug", status="New", subject="due"))
    project = RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=issues)
    controller = RedmineIssueController(all_projects="All projects")
    planned_rows = controller.enrichment_projection(
        RedmineContext(projects=(project,)), {}
    ).issue_rows
    final_context = RedmineContext(projects=(project,), raw={"issue_analysis": {"ok": {"risk": "green"}, "due": {"risk": "unknown", "reason": "due_date_not_reached"}}})
    assert [
        row["id"]
        for row in controller.enrichment_projection(final_context, {}).issue_rows
    ] == ["ok"]
    checker = RecordingChecker()
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)), clone_checker=checker)
    bridge._data_loading = True
    bridge._check_clone_status(planned_rows, progress_base=2, progress_total=4)
    assert checker.ids == ["ok", "due"]
    assert (bridge.dataLoaded, bridge.dataTotal) == (4, 4)
    bridge.close()


def test_redmine_view_creates_complete_unified_records_for_canonical_projections():
    from support.jira_integration.core import UnifiedIssue
    from tool.SmartHome.redmine.view_model import (
        detail_row_from_unified,
        issue_row_from_unified,
        view,
    )

    item = RedmineIssueListItem(
        id="60371",
        url="https://redmine/issues/60371",
        tracker="Bug",
        status="New",
        priority="High",
        subject="Playback fails",
        assignee="Alice",
    )
    project = RedmineProject(
        name="SmartHome",
        identifier="sh",
        url="https://redmine/projects/sh",
        project_id="PID",
        issues=(item,),
    )

    projected = view(
        RedmineContext(
            projects=(project,),
            raw={"issue_analysis": {"60371": {"party": "customer"}}},
        ),
        all_projects="All projects",
    )

    issue = projected["issue_list"][0]
    assert isinstance(issue, UnifiedIssue)
    assert set(issue.to_dict()) == set(UnifiedIssue().to_dict())
    assert issue.detail_state == "unloaded"
    assert issue.project["identifier"] == "sh"
    row = issue_row_from_unified(issue)
    assert row["id"] == "60371"
    assert row["updateParty"] == "customer"
    assert "updatePartyText" not in row
    assert detail_row_from_unified(issue)["id"] == "60371"


def test_canonical_issue_projection_keeps_analysis_fields():
    from tool.SmartHome.redmine.view_model import (
        detail_row_from_unified,
        issue_row_from_unified,
        unified_issue,
    )

    project = RedmineProject(
        name="SmartHome",
        identifier="sh",
        url="https://redmine/projects/sh",
        project_id="PID",
    )
    item = RedmineIssueListItem(
        id="60371",
        url="https://redmine/issues/60371",
        tracker="Bug",
        status="New",
        subject="Playback fails",
    )
    analysis = {"risk": "red", "party": "customer"}

    issue = unified_issue(project, item, analysis=analysis)
    assert issue_row_from_unified(issue)["updateParty"] == "customer"
    assert detail_row_from_unified(issue)["updateRisk"] == "red"


def test_redmine_cached_bridge_projections_are_defensive(monkeypatch):
    from support.jira_integration.core import UnifiedIssue
    from tool.SmartHome.redmine import context_store

    issue = UnifiedIssue(
        id="60371",
        key="60371",
        title="Original",
        clone={
            "state": "cloned",
            "issue_key": "SH-1",
            "issue_url": "https://jira/browse/SH-1",
        },
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._account = "alice"
    monkeypatch.setattr(
        context_store,
        "load_view",
        lambda *_args, **_kwargs: {
            "issue_list": [issue],
            "selected_issue_id": "60371",
            "filters": {},
        },
    )
    bridge._load_cached_view()
    projection = bridge.issueRows
    projection[0]["title"] = "Changed outside"

    assert bridge._issue_controller._store.get("60371").title == "Original"
    assert bridge._issue_controller._store.selected_id == "60371"
    assert bridge.issueRows[0]["clonedIssueKey"] == "SH-1"
    bridge.close()


def test_redmine_detail_result_patches_one_selected_store_record(monkeypatch):
    from tool.SmartHome.redmine.view_model import view

    item = RedmineIssueListItem(
        id="60371",
        url="https://redmine/issues/60371",
        tracker="Bug",
        status="New",
        subject="Playback fails",
    )
    project = RedmineProject(
        name="SmartHome",
        identifier="sh",
        url="https://redmine/projects/sh",
        project_id="PID",
        issues=(item,),
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._state = AuthState.AUTHENTICATED
    source_context = RedmineContext(projects=(project,))
    _set_bridge_projection(
        bridge,
        source_context,
        view(
            source_context,
            all_projects="All projects",
        )
    )
    detail = RedmineIssueDetail(
        id="60371",
        url=item.url,
        project_identifier="sh",
        subject=item.subject,
        description="Hydrated",
        attributes={"Status": "New"},
        list_item=item,
    )
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.context_store.save_view",
        lambda *_args, **_kwargs: None,
    )
    bridge._data_generation = 4
    bridge._data_loading = True
    bridge._data_operation_kind = "detail"

    bridge._apply_data(4, ("detail", "60371", detail))

    assert len(bridge._issue_controller._store.issue_list) == 1
    assert bridge._issue_controller._store.selected_id == "60371"
    assert bridge._issue_controller._store.get("60371").detail_state == "loaded"
    assert bridge.selectedIssue["description"] == "Hydrated"
    bridge.close()


def test_quick_view_detail_hydration_persists_only_active_cache_destination(
    monkeypatch, tmp_path
):
    from support.jira_integration.core import IssueStore
    from tool.SmartHome.redmine import context_store

    monkeypatch.setattr(
        context_store,
        "cache_path",
        lambda _account: tmp_path / "alice.json",
    )
    search_store = IssueStore([_issue_record("search", title="Search")])
    search_store.select("search")
    quick_store = IssueStore([_issue_record("quick", title="Quick")])
    quick_store.select("quick")
    context_store.save_view("alice", search_store, filters={"text": "search"})
    context_store.save_quick_view(
        "alice",
        "my_assigned",
        quick_store,
        filters={"text": "quick"},
    )

    item = RedmineIssueListItem(
        id="quick",
        url="https://redmine/issues/quick",
        tracker="Bug",
        status="New",
        subject="Quick",
    )
    project = RedmineProject(
        name="P",
        identifier="p",
        url="https://redmine/projects/p",
        project_id="PID",
        issues=(item,),
    )
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    bridge._account = "alice"
    bridge._issue_controller.activate_view("my_assigned")
    source_context = RedmineContext(projects=(project,))
    _set_bridge_projection(
        bridge,
        source_context,
        view(
            source_context,
            all_projects="All projects",
            filters={"text": "quick"},
        )
    )
    detail = RedmineIssueDetail(
        id="quick",
        url=item.url,
        project_identifier="p",
        subject=item.subject,
        description="Hydrated quick detail",
        attributes={"Status": "New"},
        list_item=item,
    )
    bridge._data_generation = 2
    bridge._data_loading = True
    bridge._data_operation_kind = "detail"

    bridge._apply_data(2, ("detail", "quick", detail))

    default = context_store.load_view("alice")
    quick = context_store.load_quick_view("alice", "my_assigned")
    assert [issue.id for issue in default["issue_list"]] == ["search"]
    assert [issue.id for issue in quick["issue_list"]] == ["quick"]
    assert quick["issue_list"][0].description == "Hydrated quick detail"
    assert quick["issue_list"][0].detail_state == "loaded"
    bridge.close()


def test_clone_checker_unavailable_or_failed_preserves_cached_clone_state(monkeypatch):
    from support.jira_integration.core import UnifiedIssue

    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    _set_bridge_records(
        bridge,
        [
            UnifiedIssue(
                id="1",
                key="1",
                clone={
                    "state": "cloned",
                    "issue_key": "SH-1",
                    "issue_url": "https://jira/browse/SH-1",
                },
            )
        ],
        selected_id="1",
    )
    monkeypatch.setattr(bridge, "_checker", lambda: None)
    unavailable = bridge._check_clone_status([{"id": "1"}])
    assert unavailable is None
    bridge._issue_controller._patch_clone_results(unavailable, complete=True)
    assert bridge._issue_controller._store.get("1").clone["state"] == "cloned"

    class FailingChecker:
        def check_many(self, *_args, **_kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(bridge, "_checker", lambda: FailingChecker())
    failed = bridge._check_clone_status([{"id": "1"}])
    assert failed is None
    bridge._issue_controller._patch_clone_results(failed, complete=True)
    assert bridge._issue_controller._store.get("1").clone["issue_key"] == "SH-1"
    bridge.close()


def test_successful_clone_check_with_no_match_sets_not_cloned():
    from support.jira_integration.core import UnifiedIssue

    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )
    _set_bridge_records(
        bridge,
        [
            UnifiedIssue(
                id="1",
                key="1",
                clone={
                    "state": "cloned",
                    "issue_key": "SH-1",
                    "issue_url": "https://jira/browse/SH-1",
                },
            )
        ],
        selected_id="1",
    )

    bridge._issue_controller._patch_clone_results({}, complete=True)

    assert bridge._issue_controller._store.get("1").clone == {
        "state": "not_cloned",
        "issue_key": "",
        "issue_url": "",
        "checked": True,
    }
    bridge.close()


def test_clone_submit_patches_and_persists_active_store(monkeypatch):
    bridge = clone_bridge(persist=True)
    bridge._issue_controller.activate_view("my_assigned")
    bridge.prepareCloneDrafts()
    wait_for(lambda: bridge.cloneBatchState == "editing")
    bridge._batch_controller._state = "submitting"
    saved = []
    monkeypatch.setattr(
        "ui.example.bridge.RedmineBridge.context_store.save_quick_view",
        lambda account, view_id, store, **kwargs: saved.append(
            (account, view_id, store.snapshot(), kwargs)
        ),
    )
    result = CreateIssueResult(
        created=False,
        existing_key="SH-1",
        issue_url="https://jira/browse/SH-1",
    )

    bridge._apply_clone_result(
        bridge._batch_controller.generation,
        bridge._generation,
        "submit",
        [("1", result)],
    )

    assert bridge._issue_controller._store.get("1").clone["state"] == "cloned"
    assert len(saved) == 1
    assert saved[0][1] == "my_assigned"
    assert saved[0][2]["issue_list"][0]["clone"]["issue_key"] == "SH-1"
    bridge.close()


def test_bridge_has_no_reverse_legacy_issue_ingress():
    bridge = RedmineBridge(
        FakeAuth(),
        service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)),
    )

    assert not hasattr(RedmineBridge, "_view")
    assert not hasattr(RedmineBridge, "_load_cached_projection")
    assert not hasattr(RedmineBridge, "_replace_issue_view")
    bridge.close()


def _controller_project(*issues):
    return RedmineProject(
        name="Project",
        identifier="project",
        url="https://redmine/projects/project",
        project_id="P1",
        issues=issues,
    )


def _controller_item(issue_id, *, title="Issue"):
    return RedmineIssueListItem(
        id=issue_id,
        url=f"https://redmine/issues/{issue_id}",
        tracker="Bug",
        status="Open",
        subject=title,
    )


def _issue_controller(*, account="alice"):
    return RedmineIssueController(
        account=account,
        all_projects="All projects",
    )


def test_issue_controller_reconciles_projection_and_preserves_selection(monkeypatch):
    from tool.SmartHome.redmine import issue_controller as module

    first = _controller_item("1", title="First")
    second = _controller_item("2", title="Second")
    context = RedmineContext(
        account="alice", projects=(_controller_project(first, second),)
    )
    cached_second = UnifiedIssue(
        id="2",
        key="2",
        source_system="redmine",
        title="Second",
        project={
            "id": "P1",
            "identifier": "project",
            "name": "Project",
            "url": "",
        },
        detail_state="loaded",
        clone={
            "state": "cloned",
            "issue_key": "SH-2",
            "issue_url": "https://jira/SH-2",
            "checked": True,
        },
    )
    reconcile_calls = []
    persisted = []

    def reconcile(_account, records, *, known_records=()):
        reconcile_calls.append([issue.id for issue in known_records])
        return [records[0], cached_second]

    monkeypatch.setattr(module.context_store, "reconcile_issue_records", reconcile)
    monkeypatch.setattr(
        module.context_store,
        "save_quick_view",
        lambda account, view_id, store, *, filters: persisted.append(
            (
                account,
                view_id,
                [issue.id for issue in store.issue_list],
                store.selected_id,
                dict(filters),
            )
        ),
    )
    controller = _issue_controller()
    controller.activate_view("my_assigned")
    controller.replace_result(context, filters={})
    controller.select_issue("2")
    snapshot = controller.replace_result(context, filters={"text": "panel"})

    assert reconcile_calls == [[], ["1", "2"]]
    assert snapshot.selected_id == "2"
    assert snapshot.selected_issue["clonedIssueKey"] == "SH-2"
    assert snapshot.filters["text"] == "panel"
    assert persisted[-1][0:4] == ("alice", "my_assigned", ["1", "2"], "2")


def test_issue_controller_selects_source_and_hydrates_current_detail(monkeypatch):
    from tool.SmartHome.redmine import issue_controller as module

    item = _controller_item("7")
    project = _controller_project(item)
    context = RedmineContext(account="alice", projects=(project,))
    monkeypatch.setattr(
        module.context_store,
        "reconcile_issue_records",
        lambda _account, records, **_kwargs: list(records),
    )
    monkeypatch.setattr(module.context_store, "save_view", lambda *_args, **_kwargs: None)
    controller = _issue_controller()
    controller.activate_view("")
    controller.replace_result(context, filters={})

    selection = controller.select_issue("7")
    assert selection.project == project
    assert selection.item == item
    assert selection.needs_detail is True
    detail = RedmineIssueDetail(
        id="7",
        url=item.url,
        tracker="Bug",
        subject="Hydrated",
        list_item=item,
    )
    assert controller.apply_selected_detail("other", detail) is False
    assert controller.apply_selected_detail("7", detail) is True
    assert controller.snapshot.selected_issue["title"] == "Hydrated"
    assert controller.source_for_issue("7").detail == detail


def test_issue_controller_owns_clone_patch_and_active_view_persistence(monkeypatch):
    from tool.SmartHome.redmine import issue_controller as module

    item = _controller_item("9")
    context = RedmineContext(account="alice", projects=(_controller_project(item),))
    saved = []
    monkeypatch.setattr(
        module.context_store,
        "reconcile_issue_records",
        lambda _account, records, **_kwargs: list(records),
    )
    monkeypatch.setattr(
        module.context_store,
        "save_quick_view",
        lambda _account, view_id, *_args, **_kwargs: saved.append(view_id),
    )
    controller = _issue_controller()
    controller.activate_view("watched")
    controller.replace_result(context, filters={})
    controller.record_clone_results(
        {
            "9": type(
                "Existing",
                (),
                {"key": "SH-9", "web_url": "https://jira/SH-9"},
            )()
        },
    )

    assert controller.snapshot.issue_rows[0]["clonedIssueKey"] == "SH-9"
    assert saved == ["watched", "watched"]


def test_issue_controller_project_metadata_refresh_does_not_persist_a_new_view(monkeypatch):
    from tool.SmartHome.redmine import issue_controller as module

    item = _controller_item("10")
    project = RedmineProject(
        name="Project",
        identifier="project",
        url="https://redmine/projects/project",
        project_id="",
        issues=(item,),
    )
    saved = []
    monkeypatch.setattr(
        module.context_store,
        "reconcile_issue_records",
        lambda _account, records, **_kwargs: list(records),
    )
    monkeypatch.setattr(
        module.context_store,
        "save_quick_view",
        lambda *_args, **_kwargs: saved.append("saved"),
    )
    controller = _issue_controller()
    controller.activate_view("my_assigned")
    controller.replace_result(
        RedmineContext(account="alice", projects=(project,)),
        filters={"status": "Open"},
    )
    saved.clear()

    controller.apply_project_options(
        [{"id": "project", "label": "Project", "projectId": "P1"}]
    )

    assert saved == []
    assert controller.snapshot.issue_rows[0]["projectId"] == "P1"


def test_issue_controller_empty_result_preserves_view_metadata_but_watched_clear_resets_it(monkeypatch):
    from tool.SmartHome.redmine import issue_controller as module

    item = _controller_item("11")
    monkeypatch.setattr(
        module.context_store,
        "reconcile_issue_records",
        lambda _account, records, **_kwargs: list(records),
    )
    monkeypatch.setattr(
        module.context_store, "save_quick_view", lambda *_args, **_kwargs: None
    )
    controller = _issue_controller()
    controller.activate_view("my_assigned")
    controller.replace_result(
        RedmineContext(
            account="alice", projects=(_controller_project(item),)
        ),
        filters={"status": "Open"},
    )

    empty = controller.clear_active_view()
    assert empty.filters["status"] == "Open"
    assert empty.project_filter_labels == ("All projects", "Project [P1]")

    watched = controller.clear_watched_view()
    assert watched.filters["status"] == ""
    assert watched.project_filter_labels == ("All projects",)


def test_redmine_bridge_keeps_issue_state_behind_controller_boundary():
    source = (
        Path(__file__).resolve().parents[3] / "ui/example/bridge/RedmineBridge.py"
    ).read_text(encoding="utf-8")

    assert "from tool.SmartHome.redmine.issue_controller import RedmineIssueController" in source
    assert "self._issue_controller = RedmineIssueController(" in source
    assert "from tool.SmartHome.redmine.clone_controller import RedmineCloneController" in source
    assert "self._batch_controller = RedmineCloneController(" in source
    for forbidden in (
        "self._issue_store",
        "self._context",
        "self._filters",
        "self._project_filter_labels",
        "self._status_filter_labels",
        "self._type_filter_labels",
        "self._clone_batch_state",
        "self._clone_selected_ids",
        "self._clone_draft_records",
        "self._clone_batch_loaded",
        "self._clone_batch_total",
        "self._clone_batch_error",
        "self._clone_user_options",
        "field.schema.required",
    ):
        assert forbidden not in source
    for migrated_helper in (
        "def _replace_store(",
        "def _replace_issue_view(",
        "def _load_cached_projection(",
        "def _apply_clone_status(",
        "def _persist_issue_store(",
    ):
        assert migrated_helper not in source
