from __future__ import annotations

from dataclasses import dataclass
import json
import time

from .database import WebDatabase


@dataclass(frozen=True)
class ReleaseQuerySnapshot:
    session_hash: str
    scope: str
    filters: dict
    search: str
    project_ids: tuple[str, ...]
    release_names: tuple[str, ...]
    confluence_facts_version: str
    jira_cache_version: str
    created_at: float
    updated_at: float
    expires_at: float


class ReleaseQuerySnapshotRepository:
    scopes = frozenset(("release-dashboard", "jira-release-workbench"))

    def __init__(self, database: WebDatabase, *, now=time.time):
        self.database, self._now = database, now
        self._ensure_schema()

    def _ensure_schema(self):
        with self.database.transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS web_query_snapshots (
                session_hash TEXT NOT NULL, scope TEXT NOT NULL, filters_json TEXT NOT NULL,
                search TEXT NOT NULL, project_ids_json TEXT NOT NULL, facts_version TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL, expires_at REAL NOT NULL,
                release_names_json TEXT NOT NULL DEFAULT '[]', jira_cache_version TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(session_hash,scope))""")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(web_query_snapshots)")}
            if "release_names_json" not in columns:
                connection.execute("ALTER TABLE web_query_snapshots ADD COLUMN release_names_json TEXT NOT NULL DEFAULT '[]'")
            if "jira_cache_version" not in columns:
                connection.execute("ALTER TABLE web_query_snapshots ADD COLUMN jira_cache_version TEXT NOT NULL DEFAULT ''")

    def record(self, session_hash, scope, filters, search, project_ids, release_names,
               confluence_facts_version, jira_cache_version, *, expires_at):
        scope = self._scope(scope)
        now = self._now()
        values = (
            str(session_hash), scope, json.dumps(filters or {}, sort_keys=True), str(search or ""),
            json.dumps(list(dict.fromkeys(str(value) for value in project_ids if str(value))), separators=(",", ":")),
            str(confluence_facts_version or ""),
            json.dumps([str(value) for value in release_names], separators=(",", ":")),
            str(jira_cache_version or ""), now, now, float(expires_at),
        )
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM web_query_snapshots WHERE expires_at<=?", (now,))
            connection.execute("""INSERT INTO web_query_snapshots
                (session_hash,scope,filters_json,search,project_ids_json,facts_version,
                 release_names_json,jira_cache_version,created_at,updated_at,expires_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(session_hash,scope) DO UPDATE SET
                filters_json=excluded.filters_json,search=excluded.search,
                project_ids_json=excluded.project_ids_json,facts_version=excluded.facts_version,
                release_names_json=excluded.release_names_json,jira_cache_version=excluded.jira_cache_version,
                updated_at=excluded.updated_at,expires_at=excluded.expires_at""", values)

    def get(self, session_hash, scope):
        scope = self._scope(scope)
        with self.database.connect() as connection:
            row = connection.execute("""SELECT filters_json,search,project_ids_json,
                release_names_json,facts_version,jira_cache_version,created_at,updated_at,expires_at
                FROM web_query_snapshots WHERE session_hash=? AND scope=? AND expires_at>?""",
                (str(session_hash), scope, self._now())).fetchone()
        if row is None:
            return None
        return ReleaseQuerySnapshot(
            str(session_hash), scope, json.loads(row[0]), row[1], tuple(json.loads(row[2])),
            tuple(json.loads(row[3])), row[4], row[5], *map(float, row[6:]),
        )

    def _scope(self, scope):
        value = str(scope)
        if value not in self.scopes:
            raise ValueError("invalid release snapshot scope")
        return value
