import json

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


def test_confluence_acquisition_upgrade_marks_loaded_details_stale_once(tmp_path) -> None:
    database = WebDatabase(tmp_path / "upgrade-details.db")
    initialize_web_schema(database)
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO confluence_projects(confluence_id,project_id,cached_at) VALUES('1','P1','now')"
        )
        connection.executemany(
            """INSERT INTO confluence_project_detail_states
            (confluence_id,section_name,state,source_revision,error_code,has_value,cached_at)
            VALUES('1',?,'loaded','','',1,'now')""",
            (("roles",), ("facts",)),
        )
        connection.execute("UPDATE smarttest_schema SET version=3 WHERE component='confluence_cache'")

    initialize_web_schema(database)
    with database.connect() as connection:
        assert connection.execute(
            "SELECT section_name,state FROM confluence_project_detail_states ORDER BY section_name"
        ).fetchall() == [("facts", "stale"), ("roles", "stale")]
    with database.transaction() as connection:
        connection.execute(
            "UPDATE confluence_project_detail_states SET state='loaded' WHERE confluence_id='1'"
        )

    initialize_web_schema(database)
    with database.connect() as connection:
        assert connection.execute(
            "SELECT DISTINCT state FROM confluence_project_detail_states WHERE confluence_id='1'"
        ).fetchall() == [("loaded",)]


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


def test_customer_placeholder_period_migrates_to_the_registered_card_scope(tmp_path) -> None:
    database = WebDatabase(tmp_path / "customer-period.db")
    initialize_web_schema(database)
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO user_preferences VALUES(?,?,?,?,?,?)",
            ("coco", "jira/cards/customer", "period", '"quarter"', 1, 1),
        )

    initialize_web_schema(database)

    with database.connect() as connection:
        rows = connection.execute(
            "SELECT scope,value_json FROM user_preferences WHERE username='coco'"
        ).fetchall()
    assert rows == [("jira/cards/customer-feedback", '"quarter"')]


def test_legacy_dashboard_jira_cards_migrate_without_changing_layout_or_other_config(tmp_path) -> None:
    database = WebDatabase(tmp_path / "dashboard-layout.db")
    initialize_web_schema(database)
    layout = [
        {"id": "self", "type": "jira-team-bugs", "x": 1, "y": 2, "w": 20, "h": 9,
         "config": {"color": "blue"}, "unrelated": "keep"},
        {"id": "role", "type": "role-workload", "x": 0, "y": 11, "w": 24, "h": 8,
         "config": {"mode": "major"}},
        {"id": "customer", "type": "jira-customer-statistics", "x": 2, "y": 20, "w": 22, "h": 7,
         "config": {"period": "quarter"}},
    ]
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO user_preferences VALUES(?,?,?,?,?,?)",
            ("coco", "dashboard/layout", "layout", json.dumps(layout), 1, 1),
        )

    initialize_web_schema(database)

    with database.connect() as connection:
        migrated = json.loads(connection.execute(
            "SELECT value_json FROM user_preferences WHERE username='coco' AND scope='dashboard/layout' AND key='layout'"
        ).fetchone()[0])
    assert migrated == [
        {**layout[0], "type": "jira-statistics-self-test", "config": {"color": "blue", "cardKey": "self-test"}},
        layout[1],
        {**layout[2], "type": "jira-statistics-customer-feedback",
         "config": {"period": "quarter", "cardKey": "customer-feedback"}},
    ]
