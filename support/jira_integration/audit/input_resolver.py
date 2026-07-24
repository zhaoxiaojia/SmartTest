from __future__ import annotations

import re
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from .models import ResolvedAuditInput


_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


class _ResolverClient(Protocol):
    def fetch_filter(self, filter_id: str) -> dict: ...

    def search_page(self, jql: str, **kwargs): ...


def resolve_audit_input(
    text: str,
    *,
    base_url: str,
    client: _ResolverClient,
) -> ResolvedAuditInput:
    original = str(text or "").strip()
    if not original:
        raise ValueError("请输入 JQL 或 Jira URL。")

    if _URL_SCHEME.match(original):
        resolved = _resolve_url(original, base_url=base_url, client=client)
    else:
        resolved = ResolvedAuditInput("jql", original, original)

    try:
        client.search_page(resolved.jql, start_at=0, max_results=1, validate_query="strict")
    except Exception as exc:
        raise ValueError("JQL validation failed. Check the query and Jira permissions.") from exc
    return resolved


def _resolve_url(
    original: str,
    *,
    base_url: str,
    client: _ResolverClient,
) -> ResolvedAuditInput:
    parsed = urlsplit(original)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise ValueError("Jira URLs must use HTTP or HTTPS.")
    base = urlsplit(str(base_url or "").strip())
    if not parsed.hostname or not base.hostname:
        raise ValueError("The Jira URL is malformed.")
    if str(parsed.hostname).casefold() != str(base.hostname).casefold():
        raise ValueError("The Jira URL host must match the configured Jira host.")

    query = parse_qs(parsed.query, keep_blank_values=True)
    jql_values = query.get("jql") or []
    if jql_values and str(jql_values[0] or "").strip():
        return ResolvedAuditInput("jql_url", original, str(jql_values[0]).strip())

    browse_match = re.fullmatch(r"/browse/([^/]+)/?", parsed.path)
    if browse_match:
        key = browse_match.group(1).strip()
        if not _ISSUE_KEY.fullmatch(key):
            raise ValueError("The Jira issue URL contains an invalid issue key.")
        return ResolvedAuditInput("issue_url", original, f'key = "{key}"')

    filter_id = _filter_id(parsed.path, query)
    if filter_id:
        try:
            payload = client.fetch_filter(filter_id)
        except Exception as exc:
            raise ValueError("The Jira filter could not be loaded. Check its permissions.") from exc
        jql = str((payload or {}).get("jql", "") or "").strip()
        if not jql:
            raise ValueError("The Jira filter does not contain JQL.")
        return ResolvedAuditInput("filter_url", original, jql)

    raise ValueError("Use a Jira issue, filter, or search URL.")


def _filter_id(path: str, query: dict[str, list[str]]) -> str:
    values = query.get("filter") or []
    candidate = str(values[0] or "").strip() if values else ""
    if not candidate:
        match = re.fullmatch(r"/filter/(\d+)/?", path)
        candidate = match.group(1) if match else ""
    return candidate if candidate.isdigit() else ""
