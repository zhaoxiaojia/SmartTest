from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
import json
from math import ceil
from pathlib import Path
import ssl
from threading import local
import time
from typing import Any, Iterable
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPSHandler, Request, build_opener

from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.core.errors import JiraConfigurationError, JiraRequestError
from support.jira_integration.core.models import (
    AttachmentCancellation,
    CreateIssueAttachment,
    JiraAttachmentMetadata,
    JiraFieldMetadata,
    SearchPage,
)


@dataclass(frozen=True)
class JiraClientConfig:
    base_url: str
    api_version: str = "2"
    timeout_seconds: float = 30.0
    page_size: int = 100
    max_workers: int = 8
    verify_ssl: bool = True


class JiraClient:
    def __init__(self, config: JiraClientConfig, auth: JiraBasicAuth):
        if not config.base_url.strip():
            raise JiraConfigurationError("Jira base URL cannot be empty")
        if config.page_size <= 0:
            raise JiraConfigurationError("page_size must be positive")
        if config.max_workers <= 0:
            raise JiraConfigurationError("max_workers must be positive")
        self._config = config
        self._auth = auth
        self._thread_local = local()

    @property
    def config(self) -> JiraClientConfig:
        return self._config

    def search_page(
        self,
        jql: str,
        *,
        start_at: int = 0,
        max_results: int | None = None,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
        validate_query: str = "strict",
        use_post: bool = True,
    ) -> SearchPage:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results or self._config.page_size,
        }
        normalized_validate_query = self._normalize_validate_query(validate_query, use_post=use_post)
        if normalized_validate_query is not None:
            payload["validateQuery"] = normalized_validate_query
        if fields:
            payload["fields"] = fields
        if expand:
            payload["expand"] = expand

        response = self._request(
            "POST" if use_post else "GET",
            self._api_path("search"),
            json=payload if use_post else None,
            params=payload if not use_post else None,
        )
        data = response.data if isinstance(response.data, dict) else {}
        issues = list(data.get("issues") or [])
        start = int(data.get("startAt", start_at))
        max_size = int(data.get("maxResults", payload["maxResults"]))
        total = int(data.get("total", len(issues)))
        return SearchPage(
            issues=issues,
            start_at=start,
            max_results=max_size,
            total=total,
            is_last=(start + len(issues)) >= total,
        )

    def search_all(
        self,
        jql: str,
        *,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
        page_size: int | None = None,
        max_workers: int | None = None,
        max_total_results: int | None = None,
    ) -> list[dict[str, Any]]:
        effective_page_size = page_size or self._config.page_size
        if max_total_results is not None:
            effective_page_size = min(effective_page_size, max_total_results)
        first_page = self.search_page(
            jql,
            start_at=0,
            max_results=effective_page_size,
            fields=fields,
            expand=expand,
        )
        target_total = first_page.total
        if max_total_results is not None:
            target_total = min(target_total, max_total_results)
        _trace_request(
            "search_all_plan",
            first_count=len(first_page.issues),
            jql=jql,
            page_size=effective_page_size,
            target_total=target_total,
            total=first_page.total,
        )
        if target_total <= len(first_page.issues):
            return first_page.issues[:target_total]

        effective_page_size = first_page.max_results or effective_page_size
        total_pages = ceil(target_total / effective_page_size)
        starts = [page_index * effective_page_size for page_index in range(1, total_pages)]
        workers = min(max_workers or self._config.max_workers, len(starts)) or 1

        pages_by_start: dict[int, SearchPage] = {first_page.start_at: first_page}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    self.search_page,
                    jql,
                    start_at=start_at,
                    max_results=effective_page_size,
                    fields=fields,
                    expand=expand,
                )
                for start_at in starts
            ]
            for future in futures:
                page = future.result()
                pages_by_start[page.start_at] = page

        issues: list[dict[str, Any]] = []
        for start_at in sorted(pages_by_start):
            issues.extend(pages_by_start[start_at].issues)
        return issues[:target_total]

    def fetch_issue(
        self,
        issue_key: str,
        *,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = ",".join(expand)
        response = self._request("GET", self._api_path(f"issue/{issue_key}"), params=params or None)
        return response.data

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", self._api_path("issue"), json=payload)
        data = response.data
        return data if isinstance(data, dict) else {}

    def list_attachments(self, issue_key: str) -> list[dict[str, Any]]:
        issue = self.fetch_issue(issue_key, fields=["attachment"])
        fields = issue.get("fields") if isinstance(issue, dict) else {}
        attachments = fields.get("attachment") if isinstance(fields, dict) else []
        return [item for item in attachments or [] if isinstance(item, dict)]

    def attachment_metadata(self) -> JiraAttachmentMetadata:
        response = self._request("GET", self._api_path("attachment/meta"))
        payload = response.data if isinstance(response.data, dict) else {}
        enabled = payload.get("enabled")
        upload_limit = payload.get("uploadLimit")
        return JiraAttachmentMetadata(
            available=True,
            enabled=enabled if isinstance(enabled, bool) else None,
            upload_limit=(
                int(upload_limit)
                if isinstance(upload_limit, int) and not isinstance(upload_limit, bool)
                else None
            ),
        )

    def upload_attachment(
        self,
        issue_key: str,
        attachment: CreateIssueAttachment,
        *,
        cancellation: AttachmentCancellation | None = None,
    ) -> dict[str, Any]:
        boundary = f"SmartTest-{uuid4().hex}"
        filename = attachment.upload_filename.replace("\\", "\\\\").replace('"', '\\"')
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        body = _MultipartFileBody(
            attachment.path,
            prefix,
            suffix,
            cancellation=cancellation,
        )
        response = self._request(
            "POST",
            self._api_path(f"issue/{issue_key}/attachments"),
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(prefix) + attachment.size + len(suffix)),
                "X-Atlassian-Token": "no-check",
            },
        )
        payload = response.data
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        return payload if isinstance(payload, dict) else {}

    def fetch_create_metadata(self, project_key: str, issue_type: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            self._api_path("issue/createmeta"),
            params={
                "projectKeys": project_key,
                "issuetypeNames": issue_type,
                "expand": "projects.issuetypes.fields",
            },
        )
        return response.data if isinstance(response.data, dict) else {}

    def search_users(
        self,
        query: str,
        *,
        project_key: str = "SH",
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            self._api_path("user/assignable/search"),
            params={"project": project_key, "username": query},
        )
        users = response.data if isinstance(response.data, list) else []
        return [_public_user(item) for item in users if isinstance(item, dict)]

    def current_user(self) -> dict[str, str]:
        response = self._request("GET", self._api_path("myself"))
        payload = response.data if isinstance(response.data, dict) else {}
        return _public_user(payload)

    def fetch_fields_metadata(self) -> list[JiraFieldMetadata]:
        response = self._request("GET", self._api_path("field"))
        payload = response.data if isinstance(response.data, list) else []
        return [
            JiraFieldMetadata(
                field_id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                schema_type=(item.get("schema") or {}).get("type"),
                schema_items=(item.get("schema") or {}).get("items"),
                custom=bool(item.get("custom", False)),
                custom_id=item.get("customId"),
                schema_custom=(item.get("schema") or {}).get("custom"),
                clause_names=tuple(item.get("clauseNames") or ()),
                navigable=bool(item.get("navigable", True)),
                searchable=bool(item.get("searchable", True)),
            )
            for item in payload
        ]

    def fetch_favourite_filters(self) -> list[dict[str, Any]]:
        response = self._request("GET", self._api_path("filter/favourite"))
        payload = response.data if isinstance(response.data, list) else []
        return [item for item in payload if isinstance(item, dict)]

    def _api_path(self, suffix: str) -> str:
        base = self._config.base_url.rstrip("/") + "/"
        return urljoin(base, f"rest/api/{self._config.api_version}/{suffix.lstrip('/')}")

    def _opener(self):
        opener = getattr(self._thread_local, "opener", None)
        if opener is None:
            context = None
            if not self._config.verify_ssl:
                context = ssl._create_unverified_context()
            opener = build_opener(HTTPSHandler(context=context))
            self._thread_local.opener = opener
        return opener

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: bytes | Iterable[bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> "_HttpResponse":
        started_at = time.monotonic()
        if params:
            query = urlencode(self._normalize_params(params), doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        body = data
        request_headers = {
            "Accept": "application/json",
            "Authorization": self._auth.authorization_header(),
        }
        request_headers.update(headers or {})
        if json is not None:
            body = self._encode_json(json)
            request_headers["Content-Type"] = "application/json"

        request = Request(url=url, data=body, method=method.upper(), headers=request_headers)
        opener = self._opener()
        _trace_request("request_start", method=method.upper(), url=url)
        try:
            with opener.open(request, timeout=self._config.timeout_seconds) as response:
                raw_body = response.read()
                text = raw_body.decode("utf-8", errors="replace")
                payload = json_loads(text) if text else None
                _trace_request(
                    "request_done",
                    method=method.upper(),
                    url=url,
                    status=int(response.status),
                    elapsed_ms=int((time.monotonic() - started_at) * 1000),
                )
                return _HttpResponse(status_code=int(response.status), text=text, data=payload)
        except HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            _trace_request(
                "request_http_error",
                method=method.upper(),
                url=url,
                status=exc.code,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            raise JiraRequestError(
                f"Jira request failed: {method} {url} -> {exc.code} {text[:400]}"
            ) from exc
        except URLError as exc:
            _trace_request(
                "request_url_error",
                method=method.upper(),
                url=url,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
            )
            raise JiraRequestError(f"Jira request failed: {method} {url} -> {exc.reason}") from exc

    @staticmethod
    def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                normalized[key] = [str(item) for item in value]
                continue
            normalized[key] = str(value)
        return normalized

    @staticmethod
    def _normalize_validate_query(value: str | bool | None, *, use_post: bool) -> bool | str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value if use_post else str(value).lower()

        normalized = str(value).strip().lower()
        if normalized == "":
            return None
        if use_post:
            if normalized in {"false", "0", "off", "no", "none"}:
                return False
            return True
        if normalized in {"true", "false", "warn", "strict"}:
            return normalized
        return "strict"

    @staticmethod
    def _encode_json(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class _HttpResponse:
    status_code: int
    text: str
    data: Any


class _MultipartFileBody:
    def __init__(
        self,
        path: Path,
        prefix: bytes,
        suffix: bytes,
        *,
        chunk_size: int = 64 * 1024,
        cancellation: AttachmentCancellation | None = None,
    ):
        self._path = path
        self._prefix = prefix
        self._suffix = suffix
        self._chunk_size = chunk_size
        self._cancellation = cancellation

    def __iter__(self):
        self._raise_if_cancelled()
        yield self._prefix
        with self._path.open("rb") as source:
            while True:
                self._raise_if_cancelled()
                chunk = source.read(self._chunk_size)
                if not chunk:
                    break
                yield chunk
        self._raise_if_cancelled()
        yield self._suffix

    def _raise_if_cancelled(self) -> None:
        if self._cancellation is not None:
            self._cancellation.raise_if_cancelled()


def json_loads(text: str) -> Any:
    if text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - depends on remote payload
        raise JiraRequestError(f"Jira returned invalid JSON: {text[:200]}") from exc


def _public_user(payload: dict[str, Any]) -> dict[str, str]:
    avatars = payload.get("avatarUrls") or {}
    avatar_url = ""
    if isinstance(avatars, dict):
        avatar_url = str(
            avatars.get("48x48")
            or avatars.get("32x32")
            or avatars.get("24x24")
            or avatars.get("16x16")
            or ""
        )
    return {
        "account": str(payload.get("name") or payload.get("accountId") or payload.get("key") or ""),
        "display_name": str(payload.get("displayName") or ""),
        "avatar_url": avatar_url,
    }


def _trace_request(stage: str, **values: Any) -> None:
    details = " ".join(f"{key}={values[key]}" for key in sorted(values))


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
