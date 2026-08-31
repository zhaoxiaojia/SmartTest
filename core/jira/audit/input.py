from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

from .models import JiraAuditScope


_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def resolve_audit_input(
    text: str,
    *,
    base_url: str,
    fetch_filter: Callable[[str], dict],
    validate_jql: Callable[[str], None],
) -> JiraAuditScope:
    original = str(text or "").strip()
    if not original:
        raise ValueError("invalid_input")
    if _URL.match(original):
        resolved = _resolve_url(original, base_url, fetch_filter)
    elif original.isdigit():
        resolved = _resolve_filter(original, original, "filter_id", fetch_filter)
    else:
        resolved = JiraAuditScope("jql", original, original)
    try:
        validate_jql(resolved.jql)
    except Exception as exc:
        raise ValueError("invalid_input") from exc
    return resolved


def _resolve_url(original: str, base_url: str, fetch_filter) -> JiraAuditScope:
    parsed, configured = urlsplit(original), urlsplit(str(base_url or "").strip())
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or not configured.hostname
    ):
        raise ValueError("invalid_input")
    if parsed.hostname.casefold() != configured.hostname.casefold():
        raise ValueError("jira host does not match configured host")
    query = parse_qs(parsed.query, keep_blank_values=True)
    jql = str((query.get("jql") or [""])[0] or "").strip()
    if jql:
        return JiraAuditScope("jql_url", original, jql)
    browse = re.fullmatch(r"/browse/([^/]+)/?", parsed.path)
    if browse:
        key = browse.group(1).strip()
        if not _ISSUE_KEY.fullmatch(key):
            raise ValueError("invalid_input")
        return JiraAuditScope("issue_url", original, f'key = "{key}"')
    filter_id = str((query.get("filter") or [""])[0] or "").strip()
    path_filter = re.fullmatch(r"/filter/(\d+)/?", parsed.path)
    filter_id = filter_id or (path_filter.group(1) if path_filter else "")
    if not filter_id.isdigit():
        raise ValueError("invalid_input")
    return _resolve_filter(filter_id, original, "filter_url", fetch_filter)


def _resolve_filter(filter_id, original, source_kind, fetch_filter):
    try:
        jql = str((fetch_filter(filter_id) or {}).get("jql") or "").strip()
    except Exception as exc:
        raise ValueError("invalid_input") from exc
    if not jql:
        raise ValueError("invalid_input")
    return JiraAuditScope(source_kind, original, jql)
