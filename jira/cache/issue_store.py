from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from jira.core.models import IssueRecord, IssueStoreQuery, JiraSyncState


class JiraIssueStore:
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_records(self, records: list[IssueRecord]) -> int:
        if not records:
            return 0
        now = time.time()
        payload = [
            (
                record.key,
                record.id,
                _record_updated(record),
                _summary_value(record),
                _summary_value(record).lower(),
                _status_value(record),
                _assignee_value(record),
                _priority_value(record),
                now,
                json.dumps(record.raw, ensure_ascii=False),
                json.dumps(record.fields, ensure_ascii=False),
            )
            for record in records
        ]
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO jira_issue_store(
                    issue_key,
                    issue_id,
                    updated_at,
                    summary_text,
                    summary_text_lc,
                    status_name,
                    assignee_name,
                    priority_name,
                    synced_at,
                    raw_json,
                    fields_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_key) DO UPDATE SET
                    issue_id = excluded.issue_id,
                    updated_at = excluded.updated_at,
                    summary_text = excluded.summary_text,
                    summary_text_lc = excluded.summary_text_lc,
                    status_name = excluded.status_name,
                    assignee_name = excluded.assignee_name,
                    priority_name = excluded.priority_name,
                    synced_at = excluded.synced_at,
                    raw_json = excluded.raw_json,
                    fields_json = excluded.fields_json
                """,
                payload,
            )
            conn.commit()
        return len(records)

    def get_record(self, issue_key: str) -> IssueRecord | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT issue_key, issue_id, raw_json, fields_json
                FROM jira_issue_store
                WHERE issue_key = ?
                """,
                (issue_key,),
            ).fetchone()
        return _row_to_record(row)

    def list_records(self, *, limit: int | None = None, updated_since: str | None = None) -> list[IssueRecord]:
        return self.query_records(IssueStoreQuery(limit=limit, updated_since=updated_since))

    def query_records(self, query: IssueStoreQuery) -> list[IssueRecord]:
        sql = """
            SELECT issue_key, issue_id, raw_json, fields_json
            FROM jira_issue_store
        """
        params: list[Any] = []
        conditions: list[str] = []
        if query.updated_since:
            conditions.append("updated_at >= ?")
            params.append(query.updated_since)
        if query.issue_keys:
            placeholders = ",".join("?" for _ in query.issue_keys)
            conditions.append(f"issue_key IN ({placeholders})")
            params.extend(query.issue_keys)
        if query.statuses:
            placeholders = ",".join("?" for _ in query.statuses)
            conditions.append(f"status_name IN ({placeholders})")
            params.extend(query.statuses)
        if query.assignees:
            placeholders = ",".join("?" for _ in query.assignees)
            conditions.append(f"assignee_name IN ({placeholders})")
            params.extend(query.assignees)
        if query.priorities:
            placeholders = ",".join("?" for _ in query.priorities)
            conditions.append(f"priority_name IN ({placeholders})")
            params.extend(query.priorities)
        if query.text and query.text.strip():
            conditions.append("summary_text_lc LIKE ?")
            params.append(f"%{query.text.strip().lower()}%")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY updated_at DESC, issue_key ASC"
        if query.limit is not None:
            sql += " LIMIT ?"
            params.append(query.limit)

        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_record(row) for row in rows if row is not None]

    def get_sync_state(self, scope_key: str) -> JiraSyncState | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT scope_key, cursor_updated, synced_at, base_jql, extra_json
                FROM jira_sync_state
                WHERE scope_key = ?
                """,
                (scope_key,),
            ).fetchone()
        if row is None:
            return None
        return JiraSyncState(
            scope_key=row[0],
            cursor_updated=row[1],
            synced_at=row[2],
            base_jql=row[3],
            extra=json.loads(row[4]) if row[4] else {},
        )

    def set_sync_state(
        self,
        scope_key: str,
        *,
        cursor_updated: str | None,
        base_jql: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO jira_sync_state(scope_key, cursor_updated, synced_at, base_jql, extra_json)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(scope_key) DO UPDATE SET
                    cursor_updated = excluded.cursor_updated,
                    synced_at = excluded.synced_at,
                    base_jql = excluded.base_jql,
                    extra_json = excluded.extra_json
                """,
                (
                    scope_key,
                    cursor_updated,
                    time.time(),
                    base_jql,
                    json.dumps(extra or {}, ensure_ascii=False),
                ),
            )
            conn.commit()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_issue_store(
                    issue_key TEXT PRIMARY KEY,
                    issue_id TEXT,
                    updated_at TEXT,
                    summary_text TEXT NOT NULL DEFAULT '',
                    summary_text_lc TEXT NOT NULL DEFAULT '',
                    status_name TEXT,
                    assignee_name TEXT,
                    priority_name TEXT,
                    synced_at REAL NOT NULL,
                    raw_json TEXT NOT NULL,
                    fields_json TEXT NOT NULL
                )
                """
            )
            _ensure_issue_store_columns(conn)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jira_issue_store_updated_at
                ON jira_issue_store(updated_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jira_issue_store_status_name
                ON jira_issue_store(status_name)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jira_issue_store_assignee_name
                ON jira_issue_store(assignee_name)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jira_issue_store_priority_name
                ON jira_issue_store(priority_name)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jira_issue_store_summary_text_lc
                ON jira_issue_store(summary_text_lc)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_sync_state(
                    scope_key TEXT PRIMARY KEY,
                    cursor_updated TEXT,
                    synced_at REAL NOT NULL,
                    base_jql TEXT,
                    extra_json TEXT NOT NULL
                )
                """
            )
            conn.commit()


def _record_updated(record: IssueRecord) -> str | None:
    value = record.fields.get("updated")
    return value if isinstance(value, str) and value.strip() else None


def _summary_value(record: IssueRecord) -> str:
    value = record.fields.get("summary")
    return value.strip() if isinstance(value, str) else ""


def _status_value(record: IssueRecord) -> str | None:
    value = record.fields.get("status")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _assignee_value(record: IssueRecord) -> str | None:
    value = record.fields.get("assignee")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _priority_value(record: IssueRecord) -> str | None:
    value = record.fields.get("priority")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _ensure_issue_store_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(jira_issue_store)").fetchall()
    existing_columns = {row[1] for row in rows}
    required_columns = {
        "summary_text": "ALTER TABLE jira_issue_store ADD COLUMN summary_text TEXT NOT NULL DEFAULT ''",
        "summary_text_lc": "ALTER TABLE jira_issue_store ADD COLUMN summary_text_lc TEXT NOT NULL DEFAULT ''",
        "status_name": "ALTER TABLE jira_issue_store ADD COLUMN status_name TEXT",
        "assignee_name": "ALTER TABLE jira_issue_store ADD COLUMN assignee_name TEXT",
        "priority_name": "ALTER TABLE jira_issue_store ADD COLUMN priority_name TEXT",
    }
    for column_name, ddl in required_columns.items():
        if column_name not in existing_columns:
            conn.execute(ddl)


def _row_to_record(row: tuple[Any, ...] | None) -> IssueRecord | None:
    if row is None:
        return None
    return IssueRecord(
        key=row[0],
        id=row[1],
        raw=json.loads(row[2]) if row[2] else {},
        fields=json.loads(row[3]) if row[3] else {},
    )
