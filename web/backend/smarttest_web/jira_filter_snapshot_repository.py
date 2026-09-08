from __future__ import annotations

from dataclasses import dataclass
import json
import time

from .database import WebDatabase
from .jira.schema import initialize_jira_schema


JIRA_FILTER_FIELDS = ("project", "type", "status", "currentUser", "resolution")


@dataclass(frozen=True)
class JiraFilterSnapshot:
    session_hash: str
    scope: str
    filters: dict
    jql: str
    revision: float
    expires_at: float


class JiraFilterSnapshotRepository:
    scope = "jira-global-filter"

    def __init__(self, database: WebDatabase, *, now=time.time):
        self.database, self._now = database, now
        initialize_jira_schema(database)

    def record(self, session_hash, filters, jql, *, expires_at):
        normalized = {
            key: list(dict.fromkeys(str(value).strip() for value in filters.get(key, ()) if str(value).strip()))
            for key in JIRA_FILTER_FIELDS if filters.get(key)
        }
        now = self._now()
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM web_query_snapshots WHERE expires_at<=?", (now,))
            connection.execute("""INSERT INTO web_query_snapshots
                (session_hash,scope,filters_json,search,project_ids_json,facts_version,created_at,updated_at,expires_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_hash,scope) DO UPDATE SET filters_json=excluded.filters_json,
                search=excluded.search,updated_at=excluded.updated_at,expires_at=excluded.expires_at""",
                (str(session_hash), self.scope, json.dumps(normalized, sort_keys=True), str(jql or "").strip(),
                 "[]", "", now, now, float(expires_at)))

    def get(self, session_hash):
        now = self._now()
        with self.database.connect() as connection:
            row = connection.execute("""SELECT filters_json,search,updated_at,expires_at
                FROM web_query_snapshots WHERE session_hash=? AND scope=? AND expires_at>?""",
                (str(session_hash), self.scope, now)).fetchone()
        if row is None:
            return None
        return JiraFilterSnapshot(str(session_hash), self.scope, json.loads(row[0]), row[1], float(row[2]), float(row[3]))

    def delete(self, session_hash):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM web_query_snapshots WHERE session_hash=? AND scope=?",
                               (str(session_hash), self.scope))

    def facets(self):
        columns = {
            "project": "project_key", "type": "issue_type_name", "status": "status_name",
            "resolution": "resolution_name",
        }
        with self.database.connect() as connection:
            values = {key: [row[0] for row in connection.execute(
                f"SELECT DISTINCT {column} FROM jira_issues WHERE {column} IS NOT NULL AND trim({column})<>'' ORDER BY {column}"
            )] for key, column in columns.items()}
        values["currentUser"] = ["Current User"]
        values["resolution"] = ["Unresolved", *values["resolution"]]
        labels = {"project": "Project", "type": "Type", "status": "Status",
                  "currentUser": "Current User", "resolution": "Resolution"}
        return [{"key": key, "label": labels[key], "options": values[key]} for key in JIRA_FILTER_FIELDS]
