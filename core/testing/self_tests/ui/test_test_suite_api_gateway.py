import json
from http.cookiejar import Cookie
from urllib.error import HTTPError

import pytest
from pathlib import Path

from client.app.data_sources.common import (
    AuthenticatedCredentials,
    DataSourceError,
    DataSourceResult,
)
from client.app.data_sources.web_test_suites import WebTestSuiteSource


class Response:
    def __init__(self, payload=b"{}", *, headers=None, status=200):
        self.payload = payload
        self.headers = headers or {}
        self.status = status
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return self.payload


class Opener:
    def __init__(self): self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return Response(json.dumps({"authenticated": True}).encode())


def test_web_source_uses_single_cookie_opener_and_never_places_password_in_url():
    opener = Opener()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    result = source.list_suites(AuthenticatedCredentials("coco", "very-secret"), "mine")
    assert result.ok
    assert opener.requests[0].full_url == "https://testserver/api/auth/client-session"
    assert b"very-secret" in opener.requests[0].data
    assert "very-secret" not in repr(opener.requests[0])
    assert opener.requests[1].full_url.endswith("/api/test-suites?scope=mine")


def test_web_source_maps_http_states_without_leaking_response(monkeypatch):
    class Failing:
        def open(self, *_args, **_kwargs):
            raise HTTPError("https://test", 409, "Conflict", {},
                            Response(b'{"detail":{"state":"revision_conflict"},"password":"secret"}'))
    source = WebTestSuiteSource("https://testserver", opener=Failing())
    source._authenticated_username = "coco"
    result = source.get_suite(AuthenticatedCredentials("coco", "secret"), "id")
    assert result.error == DataSourceError(
        "revision_conflict", retryable=False, stage="get", http_status=409
    )
    assert "secret" not in str(result.error)


def test_web_source_recovers_on_refresh_after_initial_outage():
    class Recovering:
        def __init__(self): self.calls = []; self.available = False
        def open(self, request, timeout):
            self.calls.append(request.full_url)
            if not self.available:
                from urllib.error import URLError
                raise URLError("offline")
            if request.full_url.endswith("/api/auth/client-session"):
                return Response(b'{"authenticated":true}')
            return Response(b'[{"id":"suite-1","name":"Recovered"}]')

    opener = Recovering()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    credentials = AuthenticatedCredentials("coco", "secret")
    first = source.list_suites(credentials, "mine")
    assert first.error == DataSourceError("service_unavailable", retryable=True, stage="login")
    opener.available = True
    second = source.list_suites(credentials, "mine")
    assert second == DataSourceResult.success([{"id": "suite-1", "name": "Recovered"}])
    assert opener.calls.count("https://testserver/api/auth/client-session") == 2


def test_web_source_never_retries_ambiguous_write_timeout():
    class TimeoutWrite:
        def __init__(self): self.calls = 0
        def open(self, request, timeout):
            self.calls += 1
            raise TimeoutError

    opener = TimeoutWrite()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    credentials = AuthenticatedCredentials("coco", "secret")
    source._authenticated_username = "coco"
    result = source.create_suite(credentials, {"name": "once"})
    assert result.error == DataSourceError("service_unavailable", retryable=True, stage="create")
    assert opener.calls == 1


def test_get_reauthenticates_and_replays_once_after_explicit_401():
    class ExpiredGet:
        def __init__(self): self.get_calls = 0; self.login_calls = 0
        def open(self, request, timeout):
            if request.full_url.endswith("/api/auth/client-session"):
                self.login_calls += 1
                return Response(b'{"authenticated":true}')
            self.get_calls += 1
            if self.get_calls == 1:
                raise HTTPError(request.full_url, 401, "Unauthorized", {},
                                Response(b'{"detail":{"state":"unauthenticated"}}'))
            return Response(b'{"id":"suite-1"}')

    opener = ExpiredGet()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    credentials = AuthenticatedCredentials("coco", "secret")
    source._authenticated_username = "coco"
    result = source.get_suite(credentials, "suite-1")
    assert result == DataSourceResult.success({"id": "suite-1"})
    assert (opener.get_calls, opener.login_calls) == (2, 1)


def test_write_reauthenticates_and_replays_once_only_after_explicit_401():
    class ExpiredWrite:
        def __init__(self): self.write_calls = 0; self.login_calls = 0
        def open(self, request, timeout):
            if request.full_url.endswith("/api/auth/client-session"):
                self.login_calls += 1
                return Response(b'{"authenticated":true}')
            self.write_calls += 1
            if self.write_calls == 1:
                raise HTTPError(request.full_url, 401, "Unauthorized", {},
                                Response(b'{"detail":{"state":"unauthenticated"}}'))
            return Response(b'{"id":"suite-1","revision":2}')

    opener = ExpiredWrite()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    credentials = AuthenticatedCredentials("coco", "secret")
    source._authenticated_username = "coco"
    result = source.update_suite(credentials, "suite-1", {"revision": 1})
    assert result == DataSourceResult.success({"id": "suite-1", "revision": 2})
    assert (opener.write_calls, opener.login_calls) == (2, 1)


