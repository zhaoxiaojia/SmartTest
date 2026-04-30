from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from jira_tool.cache.issue_store import JiraIssueStore
from jira_tool.core.models import JiraSyncResult
from jira_tool.fields.specs import FieldSpec
from jira_tool.services.issue_service import JiraIssueService


class JiraSyncService:
    def __init__(self, issue_service: JiraIssueService, issue_store: JiraIssueStore):
        self._issue_service = issue_service
        self._issue_store = issue_store

    def sync_scope(
        self,
        *,
        scope_key: str,
        jql: str,
        specs: Iterable[str | FieldSpec],
        include_heavy: bool = False,
        force_full: bool = False,
        overlap_minutes: int = 5,
        page_size: int | None = None,
        max_workers: int | None = None,
    ) -> JiraSyncResult:
        requested_specs = list(specs)
        if not _contains_updated_spec(requested_specs):
            requested_specs.append("updated")

        previous_state = None if force_full else self._issue_store.get_sync_state(scope_key)
        previous_cursor = previous_state.cursor_updated if previous_state is not None else None
        effective_jql = (
            jql
            if previous_cursor is None
            else build_incremental_jql(jql, previous_cursor, overlap_minutes=overlap_minutes)
        )

        records = self._issue_service.search_records(
            effective_jql,
            specs=requested_specs,
            include_heavy=include_heavy,
            page_size=page_size,
            max_workers=max_workers,
        )
        stored_count = self._issue_store.upsert_records(records)
        next_cursor = _max_updated_cursor(records) or previous_cursor
        self._issue_store.set_sync_state(
            scope_key,
            cursor_updated=next_cursor,
            base_jql=jql,
            extra={"include_heavy": include_heavy, "overlap_minutes": overlap_minutes},
        )
        return JiraSyncResult(
            scope_key=scope_key,
            effective_jql=effective_jql,
            fetched_count=len(records),
            stored_count=stored_count,
            previous_cursor=previous_cursor,
            next_cursor=next_cursor,
            full_sync=previous_cursor is None,
        )


def build_incremental_jql(base_jql: str, cursor_updated: str, *, overlap_minutes: int = 5) -> str:
    overlap_dt = parse_jira_datetime(cursor_updated) - timedelta(minutes=max(overlap_minutes, 0))
    formatted = overlap_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return f"({base_jql}) AND updated >= '{formatted}'"


def parse_jira_datetime(value: str) -> datetime:
    formats = ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported Jira datetime format: {value}")


def _contains_updated_spec(specs: list[str | FieldSpec]) -> bool:
    for spec in specs:
        if isinstance(spec, FieldSpec):
            if spec.name == "updated" or spec.path == "fields.updated":
                return True
            continue
        if str(spec).strip().lower() == "updated":
            return True
    return False


def _max_updated_cursor(records) -> str | None:
    cursor = None
    cursor_dt = None
    for record in records:
        updated = record.fields.get("updated")
        if not isinstance(updated, str) or updated.strip() == "":
            continue
        current_dt = parse_jira_datetime(updated)
        if cursor_dt is None or current_dt > cursor_dt:
            cursor_dt = current_dt
            cursor = updated
    return cursor
