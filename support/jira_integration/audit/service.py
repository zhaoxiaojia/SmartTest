from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from .models import AuditReport, ResolvedAuditInput
from .rules import active_rules, audit_issue


_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
_FIELDS = ("summary", "description", "reporter", "components", "labels", "attachment")


class _AuditClient(Protocol):
    def fetch_filter(self, filter_id: str) -> dict: ...
    def search_page(self, jql: str, **kwargs): ...


def resolve_audit_input(
    text: str, *, base_url: str, client: _AuditClient
) -> ResolvedAuditInput:
    original = str(text or "").strip()
    if not original:
        raise ValueError("请输入 JQL 或 Jira URL。")
    resolved = (
        _resolve_url(original, base_url, client)
        if _URL.match(original)
        else ResolvedAuditInput("jql", original, original)
    )
    try:
        client.search_page(
            resolved.jql,
            start_at=0,
            max_results=1,
            validate_query="strict",
        )
    except Exception as exc:
        raise ValueError(
            "JQL validation failed. Check the query and Jira permissions."
        ) from exc
    return resolved


def _resolve_url(
    original: str, base_url: str, client: _AuditClient
) -> ResolvedAuditInput:
    parsed, base = urlsplit(original), urlsplit(str(base_url or "").strip())
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise ValueError("Jira URLs must use HTTP or HTTPS.")
    if not parsed.hostname or not base.hostname:
        raise ValueError("The Jira URL is malformed.")
    if parsed.hostname.casefold() != base.hostname.casefold():
        raise ValueError("The Jira URL host must match the configured Jira host.")

    query = parse_qs(parsed.query, keep_blank_values=True)
    jql = str((query.get("jql") or [""])[0] or "").strip()
    if jql:
        return ResolvedAuditInput("jql_url", original, jql)

    browse = re.fullmatch(r"/browse/([^/]+)/?", parsed.path)
    if browse:
        key = browse.group(1).strip()
        if not _ISSUE_KEY.fullmatch(key):
            raise ValueError("The Jira issue URL contains an invalid issue key.")
        return ResolvedAuditInput("issue_url", original, f'key = "{key}"')

    filter_id = str((query.get("filter") or [""])[0] or "").strip()
    path_filter = re.fullmatch(r"/filter/(\d+)/?", parsed.path)
    filter_id = filter_id or (path_filter.group(1) if path_filter else "")
    if filter_id.isdigit():
        try:
            payload = client.fetch_filter(filter_id)
        except Exception as exc:
            raise ValueError(
                "The Jira filter could not be loaded. Check its permissions."
            ) from exc
        jql = str((payload or {}).get("jql", "") or "").strip()
        if not jql:
            raise ValueError("The Jira filter does not contain JQL.")
        return ResolvedAuditInput("filter_url", original, jql)
    raise ValueError("Use a Jira issue, filter, or search URL.")


class JiraAuditService:
    def __init__(self, client: _AuditClient, *, base_url: str):
        self._client = client
        self._base_url = str(base_url or "").rstrip("/")

    def run(
        self, resolved: ResolvedAuditInput, progress: Callable[[str, int, int], None]
    ) -> AuditReport:
        raw_issues = []
        start_at = 0
        while True:
            page = self._client.search_page(
                resolved.jql,
                start_at=start_at,
                fields=_FIELDS,
                validate_query="strict",
            )
            raw_issues.extend(page.issues)
            progress("fetching", len(raw_issues), page.total)
            if page.is_last or not page.issues or len(raw_issues) >= page.total:
                break
            start_at = page.start_at + len(page.issues)

        results = []
        for index, issue in enumerate(raw_issues, 1):
            results.append(audit_issue(issue, base_url=self._base_url))
            progress("auditing", index, len(raw_issues))
        return AuditReport(
            resolved,
            datetime.now(),
            active_rules(),
            tuple(results),
        )
