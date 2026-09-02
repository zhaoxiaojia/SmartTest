from __future__ import annotations

from http.cookiejar import CookieJar
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

from core.logging import smart_log

from .common import AuthenticatedCredentials, DataSourceError, DataSourceResult


def web_base_url() -> str:
    return os.getenv("SMARTTEST_WEB_BASE_URL", "").strip().rstrip("/")


class WebTestSuiteSource:
    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0, opener=None):
        self._base_url = str(base_url or "").strip().rstrip("/")
        self._timeout = float(timeout_seconds)
        self._cookies = CookieJar()
        self._opener = opener or build_opener(HTTPCookieProcessor(self._cookies))
        self._authenticated_username = ""
        self._last_request_id = ""

    def _log(
        self,
        stage: str,
        outcome: str,
        *,
        method: str = "",
        path: str = "",
        http_status: int | None = None,
        error_code: str = "",
        request_id: str = "",
        reauthentication: str = "",
        retry_outcome: str = "",
    ) -> None:
        request_url = self._base_url + path if path else self._base_url
        scheme = urlsplit(request_url).scheme.lower()
        cookies = list(self._cookies)
        cookie_probe = Request(request_url) if request_url else None
        if cookie_probe is not None:
            self._cookies.add_cookie_header(cookie_probe)
        cookie_header = cookie_probe.get_header("Cookie", "") if cookie_probe is not None else ""
        sendable_cookie_count = len(cookie_header.split(";")) if cookie_header else 0
        safe_path = urlsplit(path).path if path else ""
        transport_allowed = scheme == "https"
        extra = {
            "stage": stage,
            "outcome": outcome,
            "method": method.upper(),
            "path": safe_path,
            "http_status": http_status,
            "error_code": error_code,
            "cookie_count": len(cookies),
            "secure_cookie_count": sum(1 for cookie in cookies if cookie.secure),
            "secure_cookie_transport_allowed": transport_allowed,
            "sendable_cookie_count": sendable_cookie_count,
            "cookie_header_present": bool(cookie_header),
            "request_id": request_id,
        }
        if reauthentication:
            extra["reauthentication"] = reauthentication
        if retry_outcome:
            extra["retry_outcome"] = retry_outcome
        message = (
            f"Test suite Web source stage={stage} outcome={outcome} "
            f"method={method.upper() or 'none'} path={safe_path or 'none'} "
            f"status={http_status if http_status is not None else 'none'} "
            f"error={error_code or 'none'} cookie_count={len(cookies)} "
            f"secure_count={extra['secure_cookie_count']} "
            f"transport_allowed={str(transport_allowed).lower()} "
            f"sendable_count={sendable_cookie_count} "
            f"cookie_present={str(bool(cookie_header)).lower()} "
            f"request_id={request_id or 'none'}"
        )
        smart_log(
            message,
            level="warning" if outcome == "failure" else "info",
            domain="ui",
            source="web_test_suite_source",
            extra=extra,
        )

    @staticmethod
    def _error(code: str, stage: str, *, http_status: int | None = None) -> DataSourceError:
        return DataSourceError(
            code=code,
            retryable=code in {"service_unavailable", "authentication_required"},
            stage=stage,
            http_status=http_status,
        )

    def _request(self, method: str, path: str, stage: str, payload: dict | None = None):
        self._last_request_id = ""
        self._log(stage, "start", method=method, path=path)
        if not self._base_url:
            error = self._error("service_unavailable", stage)
            self._log(stage, "failure", method=method, path=path, error_code=error.code)
            return DataSourceResult.failure(error)
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read()
                request_id = str(response.headers.get("x-request-id", "") or "").strip()
            value = json.loads(raw.decode("utf-8")) if raw else None
            http_status = getattr(response, "status", None) or 200
            self._last_request_id = request_id
            self._log(
                stage, "success", method=method, path=path,
                http_status=http_status, request_id=request_id,
            )
            return DataSourceResult.success(value)
        except HTTPError as http_error:
            http_status = http_error.code
            request_id = str(http_error.headers.get("x-request-id", "") or "").strip()
            self._last_request_id = request_id
            state = ""
            try:
                detail = json.loads(http_error.read().decode("utf-8")).get("detail", {})
                state = str(detail.get("state", ""))
            except Exception:
                pass
            aliases = {
                "unauthenticated": "authentication_required",
                "reauthentication_required": "authentication_required",
            }
            fallback = {
                401: "authentication_required",
                404: "not_found",
                409: "revision_conflict",
                422: "invalid_input",
                503: "service_unavailable",
            }
            code = aliases.get(state, state) or fallback.get(http_error.code, "service_unavailable")
        except (URLError, OSError, TimeoutError, ValueError):
            code = "service_unavailable"
            http_status = None
        error = self._error(code, stage, http_status=http_status)
        self._log(
            stage,
            "failure",
            method=method,
            path=path,
            http_status=http_status,
            error_code=error.code,
            request_id=self._last_request_id,
        )
        return DataSourceResult.failure(error)

    def _clear_session(self) -> None:
        self._authenticated_username = ""
        self._cookies.clear()

    def _ensure_session(self, credentials: AuthenticatedCredentials):
        if self._authenticated_username == credentials.username:
            return DataSourceResult.success(None)
        self._clear_session()
        result = self._request(
            "POST",
            "/api/auth/client-session",
            "login",
            {"username": credentials.username, "password": credentials.password},
        )
        if result.ok:
            self._authenticated_username = credentials.username
        return result

    def _authenticated_request(
        self,
        credentials: AuthenticatedCredentials,
        method: str,
        path: str,
        stage: str,
        payload: dict | None = None,
    ):
        session = self._ensure_session(credentials)
        if not session.ok:
            return session
        result = self._request(method, path, stage, payload)
        if result.error is None or result.error.http_status != 401:
            return result
        self._log(
            stage,
            "reauthentication",
            method=method,
            path=path,
            http_status=401,
            error_code=result.error.code,
            request_id=self._last_request_id,
            reauthentication="triggered",
        )
        self._clear_session()
        session = self._ensure_session(credentials)
        if not session.ok:
            self._log(
                stage,
                "failure",
                method=method,
                path=path,
                error_code=session.error.code if session.error else "service_unavailable",
                reauthentication="completed",
                retry_outcome="not_attempted",
            )
            return session
        retried = self._request(method, path, stage, payload)
        self._log(
            stage,
            "retry",
            method=method,
            path=path,
            http_status=retried.error.http_status if retried.error else 200,
            error_code=retried.error.code if retried.error else "",
            request_id=self._last_request_id,
            reauthentication="completed",
            retry_outcome="success" if retried.ok else "failure",
        )
        return retried

    def switch_account(self, credentials: AuthenticatedCredentials | None, scope: str):
        self.close_session()
        if credentials is None:
            return DataSourceResult.success([])
        return self.list_suites(credentials, scope)

    def close_session(self):
        result = DataSourceResult.success(None)
        if self._authenticated_username:
            result = self._request("POST", "/api/auth/logout", "logout", {})
        self._clear_session()
        return result

    def discard_session(self) -> None:
        self._clear_session()

    def list_suites(self, credentials: AuthenticatedCredentials, scope: str):
        return self._authenticated_request(
            credentials, "GET", "/api/test-suites?" + urlencode({"scope": scope}), "list"
        )

    def get_suite(self, credentials: AuthenticatedCredentials, suite_id: str):
        return self._authenticated_request(
            credentials, "GET", "/api/test-suites/" + quote(suite_id, safe=""), "get"
        )

    def create_suite(self, credentials: AuthenticatedCredentials, payload: dict):
        return self._authenticated_request(
            credentials, "POST", "/api/test-suites", "create", payload
        )

    def update_suite(self, credentials: AuthenticatedCredentials, suite_id: str, payload: dict):
        return self._authenticated_request(
            credentials,
            "PUT",
            "/api/test-suites/" + quote(suite_id, safe=""),
            "update",
            payload,
        )

    def delete_suite(self, credentials: AuthenticatedCredentials, suite_id: str):
        return self._authenticated_request(
            credentials, "DELETE", "/api/test-suites/" + quote(suite_id, safe=""), "delete"
        )

    def copy_suite(self, credentials: AuthenticatedCredentials, suite_id: str, payload: dict):
        return self._authenticated_request(
            credentials,
            "POST",
            "/api/test-suites/" + quote(suite_id, safe="") + "/copy",
            "copy",
            payload,
        )
