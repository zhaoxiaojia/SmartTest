import asyncio
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Signal

from tool.SmartHome.redmine.models import AuthResult, AuthState
from support.jira_integration.core.create_schema import CreateFieldControl, CreateFieldSchema
from support.jira_integration.core.models import CreateIssueResult, ExistingIssue
from tool.SmartHome.redmine.clone_draft import RedmineCloneDraftService
from tool.SmartHome.redmine.models import RedmineContext, RedmineIssueDetail, RedmineIssueListItem, RedmineProject
from ui.example.bridge.RedmineBridge import RedmineBridge, _AsyncLoopWorker
from ui.example.bridge.ToolBridge import build_tool_groups


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
    bridge._view = {
        "context": None,
        "context_payload": {},
        "issueRows": [{"id": "61043", "key": "61043", "title": "panel", "webUrl": "https://support/issues/61043"}],
        "selectedIssue": {"id": "61043", "key": "61043", "title": "panel", "webUrl": "https://support/issues/61043"},
    }

    bridge._apply_clone_status({"61043": ExistingIssue(key="SH-26384", web_url="https://jira/browse/SH-26384")})

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
    bridge._view = {
        **bridge._view,
        "issueRows": [
            {"id": "3", "cloneStatus": "not_cloned"},
            {"id": "1", "cloneStatus": "cloned"},
            {"id": "2", "cloneStatus": "not_cloned"},
        ],
    }

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
    CreateFieldSchema("description", "Description", False, CreateFieldControl.MULTILINE),
    CreateFieldSchema("reporter", "Reporter", False, CreateFieldControl.USER),
    CreateFieldSchema("customfield_10409", "FAE Coworker", False, CreateFieldControl.USER),
)


class CloneJiraClient:
    def __init__(self, account="defeng.zhai"):
        self.account = account
        self.search_calls = []

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
        self.duplicates = {}
        self.fail_once = set()

    def check_issue_by_external_url(self, *, project_key, external_url):
        self.rechecks.append((project_key, external_url))
        return self.duplicates.get(external_url)

    def create_issue(self, request):
        self.creates.append(request.source_id)
        if request.source_id in self.fail_once:
            self.fail_once.remove(request.source_id)
            raise RuntimeError(f"failed {request.source_id}")
        return CreateIssueResult(
            created=True,
            issue_key=f"SH-{request.source_id}",
            issue_url=f"https://jira/browse/SH-{request.source_id}",
        )


class RecordingDraftService:
    def __init__(self):
        self.calls = []
        self.owner = RedmineCloneDraftService()

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return self.owner.build(**kwargs)


def clone_bridge(*, issue_ids=("1",), schema=CLONE_SCHEMA):
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
    bridge._view = {
        **bridge._view,
        "context": RedmineContext(account=auth.username, projects=(project,), issues=details),
        "issueRows": [{"id": item.id, "key": item.id, "webUrl": item.url, "cloneStatus": "not_cloned"} for item in items],
    }
    bridge._jira_client = CloneJiraClient(auth.username)
    bridge._jira_schema_service = CloneSchemaService(schema)
    bridge._jira_create_service = CloneCreateService()
    bridge._draft_service = RecordingDraftService()
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
    assert [item["fieldId"] for item in bridge.cloneDrafts[0]["fields"]] == [item.field_id for item in CLONE_SCHEMA]
    assert bridge._draft_service.calls[0]["account"] == "defeng.zhai"
    assert bridge._draft_service.calls[0]["department"] == "FAE-SW"
    assert bridge.cloneDrafts[0]["fields"][4]["value"] == "defeng.zhai"
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


