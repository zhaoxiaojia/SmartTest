from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from jira_tool.core.models import JiraFieldMetadata


class JiraFieldMetadataCache:
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get(self, *, base_url: str, ttl_seconds: float | None = None) -> list[JiraFieldMetadata] | None:
        normalized_base_url = _normalize_base_url(base_url)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT created_at, payload_json FROM jira_field_metadata_cache WHERE base_url = ?",
                (normalized_base_url,),
            ).fetchone()
        if row is None:
            return None
        created_at, payload_json = row
        if ttl_seconds is not None and (time.time() - float(created_at)) > ttl_seconds:
            return None
        payload = json.loads(payload_json)
        return [JiraFieldMetadata.from_dict(item) for item in payload]

    def put(self, *, base_url: str, metadata_items: list[JiraFieldMetadata]) -> None:
        normalized_base_url = _normalize_base_url(base_url)
        payload = json.dumps([item.to_dict() for item in metadata_items], ensure_ascii=False)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO jira_field_metadata_cache(base_url, created_at, payload_json)
                VALUES(?, ?, ?)
                ON CONFLICT(base_url) DO UPDATE SET
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
                """,
                (normalized_base_url, time.time(), payload),
            )
            conn.commit()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_field_metadata_cache(
                    base_url TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()


def _normalize_base_url(base_url: str) -> str:
    return (base_url or "").strip().rstrip("/").lower()
