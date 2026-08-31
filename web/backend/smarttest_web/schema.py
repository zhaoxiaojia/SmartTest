from __future__ import annotations

from collections.abc import Iterable

from .database import WebDatabase


def ensure_component_schema(
    database: WebDatabase,
    *,
    component: str,
    version: int,
    drop_tables: Iterable[str],
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
        if row is not None and int(row[0]) != version:
            for table in drop_tables:
                connection.execute(f'DROP TABLE IF EXISTS "{table}"')
            connection.execute(
                "DELETE FROM smarttest_schema WHERE component=?", (component,)
            )
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
