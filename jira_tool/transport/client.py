from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
import json
from math import ceil
import ssl
from threading import local
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPSHandler, Request, build_opener

from jira_tool.auth.basic import JiraBasicAuth
from jira_tool.core.errors import JiraConfigurationError, JiraRequestError
from jira_tool.core.models import JiraFieldMetadata, SearchPage


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
    ) -> "_HttpResponse":
        started_at = time.monotonic()
        if params:
            query = urlencode(self._normalize_params(params), doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": self._auth.authorization_header(),
        }
        if json is not None:
            body = self._encode_json(json)
            headers["Content-Type"] = "application/json"

        request = Request(url=url, data=body, method=method.upper(), headers=headers)
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


def json_loads(text: str) -> Any:
    if text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - depends on remote payload
        raise JiraRequestError(f"Jira returned invalid JSON: {text[:200]}") from exc


def _trace_request(stage: str, **values: Any) -> None:
    details = " ".join(f"{key}={values[key]}" for key in sorted(values))
    print(f"{_trace_timestamp()} [JIRA_HTTP] {stage} {details}".rstrip())


def _trace_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
