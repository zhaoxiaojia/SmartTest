from smarttest_web.audit.email_history import AuditEmailHistory
from smarttest_web.confluence.project_repository import ConfluenceProjectRepository
from smarttest_web.database import WebDatabase
from smarttest_web.jira.issue_repository import JiraIssueRepository
from smarttest_web.resource_access import ResourceAccess
from smarttest_web.schema import initialize_web_schema
from smarttest_web.session import PersistentSessionStore
from smarttest_web.test_suite_repository import TestSuiteRepository


def test_empty_database_initialization_is_complete_and_idempotent(tmp_path) -> None:
    database = WebDatabase(tmp_path / "empty.db")

    initialize_web_schema(database)
    initialize_web_schema(database)

    with database.connect() as connection:
        names = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"web_sessions", "web_credentials", "web_resource_access", "test_suites",
            "audit_email_runs", "jira_issues", "confluence_projects"} <= names


def test_component_version_upgrade_preserves_persistent_rows(tmp_path) -> None:
    database = WebDatabase(tmp_path / "upgrade.db")
    initialize_web_schema(database)
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO confluence_projects(confluence_id,project_id,cached_at) VALUES('1','P1','now')"
        )
        connection.execute("UPDATE smarttest_schema SET version=1 WHERE component='confluence_cache'")

    initialize_web_schema(database)

    with database.connect() as connection:
        assert connection.execute(
            "SELECT project_id FROM confluence_projects WHERE confluence_id='1'"
        ).fetchone()[0] == "P1"


def test_owner_construction_executes_no_schema_ddl(tmp_path) -> None:
    database = WebDatabase(tmp_path / "owners.db")
    initialize_web_schema(database)
    with database.connect() as connection:
        before = connection.execute("PRAGMA schema_version").fetchone()[0]
    JiraIssueRepository(database)
    ConfluenceProjectRepository(database)
    TestSuiteRepository(database)
    AuditEmailHistory(database)
    ResourceAccess(database, "a", "p", "s")
    PersistentSessionStore(database.path)
    with database.connect() as connection:
        after = connection.execute("PRAGMA schema_version").fetchone()[0]
    assert after == before
