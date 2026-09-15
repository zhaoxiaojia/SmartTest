from __future__ import annotations

from ..database import WebDatabase
from ..schema import ensure_component_schema


JIRA_TABLES = (
    "jira_team_bug_rows",
    "jira_team_bug_lines",
    "jira_team_bug_snapshots",
    "jira_team_bug_accounts",
    "jira_analytics_snapshot_issues",
    "jira_analytics_snapshots",
    "jira_analytics_queries",
    "jira_issue_fix_versions",
    "jira_issue_release_facts",
    "jira_release_field_metadata",
    "jira_issue_components",
    "jira_issue_custom_fields",
    "jira_issue_links",
    "jira_issue_attachments",
    "jira_issue_comments",
    "jira_issue_descriptions",
    "jira_issue_detail_states",
    "jira_issue_labels",
    "jira_sync_state",
    "jira_issues",
)

JIRA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS jira_team_bug_accounts (
        account TEXT PRIMARY KEY, active_snapshot_id TEXT NOT NULL DEFAULT '',
        last_error TEXT NOT NULL DEFAULT '', roster_fingerprint TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS jira_team_bug_snapshots (
        snapshot_id TEXT PRIMARY KEY, account TEXT NOT NULL, roster_fingerprint TEXT NOT NULL,
        team_total INTEGER NOT NULL,
        created_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS jira_team_bug_rows (
        snapshot_id TEXT NOT NULL REFERENCES jira_team_bug_snapshots(snapshot_id) ON DELETE CASCADE,
        product_line TEXT NOT NULL, ordinal INTEGER NOT NULL,
        identity TEXT NOT NULL, display_name TEXT NOT NULL,
        bug_count INTEGER NOT NULL, resolved_count INTEGER NOT NULL,
        p0_count INTEGER NOT NULL, invalid_count INTEGER NOT NULL,
        PRIMARY KEY(snapshot_id,product_line,ordinal)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_team_bug_lines (
        snapshot_id TEXT NOT NULL REFERENCES jira_team_bug_snapshots(snapshot_id) ON DELETE CASCADE,
        ordinal INTEGER NOT NULL, product_line TEXT NOT NULL, project_key TEXT NOT NULL,
        PRIMARY KEY(snapshot_id,product_line)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_analytics_queries (
        session_hash TEXT PRIMARY KEY, account TEXT NOT NULL,
        active_snapshot_id TEXT NOT NULL DEFAULT '', pending_snapshot_id TEXT NOT NULL DEFAULT '',
        task_id TEXT NOT NULL DEFAULT '', expires_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS jira_analytics_snapshots (
        snapshot_id TEXT PRIMARY KEY, session_hash TEXT NOT NULL, account TEXT NOT NULL,
        jql TEXT NOT NULL, basic_json TEXT NOT NULL, source_filter_id TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
        FOREIGN KEY(session_hash) REFERENCES jira_analytics_queries(session_hash) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS jira_analytics_snapshot_issues (
        snapshot_id TEXT NOT NULL REFERENCES jira_analytics_snapshots(snapshot_id) ON DELETE CASCADE,
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        ordinal INTEGER NOT NULL, PRIMARY KEY(snapshot_id,issue_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issues (
        issue_id TEXT PRIMARY KEY, issue_key TEXT NOT NULL UNIQUE,
        web_url TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
        project_id TEXT NOT NULL DEFAULT '', project_key TEXT NOT NULL DEFAULT '',
        project_name TEXT NOT NULL DEFAULT '', status_id TEXT NOT NULL DEFAULT '',
        status_name TEXT NOT NULL DEFAULT '', issue_type_id TEXT NOT NULL DEFAULT '',
        issue_type_name TEXT NOT NULL DEFAULT '', priority_id TEXT, priority_name TEXT,
        assignee_identity TEXT, assignee_account TEXT, assignee_display_name TEXT,
        reporter_identity TEXT, reporter_account TEXT, reporter_display_name TEXT,
        created_at TEXT, updated_at TEXT, source_revision TEXT NOT NULL DEFAULT '',
        cached_at TEXT NOT NULL,
        creator_identity TEXT, creator_account TEXT, creator_display_name TEXT,
        resolution_id TEXT, resolution_name TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS jira_issues_project_key_idx ON jira_issues(project_key)",
    "CREATE INDEX IF NOT EXISTS jira_issues_updated_at_idx ON jira_issues(updated_at)",
    """CREATE TABLE IF NOT EXISTS jira_issue_release_facts (
        issue_id TEXT PRIMARY KEY REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        project_business_id TEXT NOT NULL DEFAULT '', software_release TEXT NOT NULL DEFAULT '',
        severity TEXT NOT NULL DEFAULT '', compare_status TEXT NOT NULL DEFAULT '',
        qa_assignee_identity TEXT NOT NULL DEFAULT '', manager_identity TEXT NOT NULL DEFAULT '',
        resolved_at TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_fix_versions (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        version_id TEXT NOT NULL DEFAULT '', version_name TEXT NOT NULL DEFAULT '',
        released INTEGER, release_date TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(issue_id,version_id,version_name)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_release_field_metadata (
        field_name TEXT PRIMARY KEY, field_key TEXT NOT NULL,
        cached_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_labels (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        label TEXT NOT NULL, PRIMARY KEY(issue_id,label)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_components (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        component_id TEXT NOT NULL, component_name TEXT NOT NULL,
        PRIMARY KEY(issue_id,component_id,component_name)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_detail_states (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        section_name TEXT NOT NULL, state TEXT NOT NULL,
        source_revision TEXT NOT NULL DEFAULT '', error_code TEXT NOT NULL DEFAULT '',
        has_value INTEGER NOT NULL DEFAULT 0, cached_at TEXT NOT NULL,
        PRIMARY KEY(issue_id,section_name)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_descriptions (
        issue_id TEXT PRIMARY KEY REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        content_json TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_comments (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        comment_id TEXT NOT NULL, body_json TEXT NOT NULL,
        author_identity TEXT, author_account TEXT, author_display_name TEXT,
        created_at TEXT, updated_at TEXT, PRIMARY KEY(issue_id,comment_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_attachments (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        attachment_id TEXT NOT NULL, filename TEXT NOT NULL, url TEXT NOT NULL DEFAULT '',
        size INTEGER, author_identity TEXT, author_account TEXT,
        author_display_name TEXT, PRIMARY KEY(issue_id,attachment_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_links (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        link_id TEXT NOT NULL, link_type TEXT NOT NULL, direction TEXT NOT NULL,
        target_id TEXT NOT NULL DEFAULT '', target_key TEXT NOT NULL DEFAULT '',
        target_web_url TEXT NOT NULL DEFAULT '', target_summary TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(issue_id,link_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_issue_custom_fields (
        issue_id TEXT NOT NULL REFERENCES jira_issues(issue_id) ON DELETE CASCADE,
        field_key TEXT NOT NULL, value_json TEXT NOT NULL,
        PRIMARY KEY(issue_id,field_key)
    )""",
    """CREATE TABLE IF NOT EXISTS jira_sync_state (
        scope_key TEXT PRIMARY KEY, cursor TEXT, last_synced_at TEXT, last_error TEXT
    )""",
)


def initialize_jira_schema(database: WebDatabase) -> None:
    ensure_component_schema(
        database,
        component="jira_cache",
        version=4,
        drop_tables=JIRA_TABLES,
        statements=JIRA_STATEMENTS,
    )
    with database.transaction() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jira_issue_release_facts)")}
        if "resolved_at" not in columns:
            connection.execute("ALTER TABLE jira_issue_release_facts ADD COLUMN resolved_at TEXT NOT NULL DEFAULT ''")
        account_columns = {row[1] for row in connection.execute("PRAGMA table_info(jira_team_bug_accounts)")}
        if "roster_fingerprint" not in account_columns:
            connection.execute("ALTER TABLE jira_team_bug_accounts ADD COLUMN roster_fingerprint TEXT NOT NULL DEFAULT ''")
        snapshot_columns = {row[1] for row in connection.execute("PRAGMA table_info(jira_team_bug_snapshots)")}
        if "roster_fingerprint" not in snapshot_columns:
            connection.execute("ALTER TABLE jira_team_bug_snapshots ADD COLUMN roster_fingerprint TEXT NOT NULL DEFAULT ''")
        row_columns = {row[1] for row in connection.execute("PRAGMA table_info(jira_team_bug_rows)")}
        if "product_line" not in row_columns:
            connection.execute("DROP TABLE jira_team_bug_rows")
            connection.execute("""CREATE TABLE jira_team_bug_rows (
                snapshot_id TEXT NOT NULL REFERENCES jira_team_bug_snapshots(snapshot_id) ON DELETE CASCADE,
                product_line TEXT NOT NULL, ordinal INTEGER NOT NULL,
                identity TEXT NOT NULL, display_name TEXT NOT NULL,
                bug_count INTEGER NOT NULL, resolved_count INTEGER NOT NULL,
                p0_count INTEGER NOT NULL, invalid_count INTEGER NOT NULL,
                PRIMARY KEY(snapshot_id,product_line,ordinal))""")
