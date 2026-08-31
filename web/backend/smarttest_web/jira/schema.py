from __future__ import annotations

from ..database import WebDatabase
from ..schema import ensure_component_schema


JIRA_TABLES = (
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
