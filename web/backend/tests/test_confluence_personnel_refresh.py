from fastapi.testclient import TestClient

from smarttest_web.app import create_app
import smarttest_web.app as app_module
from smarttest_web.confluence_personnel_refresh import ConfluencePersonnelRefreshScheduler


class Tasks:
    def __init__(self):
        self.runners = []

    def submit(self, label, runner):
        self.runners.append((label, runner))


def test_scheduler_submits_once_per_account_without_running_inline(monkeypatch):
    tasks = Tasks()
    scheduler = ConfluencePersonnelRefreshScheduler(tasks)
    owners = []
    assert scheduler.schedule("Coco", "secret", lambda *_: owners.append(True)) is True
    assert scheduler.schedule("coco", "secret", lambda *_: owners.append(True)) is False
    assert len(tasks.runners) == 1
    assert owners == []


class Authenticator:
    def authenticate(self, username, password):
        return {"success": True, "username": username, "display_name": username}


def test_login_and_session_restore_use_current_account_and_shared_dedup_owner():
    tasks = Tasks()
    refresh = ConfluencePersonnelRefreshScheduler(tasks)
    owner_calls = []
    app = create_app(
        authenticator=Authenticator,
        confluence_personnel_refresh=lambda: refresh,
        confluence_personnel_owner=lambda *values: owner_calls.append(values),
    )
    api = TestClient(app)

    assert api.post("/api/auth/login", json={"username": "coco", "password": "secret"}).status_code == 200
    assert api.get("/api/auth/session").status_code == 200
    assert len(tasks.runners) == 1 and owner_calls == []


def test_default_owner_reuses_current_credentials_for_confluence_and_jira_without_ldap(monkeypatch):
    seen, captured = [], {}
    class Confluence:
        def __init__(self, _config, username, password): seen.append((username, password))
    monkeypatch.setattr(app_module, "LdapAuthenticator",
                        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("personnel sync must not use LDAP")))
    monkeypatch.setattr(app_module, "ConfluenceGateway", Confluence)
    class Jira:
        def __init__(self, _base_url, username, password): seen.append((username, password))
        def search_users(self, account): return [{"account": account}]
    monkeypatch.setattr(app_module, "JiraGateway", Jira)
    def sync(gateway, _path, **kwargs):
        captured.update({"gateway": gateway, **kwargs}); return object()
    monkeypatch.setattr(app_module, "PersonnelAssignmentSync", sync)
    app_module.default_confluence_personnel_owner("coco", "secret")
    assert isinstance(captured["gateway"], Confluence)
    assert seen == [("coco", "secret"), ("coco", "secret")]
    assert captured["jira_user_resolver"]("new.user") == [{"account": "new.user"}]


def test_session_restore_runs_confluence_identity_lookup_and_never_constructs_ldap(monkeypatch):
    queries = []
    class Confluence:
        def __init__(self, _config, _username, _password): pass
        def resolve_user_keys(self, values): queries.extend(values); return {}
    class Sync:
        def __init__(self, gateway, _path, **_kwargs): self.gateway = gateway
        def refresh(self): return self.gateway.resolve_user_keys(("user-key-1",))
    class ImmediateRefresh:
        def schedule(self, account, password, owner_factory, **_context):
            owner_factory(account, password).refresh()
            return True
    monkeypatch.setattr(app_module, "ConfluenceGateway", Confluence)
    monkeypatch.setattr(app_module, "PersonnelAssignmentSync", Sync)
    monkeypatch.setattr(app_module, "LdapAuthenticator",
                        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("session restore must not use LDAP")))
    app = create_app(
        authenticator=Authenticator,
        confluence_personnel_refresh=ImmediateRefresh,
        confluence_personnel_owner=app_module.default_confluence_personnel_owner,
    )
    api = TestClient(app)
    assert api.post("/api/auth/login", json={"username": "coco", "password": "secret"}).status_code == 200
    queries.clear()

    assert api.get("/api/auth/session").status_code == 200
    assert queries == ["user-key-1"]


def test_scheduler_failure_log_contains_safe_stage_without_external_message(monkeypatch):
    records = []
    monkeypatch.setattr("smarttest_web.confluence_personnel_refresh.smart_log",
                        lambda message, **fields: records.append((message, fields)))
    error = RuntimeError("SECRET page body")
    error.sync_stage, error.sync_code = "confluence_rest", "confluence_rest_failed"
    error.status_code, error.sync_reason = 503, "transient-exhausted"
    class Owner:
        def refresh(self): raise error

    assert ConfluencePersonnelRefreshScheduler._run("coco", "secret", lambda *_: Owner()) is False
    assert records[0][1]["extra"] == {
        "exception_type": "RuntimeError", "stage": "confluence_rest",
        "exception_code": "confluence_rest_failed", "exception_message": "confluence_rest_failed",
        "http_status": 503, "reason": "transient-exhausted",
    }
    assert records[0][0] == (
        "Confluence personnel assignment refresh failed stage=confluence_rest "
        "code=confluence_rest_failed type=RuntimeError http_status=503 reason=transient-exhausted"
    )
    assert "SECRET" not in repr(records) and "coco" not in repr(records) and "secret" not in repr(records)
