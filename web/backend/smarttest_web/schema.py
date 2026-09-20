from __future__ import annotations

from collections.abc import Iterable

from .database import WebDatabase


def ensure_component_schema(
    database: WebDatabase,
    *,
    component: str,
    version: int,
    statements: Iterable[str],
) -> None:
    with database.transaction() as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(smarttest_schema)")
        }
        obsolete_marker = bool(columns and "component" not in columns)
        if obsolete_marker:
            connection.execute("DROP TABLE smarttest_schema")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS smarttest_schema ("
            "component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
        )
        if obsolete_marker:
            connection.execute(
                "INSERT INTO smarttest_schema(component,version) VALUES('confluence_cache',0)"
            )
        row = connection.execute(
            "SELECT version FROM smarttest_schema WHERE component=?", (component,)
        ).fetchone()
        for statement in statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO smarttest_schema(component,version) VALUES(?,?) "
            "ON CONFLICT(component) DO UPDATE SET version=excluded.version",
            (component, version),
        )


def initialize_current_cache_schema(database: WebDatabase) -> None:
    from .confluence.schema import initialize_confluence_schema
    from .jira.schema import initialize_jira_schema

    initialize_jira_schema(database)
    initialize_confluence_schema(database)


def initialize_web_schema(database: WebDatabase) -> None:
    """Prepare every persistent Web component before constructing its owners."""
    with database.connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    with database.transaction() as connection:
        if connection.execute("PRAGMA user_version").fetchone()[0] > 3:
            raise RuntimeError("Unsupported SmartTest Web database schema.")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS web_sessions (
                id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL, display_name TEXT NOT NULL, avatar BLOB,
                created_at REAL NOT NULL, last_seen_at REAL NOT NULL,
                expires_at REAL NOT NULL, revoked_at REAL
            );
            CREATE INDEX IF NOT EXISTS ix_web_sessions_user ON web_sessions(username);
            CREATE TABLE IF NOT EXISTS user_preferences (
                username TEXT NOT NULL, scope TEXT NOT NULL, key TEXT NOT NULL,
                value_json TEXT NOT NULL, schema_version INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL, PRIMARY KEY (username, scope, key)
            );
            CREATE TABLE IF NOT EXISTS web_query_snapshots (
                session_hash TEXT NOT NULL, scope TEXT NOT NULL,
                filters_json TEXT NOT NULL, search TEXT NOT NULL,
                project_ids_json TEXT NOT NULL, facts_version TEXT NOT NULL,
                release_names_json TEXT NOT NULL DEFAULT '[]',
                jira_cache_version TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL, updated_at REAL NOT NULL, expires_at REAL NOT NULL,
                PRIMARY KEY (session_hash, scope)
            );
            CREATE INDEX IF NOT EXISTS ix_web_query_snapshots_expiry ON web_query_snapshots(expires_at);
            CREATE TABLE IF NOT EXISTS web_credentials (
                credential_ref TEXT PRIMARY KEY, nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL, key_version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS web_resource_access (
                account TEXT NOT NULL, platform TEXT NOT NULL, kind TEXT NOT NULL,
                resource_id TEXT NOT NULL, capability TEXT NOT NULL, scope TEXT NOT NULL,
                confirmed_at REAL NOT NULL,
                PRIMARY KEY(account,platform,kind,resource_id,capability,scope)
            );
            CREATE TABLE IF NOT EXISTS test_suites (
                id TEXT PRIMARY KEY, owner_username TEXT NOT NULL,
                owner_display_name TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', visibility TEXT NOT NULL
                CHECK (visibility IN ('private','shared')),
                ordered_nodeids_json TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL, updated_at REAL NOT NULL,
                UNIQUE(owner_username,name)
            );
            CREATE INDEX IF NOT EXISTS ix_test_suites_visibility_updated
                ON test_suites(visibility,updated_at DESC);
            CREATE TABLE IF NOT EXISTS audit_email_runs (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                account TEXT NOT NULL, label TEXT NOT NULL, state TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_email_occurrences (
                account TEXT NOT NULL, occurrence TEXT NOT NULL, claimed_at TEXT NOT NULL,
                PRIMARY KEY(account, occurrence)
            );
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(web_sessions)")}
        if "credential_ref" not in columns:
            connection.execute("ALTER TABLE web_sessions ADD COLUMN credential_ref TEXT")
        if "revoked_reason" not in columns:
            connection.execute("ALTER TABLE web_sessions ADD COLUMN revoked_reason TEXT")
        snapshot_columns = {row[1] for row in connection.execute("PRAGMA table_info(web_query_snapshots)")}
        if "release_names_json" not in snapshot_columns:
            connection.execute("ALTER TABLE web_query_snapshots ADD COLUMN release_names_json TEXT NOT NULL DEFAULT '[]'")
        if "jira_cache_version" not in snapshot_columns:
            connection.execute("ALTER TABLE web_query_snapshots ADD COLUMN jira_cache_version TEXT NOT NULL DEFAULT ''")
        connection.execute("PRAGMA user_version=3")
    initialize_current_cache_schema(database)
    from .confluence.project_repository import upgrade_cached_project_names
    upgrade_cached_project_names(database)
