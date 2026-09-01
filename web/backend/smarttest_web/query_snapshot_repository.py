from __future__ import annotations

from dataclasses import dataclass
import json
import time

from .database import WebDatabase


@dataclass(frozen=True)
class ConfluenceQuerySnapshot:
    session_hash: str
    scope: str
    filters: dict
    search: str
    project_ids: tuple[str, ...]
    facts_version: str
    created_at: float
    updated_at: float
    expires_at: float


class ConfluenceQuerySnapshotRepository:
    scope = "confluence-project-facts"

    def __init__(self, database: WebDatabase, *, now=time.time):
        self.database, self._now = database, now

    def record(self, session_hash, filters, search, project_ids, facts_version, *, expires_at):
        now = self._now()
        values = (str(session_hash), self.scope, json.dumps(filters or {}, sort_keys=True), str(search or ""),
                  json.dumps(list(dict.fromkeys(str(value) for value in project_ids if str(value))), separators=(",", ":")),
                  str(facts_version or ""), now, now, float(expires_at))
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM web_query_snapshots WHERE expires_at<=?", (now,))
            connection.execute("""INSERT INTO web_query_snapshots
                (session_hash,scope,filters_json,search,project_ids_json,facts_version,created_at,updated_at,expires_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_hash,scope) DO UPDATE SET filters_json=excluded.filters_json,search=excluded.search,
                project_ids_json=excluded.project_ids_json,facts_version=excluded.facts_version,updated_at=excluded.updated_at,expires_at=excluded.expires_at""", values)

    def get(self, session_hash, *, expires_at=None):
        now = self._now() if expires_at is None else float(expires_at)
        with self.database.connect() as connection:
            row = connection.execute("""SELECT filters_json,search,project_ids_json,facts_version,created_at,updated_at,expires_at
                FROM web_query_snapshots WHERE session_hash=? AND scope=? AND expires_at>?""",
                (str(session_hash), self.scope, now)).fetchone()
        if row is None:
            return None
        return ConfluenceQuerySnapshot(str(session_hash), self.scope, json.loads(row[0]), row[1],
                                       tuple(json.loads(row[2])), row[3], *map(float, row[4:]))

    def delete_session(self, session_hash):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM web_query_snapshots WHERE session_hash=?", (str(session_hash),))

    def cleanup(self):
        with self.database.transaction() as connection:
            return connection.execute("DELETE FROM web_query_snapshots WHERE expires_at<=?", (self._now(),)).rowcount