def test_clone_account_and_user_search_generations_reject_late_results():
    bridge = clone_bridge()
    bridge.prepareCloneDrafts(); wait_for(lambda: bridge.cloneBatchState == "editing")
    old_clone_generation = bridge._clone_generation
    old_account_generation = bridge._generation
    bridge.searchCloneUsers("1", "reporter", "fred")
    current_generation = bridge._clone_generation
    bridge._apply_clone_result(old_clone_generation, old_account_generation, "users", ("1", "reporter", [{"account": "old", "display_name": "Old"}]))
    assert all(item.get("value") != "old" for item in bridge.cloneDrafts[0]["fields"][4]["options"])
    bridge._apply_clone_result(current_generation, old_account_generation, "users", ("1", "reporter", [{"account": "fred", "display_name": "Fred", "avatar_url": "a"}]))
    assert bridge.cloneDrafts[0]["fields"][4]["options"][0]["value"] == "fred"

    bridge._auth.username = "other"; bridge._auth.authChanged.emit()
    assert bridge.cloneBatchState == "idle" and bridge.cloneDrafts == []
    bridge._apply_clone_result(current_generation, old_account_generation, "prepare", [])
    assert bridge.cloneBatchState == "idle"
    bridge.close()


def test_clone_batch_close_cancels_loading_but_not_submission():
    class Pending:
        def __init__(self): self.cancelled = False
        def cancel(self): self.cancelled = True

    bridge = clone_bridge()
    pending = Pending()
    bridge._clone_future = pending
    bridge._clone_batch_state = "loading"
    bridge.closeCloneBatch()
    assert pending.cancelled and bridge.cloneBatchState == "idle"

    bridge._clone_batch_state = "submitting"
    bridge.closeCloneBatch()
    assert bridge.cloneBatchState == "submitting"
    bridge._clone_batch_state = "idle"
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
    bridge._view = {**bridge._view, "projectFilterLabels": ["All projects", "Alice project"], "issueRows": [{"id": "1"}]}
    bridge._clone_checker = object()

    auth.username = "bob"; auth.password = "bob-secret"; auth.authChanged.emit()

    assert bridge.state == "idle" and bridge.account == ""
    assert bridge.projectFilterLabels == ["All projects"]
    assert bridge.statusFilterLabels == ["All statuses", "Open", "Closed"]
    assert bridge.typeFilterLabels == ["All types"]
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


def test_explicit_search_clears_active_quick_view(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED; bridge._projects_ready = True; bridge._active_quick_view_id = "my_assigned"
    monkeypatch.setattr(bridge, "_launch_data_load", lambda operation, **kwargs: None)
    bridge.applyFilters({"status": "Open"})
    assert bridge.activeQuickViewId == ""
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
    bridge._view = view(context, all_projects="All projects", all_statuses="All statuses")
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
    bridge._view = view(context, all_projects="All projects", all_statuses="All statuses")
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


def test_apply_filters_requests_fresh_search_instead_of_finalizing_cached_view(monkeypatch):
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)))
    bridge._state = AuthState.AUTHENTICATED
    bridge._projects_ready = True
    requested = []
    monkeypatch.setattr(bridge, "refreshData", lambda: requested.append(dict(bridge._pending_filters or {})))
    bridge.applyFilters({"project": "P", "status": "Open", "type": "Bug", "text": "needle"})
    assert requested == [{"project": "P", "status": "Open", "type": "Bug", "text": "needle"}]
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
    cached = {**bridge._view, "issueRows": [{"id": "mine"}]}
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
    project = RedmineProject(name="P", identifier="p", url="u", project_id="P", issues=(bug, support))
    context = RedmineContext(projects=(project,), issues=(RedmineIssueDetail(id="s", url="us", project_identifier="p", tracker="Support", subject="support", list_item=support),))
    bridge._view = view(RedmineContext(projects=(project,)), all_projects="All projects", all_statuses="All statuses", filters={"type": "Bug"})
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
    planned_rows = view(RedmineContext(projects=(project,)), all_projects="All projects", all_statuses="All statuses")["issueRows"]
    final_context = RedmineContext(projects=(project,), raw={"issue_analysis": {"ok": {"risk": "green"}, "due": {"risk": "unknown", "reason": "due_date_not_reached"}}})
    assert [row["id"] for row in view(final_context, all_projects="All projects", all_statuses="All statuses")["issueRows"]] == ["ok"]
    checker = RecordingChecker()
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: FakeService(AuthResult(AuthState.IDLE)), clone_checker=checker)
    bridge._data_loading = True
    bridge._check_clone_status(planned_rows, progress_base=2, progress_total=4)
    assert checker.ids == ["ok", "due"]
    assert (bridge.dataLoaded, bridge.dataTotal) == (4, 4)
    bridge.close()
