from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from threading import RLock


def _account(value):
    return str(value or "").strip().casefold()


class ConfluenceCurrentStateRepository:
    """Normalized current-state owner shared by every Confluence account."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._migrate()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate(self):
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS confluence_projects (
                    project_page_id TEXT PRIMARY KEY, space_key TEXT NOT NULL,
                    project_id TEXT NOT NULL, display_name TEXT NOT NULL,
                    page_url TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT, sync_status TEXT NOT NULL, base_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS confluence_project_attributes (
                    project_page_id TEXT NOT NULL REFERENCES confluence_projects(project_page_id) ON DELETE CASCADE,
                    field_key TEXT NOT NULL, raw_header TEXT NOT NULL, raw_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL, PRIMARY KEY(project_page_id, field_key)
                );
                CREATE TABLE IF NOT EXISTS confluence_project_people (
                    project_page_id TEXT NOT NULL REFERENCES confluence_projects(project_page_id) ON DELETE CASCADE,
                    role_key TEXT NOT NULL, identity TEXT NOT NULL, display_name TEXT NOT NULL,
                    PRIMARY KEY(project_page_id, role_key, identity)
                );
                CREATE TABLE IF NOT EXISTS confluence_project_pages (
                    project_page_id TEXT NOT NULL REFERENCES confluence_projects(project_page_id) ON DELETE CASCADE,
                    page_type TEXT NOT NULL, page_id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT, parse_status TEXT NOT NULL, PRIMARY KEY(project_page_id, page_type)
                );
                CREATE TABLE IF NOT EXISTS confluence_account_project_access (
                    account_id TEXT NOT NULL, project_page_id TEXT NOT NULL
                        REFERENCES confluence_projects(project_page_id) ON DELETE CASCADE,
                    checked_at TEXT, PRIMARY KEY(account_id, project_page_id)
                );
                CREATE TABLE IF NOT EXISTS confluence_sync_state (
                    account_id TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT, result TEXT NOT NULL, error_summary TEXT, metadata_json TEXT NOT NULL DEFAULT '{}'
                );
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(confluence_sync_state)")}
            if "metadata_json" not in columns:
                connection.execute("ALTER TABLE confluence_sync_state ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")

    @staticmethod
    def _page_id(project):
        return str(project.get("page_id") or project.get("identity") or
                   ":".join(filter(None, (project.get("space_key"), project.get("project_id")))) or "")

    def import_legacy_snapshot(self, username, snapshot):
        """Import one complete legacy snapshot; runtime refreshes must not call this."""
        account = _account(username)
        projects = [row for row in snapshot.get("projects", ()) if row.get("active", True)]
        with self._lock, self._connect() as connection:
            revision_row = connection.execute(
                "SELECT revision FROM confluence_sync_state WHERE account_id=?", (account,),
            ).fetchone()
            revision = int(revision_row[0] if revision_row else 0) + 1
            visible = []
            for incoming in projects:
                project = deepcopy(incoming)
                page_id = self._page_id(project)
                if not page_id:
                    continue
                existing = connection.execute(
                    "SELECT base_json FROM confluence_projects WHERE project_page_id=?", (page_id,),
                ).fetchone()
                failed = project.get("status") == "failed"
                if failed and existing:
                    previous = json.loads(existing[0])
                    project = {**previous, "status": "stale", "error": project.get("error"),
                               "updated_at": project.get("updated_at", previous.get("updated_at"))}
                    fields = self._load_attributes(connection, page_id)
                    roles = self._load_people(connection, page_id)
                    project["fields"], project["roles"] = fields, roles
                base = deepcopy(project)
                fields = base.pop("fields", {})
                raw_fields = base.pop("raw_fields", {})
                roles = base.pop("roles", {})
                sources = {"catalog": base.pop("catalog_source", None),
                           "basic": base.pop("detail_source", None)}
                version = max((int((source or {}).get("version") or 0) for source in sources.values()), default=0)
                connection.execute("""INSERT INTO confluence_projects
                    (project_page_id,space_key,project_id,display_name,page_url,version,updated_at,sync_status,base_json)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(project_page_id) DO UPDATE SET
                    space_key=excluded.space_key,project_id=excluded.project_id,display_name=excluded.display_name,
                    page_url=excluded.page_url,version=excluded.version,updated_at=excluded.updated_at,
                    sync_status=excluded.sync_status,base_json=excluded.base_json""",
                    (page_id, project.get("space_key", ""), project.get("project_id", ""),
                     project.get("name", ""), project.get("page_url", ""), version,
                     project.get("updated_at"), project.get("status", "current"), json.dumps(base)))
                connection.execute("DELETE FROM confluence_project_attributes WHERE project_page_id=?", (page_id,))
                headers = {str(header).strip().casefold(): header for header in project.get("raw_headers", ())}
                for key, value in fields.items():
                    connection.execute("INSERT INTO confluence_project_attributes VALUES(?,?,?,?,?)",
                        (page_id, key, headers.get(key, key), str(raw_fields.get(headers.get(key, key), value)), str(value)))
                connection.execute("DELETE FROM confluence_project_people WHERE project_page_id=?", (page_id,))
                for role, people in roles.items():
                    for person in people:
                        identity = str(person.get("identity") or person.get("name") or "")
                        connection.execute("INSERT OR REPLACE INTO confluence_project_people VALUES(?,?,?,?)",
                            (page_id, role, identity, str(person.get("name") or identity)))
                connection.execute("DELETE FROM confluence_project_pages WHERE project_page_id=?", (page_id,))
                for page_type, source in sources.items():
                    if source:
                        connection.execute("INSERT INTO confluence_project_pages VALUES(?,?,?,?,?,?)",
                            (page_id, page_type, str(source.get("page_id") or ""), int(source.get("version") or 0),
                             source.get("updated_at"), project.get("status", "current")))
                visible.append(page_id)
            connection.execute("DELETE FROM confluence_account_project_access WHERE account_id=?", (account,))
            connection.executemany("INSERT INTO confluence_account_project_access VALUES(?,?,?)",
                                   ((account, page_id, snapshot.get("updated_at")) for page_id in visible))
            metadata = {key: value for key, value in snapshot.items() if key not in {"projects", "revision"}}
            connection.execute("""INSERT INTO confluence_sync_state(account_id,revision,updated_at,result,error_summary,metadata_json)
                VALUES(?,?,?,?,NULL,?) ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,
                updated_at=excluded.updated_at,result=excluded.result,error_summary=NULL,metadata_json=excluded.metadata_json""",
                (account, revision, snapshot.get("updated_at"), snapshot.get("phase", "ready"), json.dumps(metadata)))
        return revision

    def replace_account_catalog(self, username, snapshot):
        """Publish one account's catalog and visibility without replacing shared details."""
        account = _account(username)
        projects = [row for row in snapshot.get("projects", ()) if row.get("active", True)]
        with self._lock, self._connect() as connection:
            revision_row = connection.execute(
                "SELECT revision FROM confluence_sync_state WHERE account_id=?", (account,),
            ).fetchone()
            revision = int(revision_row[0] if revision_row else 0) + 1
            visible = []
            for incoming in projects:
                catalog = deepcopy(incoming)
                page_id = self._page_id(catalog)
                if not page_id:
                    continue
                existing = connection.execute(
                    "SELECT base_json FROM confluence_projects WHERE project_page_id=?", (page_id,),
                ).fetchone()
                incoming_fields = catalog.pop("fields", {})
                incoming_raw_fields = catalog.pop("raw_fields", {})
                catalog.pop("roles", None)
                catalog.pop("detail_source", None)
                catalog_source = catalog.pop("catalog_source", None)
                if existing:
                    base = json.loads(existing[0])
                    preserved_status = base.get("status")
                    base.update(catalog)
                    if preserved_status in {"current", "stale"}:
                        base["status"] = preserved_status
                else:
                    base = catalog
                version = int((catalog_source or {}).get("version") or 0)
                connection.execute("""INSERT INTO confluence_projects
                    (project_page_id,space_key,project_id,display_name,page_url,version,updated_at,sync_status,base_json)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(project_page_id) DO UPDATE SET
                    space_key=excluded.space_key,project_id=excluded.project_id,display_name=excluded.display_name,
                    page_url=excluded.page_url,version=max(confluence_projects.version,excluded.version),
                    updated_at=excluded.updated_at,sync_status=excluded.sync_status,base_json=excluded.base_json""",
                    (page_id, base.get("space_key", ""), base.get("project_id", ""),
                     base.get("name", ""), base.get("page_url", ""), version,
                     base.get("updated_at"), base.get("status", "catalog_ready"), json.dumps(base)))
                headers = {str(header).strip().casefold(): header for header in catalog.get("raw_headers", ())}
                for key, value in incoming_fields.items():
                    header = headers.get(key, key)
                    connection.execute("INSERT OR REPLACE INTO confluence_project_attributes VALUES(?,?,?,?,?)",
                                       (page_id, key, header,
                                        str(incoming_raw_fields.get(header, value)), str(value)))
                if catalog_source:
                    connection.execute("INSERT OR REPLACE INTO confluence_project_pages VALUES(?,?,?,?,?,?)",
                                       (page_id, "catalog", str(catalog_source.get("page_id") or ""), version,
                                        catalog_source.get("updated_at"), base.get("status", "catalog_ready")))
                visible.append(page_id)
            connection.execute("DELETE FROM confluence_account_project_access WHERE account_id=?", (account,))
            connection.executemany("INSERT INTO confluence_account_project_access VALUES(?,?,?)",
                                   ((account, page_id, snapshot.get("updated_at")) for page_id in visible))
            metadata = {key: value for key, value in snapshot.items() if key not in {"projects", "revision"}}
            connection.execute("""INSERT INTO confluence_sync_state(account_id,revision,updated_at,result,error_summary,metadata_json)
                VALUES(?,?,?,?,NULL,?) ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,
                updated_at=excluded.updated_at,result=excluded.result,error_summary=NULL,metadata_json=excluded.metadata_json""",
                (account, revision, snapshot.get("updated_at"), snapshot.get("phase", "ready"), json.dumps(metadata)))
        return revision

    @staticmethod
    def _load_attributes(connection, page_id):
        return {row[0]: row[1] for row in connection.execute(
            "SELECT field_key,normalized_value FROM confluence_project_attributes WHERE project_page_id=?", (page_id,))}

    @staticmethod
    def _load_people(connection, page_id):
        roles = {}
        for row in connection.execute("SELECT role_key,identity,display_name FROM confluence_project_people WHERE project_page_id=?", (page_id,)):
            roles.setdefault(row[0], []).append({"identity": row[1], "name": row[2]})
        return roles

    def load_account_snapshot(self, username):
        account = _account(username)
        with self._connect() as connection:
            state = connection.execute("SELECT revision,updated_at,result,error_summary,metadata_json FROM confluence_sync_state WHERE account_id=?", (account,)).fetchone()
            if state is None:
                return None
            projects = []
            rows = connection.execute("""SELECT p.* FROM confluence_projects p
                JOIN confluence_account_project_access a ON a.project_page_id=p.project_page_id
                WHERE a.account_id=? ORDER BY lower(p.project_id), lower(p.project_page_id)""", (account,))
            for row in rows:
                project = json.loads(row["base_json"])
                project["fields"] = self._load_attributes(connection, row["project_page_id"])
                project["roles"] = self._load_people(connection, row["project_page_id"])
                sources = {source[0]: dict(page_id=source[1], version=source[2], updated_at=source[3])
                           for source in connection.execute("SELECT page_type,page_id,version,updated_at FROM confluence_project_pages WHERE project_page_id=?", (row["project_page_id"],))}
                project["catalog_source"] = sources.get("catalog")
                project["detail_source"] = sources.get("basic")
                projects.append(project)
            metadata = json.loads(state[4] or "{}")
            return {**metadata, "schema_version": 1, "updated_at": state[1], "phase": state[2],
                    "revision": state[0], "projects": projects}

    def account_store(self, username):
        return _AccountCurrentStateStore(self, username)

    def stored_version(self, project_page_id, page_type="basic"):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT version FROM confluence_project_pages WHERE project_page_id=? AND page_type=?",
                (str(project_page_id), page_type),
            ).fetchone()
            return int(row[0]) if row else None

    def upsert_project(self, project):
        """Atomically replace one complete current project without changing access sets."""
        project = deepcopy(project)
        page_id = self._page_id(project)
        fields = project.pop("fields", {})
        raw_fields = project.pop("raw_fields", {})
        roles = project.pop("roles", {})
        sources = {"catalog": project.pop("catalog_source", None),
                   "basic": project.pop("detail_source", None)}
        headers = {str(header).strip().casefold(): header for header in project.get("raw_headers", ())}
        version = max((int((source or {}).get("version") or 0) for source in sources.values()), default=0)
        base_json = json.dumps(project)
        with self._lock, self._connect() as connection:
            connection.execute("""INSERT INTO confluence_projects
                (project_page_id,space_key,project_id,display_name,page_url,version,updated_at,sync_status,base_json)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(project_page_id) DO UPDATE SET
                space_key=excluded.space_key,project_id=excluded.project_id,display_name=excluded.display_name,
                page_url=excluded.page_url,version=excluded.version,updated_at=excluded.updated_at,
                sync_status=excluded.sync_status,base_json=excluded.base_json""",
                (page_id, project.get("space_key", ""), project.get("project_id", ""),
                 project.get("name", ""), project.get("page_url", ""), version,
                 project.get("updated_at"), project.get("status", "current"), base_json))
            connection.execute("DELETE FROM confluence_project_attributes WHERE project_page_id=?", (page_id,))
            for key, value in fields.items():
                header = headers.get(key, key)
                connection.execute("INSERT INTO confluence_project_attributes VALUES(?,?,?,?,?)",
                                   (page_id, key, header, str(raw_fields.get(header, value)), str(value)))
            connection.execute("DELETE FROM confluence_project_people WHERE project_page_id=?", (page_id,))
            for role, people in roles.items():
                for person in people:
                    identity = str(person.get("identity") or person.get("name") or "")
                    connection.execute("INSERT OR REPLACE INTO confluence_project_people VALUES(?,?,?,?)",
                                       (page_id, role, identity, str(person.get("name") or identity)))
            connection.execute("DELETE FROM confluence_project_pages WHERE project_page_id=?", (page_id,))
            for page_type, source in sources.items():
                if source:
                    connection.execute("INSERT INTO confluence_project_pages VALUES(?,?,?,?,?,?)",
                                       (page_id, page_type, str(source.get("page_id") or ""),
                                        int(source.get("version") or 0), source.get("updated_at"),
                                        project.get("status", "current")))
            connection.execute("""UPDATE confluence_sync_state SET revision=revision+1
                WHERE account_id IN (SELECT account_id FROM confluence_account_project_access
                                     WHERE project_page_id=?)""", (page_id,))

    def mark_project_stale(self, project_page_id, error_summary):
        with self._connect() as connection:
            row = connection.execute("SELECT base_json FROM confluence_projects WHERE project_page_id=?",
                                     (str(project_page_id),)).fetchone()
            if not row:
                return False
            base = json.loads(row[0]); base.update(status="stale", error={"message": str(error_summary)[:240]})
            connection.execute("UPDATE confluence_projects SET sync_status='stale',base_json=? WHERE project_page_id=?",
                               (json.dumps(base), str(project_page_id)))
            return True


class _AccountCurrentStateStore:
    def __init__(self, repository, username):
        self._repository = repository
        self._username = username
        self.resolved_path = repository.path

    def load(self):
        return self._repository.load_account_snapshot(self._username)

    def save(self, snapshot):
        return self._repository.replace_account_catalog(self._username, snapshot)
