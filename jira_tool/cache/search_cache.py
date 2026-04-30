from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from jira_tool.core.models import IssueRecord


class JiraSearchCache:
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get_records(
        self,
        *,
        jql: str,
        spec_names: list[str],
        include_heavy: bool,
        ttl_seconds: float | None,
    ) -> list[IssueRecord] | None:
        cache_key = self._cache_key(jql=jql, spec_names=spec_names, include_heavy=include_heavy)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT created_at, payload_json FROM jira_search_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        created_at, payload_json = row
        if ttl_seconds is not None and (time.time() - float(created_at)) > ttl_seconds:
            return None
        payload = json.loads(payload_json)
        return [
            IssueRecord(
                key=item["key"],
                id=item.get("id"),
                raw=item.get("raw") or {},
                fields=item.get("fields") or {},
            )
            for item in payload
        ]

    def put_records(
        self,
        *,
        jql: str,
        spec_names: list[str],
        include_heavy: bool,
        records: list[IssueRecord],
    ) -> None:
        cache_key = self._cache_key(jql=jql, spec_names=spec_names, include_heavy=include_heavy)
        payload = json.dumps(
            [
                {
                    "key": record.key,
                    "id": record.id,
                    "raw": record.raw,
                    "fields": record.fields,
                }
                for record in records
            ],
            ensure_ascii=False,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO jira_search_cache(cache_key, created_at, payload_json)
                VALUES(?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
                """,
                (cache_key, time.time(), payload),
            )
            conn.commit()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_search_cache(
                    cache_key TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _cache_key(*, jql: str, spec_names: list[str], include_heavy: bool) -> str:
        signature = json.dumps(
            {
                "jql": jql,
                "spec_names": sorted(spec_names),
                "include_heavy": include_heavy,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(signature.encode("utf-8")).hexdigest()