def test_expired_web_session_preserves_explicit_invalid_credentials_from_relogin():
    class InvalidRelogin:
        def __init__(self): self.list_calls = 0; self.login_calls = 0
        def open(self, request, timeout):
            if request.full_url.endswith("/api/auth/client-session"):
                self.login_calls += 1
                raise HTTPError(request.full_url, 401, "Unauthorized", {},
                                Response(b'{"detail":{"state":"invalid_credentials"}}'))
            self.list_calls += 1
            raise HTTPError(request.full_url, 401, "Unauthorized", {},
                            Response(b'{"detail":{"state":"unauthenticated"}}'))

    opener = InvalidRelogin()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    source._authenticated_username = "coco"
    result = source.list_suites(AuthenticatedCredentials("coco", "expired"), "mine")
    assert result.error == DataSourceError(
        "invalid_credentials", retryable=False, stage="login", http_status=401
    )
    assert (opener.list_calls, opener.login_calls) == (1, 1)


def test_web_source_discards_session_on_client_exit():
    opener = Opener()
    source = WebTestSuiteSource("https://testserver", opener=opener)
    credentials = AuthenticatedCredentials("coco", "secret")
    source.list_suites(credentials, "mine")
    source.discard_session()
    source.list_suites(credentials, "mine")
    login_urls = [request.full_url for request in opener.requests
                  if request.full_url.endswith("/api/auth/client-session")]
    assert len(login_urls) == 2


def test_web_source_lifecycle_logs_are_structured_and_secret_free(monkeypatch):
    from client.app.data_sources import web_test_suites as source_module

    records = []
    monkeypatch.setattr(source_module, "smart_log",
                        lambda message, *args, **kwargs: records.append((message, args, kwargs)))
    source = WebTestSuiteSource("http://testserver.local", opener=Opener())
    source._cookies.set_cookie(Cookie(
        version=0, name="session", value="cookie-secret", port=None,
        port_specified=False, domain="testserver.local", domain_specified=True,
        domain_initial_dot=False, path="/", path_specified=True,
        secure=True, expires=None, discard=True, comment=None,
        comment_url=None, rest={}, rfc2109=False,
    ))
    source._cookies.set_cookie(Cookie(
        version=0, name="http_session", value="http-cookie-secret", port=None,
        port_specified=False, domain="testserver.local", domain_specified=True,
        domain_initial_dot=False, path="/", path_specified=True,
        secure=False, expires=None, discard=True, comment=None,
        comment_url=None, rest={}, rfc2109=False,
    ))
    source._authenticated_username = "coco"
    source._request(
        "POST", "/api/test-suites?token=query-secret", "create",
        {"password": "payload-secret"},
    )
    extras = [record[2]["extra"] for record in records]
    assert extras[0].items() >= {
        "stage": "create", "outcome": "start", "method": "POST",
        "path": "/api/test-suites", "cookie_count": 2,
        "secure_cookie_count": 1, "secure_cookie_transport_allowed": False,
        "sendable_cookie_count": 1, "cookie_header_present": True,
    }.items()
    assert extras[-1]["http_status"] == 200
    rendered = repr(records).lower()
    assert "query-secret" not in rendered
    assert "payload-secret" not in rendered
    assert "cookie-secret" not in rendered
    assert "http-cookie-secret" not in rendered
    readable = records[0][0] % records[0][1]
    assert all(field in readable for field in (
        "method=POST", "path=/api/test-suites", "status=none",
        "error=none", "cookie_count=2", "secure_count=1",
        "transport_allowed=false", "sendable_count=1", "request_id=none",
    ))


def test_web_source_logs_explicit_401_reauthentication_and_retry_result(monkeypatch):
    from client.app.data_sources import web_test_suites as source_module

    records = []
    monkeypatch.setattr(source_module, "smart_log",
                        lambda message, *args, **kwargs: records.append((message, kwargs["extra"])))

    class ExpiredList:
        def __init__(self): self.list_calls = 0
        def open(self, request, timeout):
            if request.full_url.endswith("/api/auth/client-session"):
                return Response(b'{"authenticated":true}')
            self.list_calls += 1
            if self.list_calls == 1:
                raise HTTPError(request.full_url, 401, "Unauthorized",
                                {"x-request-id": "web-401"},
                                Response(b'{"detail":{"state":"unauthenticated"}}'))
            return Response(b'[]', headers={"x-request-id": "web-retry"})

    source = WebTestSuiteSource("https://testserver", opener=ExpiredList())
    source._authenticated_username = "coco"
    assert source.list_suites(AuthenticatedCredentials("coco", "secret"), "mine").ok
    extras = [item[1] for item in records]
    assert any(item.get("reauthentication") == "triggered" for item in extras)
    assert any(item.get("retry_outcome") == "success" for item in extras)
    assert any(item.get("request_id") == "web-401" and item.get("http_status") == 401
               for item in extras)
    assert any(item.get("request_id") == "web-retry" and item.get("http_status") == 200
               for item in extras)
    assert any("status=401" in message and "request_id=web-401" in message
               for message, _extra in records)


def test_auth_bridge_credentials_are_python_only_and_require_authenticated_session(tmp_path):
    from client.app.ui.example.bridge.AuthBridge import AuthBridge
    class Credentials:
        def read(self, _): raise KeyError
        def write(self, *_): pass
        def delete(self, *_): pass
    bridge = AuthBridge(project_root=Path(__file__).resolve().parents[4], state_root=tmp_path,
                        credential_store=Credentials())
    assert bridge.runtime_credentials() is None
    bridge._set_auth_state(username="coco", authenticated=True, password="secret",
                           display_name="Coco")
    assert bridge.runtime_credentials() == AuthenticatedCredentials("coco", "secret")
    assert bridge.metaObject().indexOfMethod("runtime_credentials()") == -1
