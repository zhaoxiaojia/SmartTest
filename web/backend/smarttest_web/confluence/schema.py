from __future__ import annotations

from ..database import WebDatabase
from ..schema import ensure_component_schema


CONFLUENCE_TABLES = (
    "project_current_releases",
    "confluence_account_project_access",
    "confluence_project_attributes",
    "confluence_project_people",
    "confluence_project_pages",
    "confluence_project_evidence",
    "confluence_project_fields",
    "confluence_project_milestones",
    "confluence_project_role_people",
    "confluence_project_roles",
    "confluence_project_detail_states",
    "confluence_project_owners",
    "confluence_sync_state",
    "confluence_projects",
)

CONFLUENCE_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS confluence_projects (
        confluence_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '', product_space_key TEXT NOT NULL DEFAULT '',
        product_space_name TEXT NOT NULL DEFAULT '', product_space_url TEXT NOT NULL DEFAULT '',
        catalog_page_id TEXT NOT NULL DEFAULT '', catalog_page_title TEXT NOT NULL DEFAULT '',
        catalog_page_url TEXT NOT NULL DEFAULT '', catalog_page_version INTEGER NOT NULL DEFAULT 0,
        status_id TEXT, status_name TEXT, stage_id TEXT, stage_name TEXT,
        support_mode_id TEXT, support_mode_name TEXT, customer_summary TEXT NOT NULL DEFAULT '',
        source_revision TEXT NOT NULL DEFAULT '', cached_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS confluence_projects_space_idx ON confluence_projects(product_space_key)",
    """CREATE TABLE IF NOT EXISTS project_current_releases (
        confluence_id TEXT PRIMARY KEY REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        project_id TEXT NOT NULL DEFAULT '', release_name TEXT NOT NULL DEFAULT '',
        launch_time TEXT NOT NULL DEFAULT '', mp_time TEXT NOT NULL DEFAULT '',
        next_target TEXT NOT NULL DEFAULT '', next_target_date TEXT NOT NULL DEFAULT '',
        current_hw_stage TEXT NOT NULL DEFAULT '', status_summary TEXT NOT NULL DEFAULT '',
        source_revision TEXT NOT NULL DEFAULT '', cached_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_owners (
        confluence_id TEXT NOT NULL REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        identity TEXT NOT NULL, account TEXT NOT NULL DEFAULT '', display_name TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(confluence_id,identity)
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_detail_states (
        confluence_id TEXT NOT NULL REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        section_name TEXT NOT NULL, state TEXT NOT NULL,
        source_revision TEXT NOT NULL DEFAULT '', error_code TEXT NOT NULL DEFAULT '',
        has_value INTEGER NOT NULL DEFAULT 0, cached_at TEXT NOT NULL,
        PRIMARY KEY(confluence_id,section_name)
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_roles (
        confluence_id TEXT NOT NULL REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        role_id TEXT NOT NULL, role_name TEXT NOT NULL,
        PRIMARY KEY(confluence_id,role_id)
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_role_people (
        confluence_id TEXT NOT NULL, role_id TEXT NOT NULL, identity TEXT NOT NULL,
        account TEXT NOT NULL DEFAULT '', display_name TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(confluence_id,role_id,identity),
        FOREIGN KEY(confluence_id,role_id) REFERENCES confluence_project_roles(confluence_id,role_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_milestones (
        confluence_id TEXT NOT NULL REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        milestone_key TEXT NOT NULL, milestone_value TEXT NOT NULL,
        PRIMARY KEY(confluence_id,milestone_key)
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_fields (
        confluence_id TEXT NOT NULL REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        section_name TEXT NOT NULL, field_key TEXT NOT NULL, value_json TEXT NOT NULL,
        PRIMARY KEY(confluence_id,section_name,field_key)
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_project_evidence (
        confluence_id TEXT NOT NULL REFERENCES confluence_projects(confluence_id) ON DELETE CASCADE,
        source TEXT NOT NULL, page_id TEXT NOT NULL, page_title TEXT NOT NULL DEFAULT '',
        page_url TEXT NOT NULL DEFAULT '', page_version INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(confluence_id,source,page_id)
    )""",
    """CREATE TABLE IF NOT EXISTS confluence_sync_state (
        scope_key TEXT PRIMARY KEY, cursor TEXT, last_synced_at TEXT, last_error TEXT
    )""",
)


def initialize_confluence_schema(database: WebDatabase) -> None:
    ensure_component_schema(
        database,
        component="confluence_cache",
        version=3,
        drop_tables=CONFLUENCE_TABLES,
        statements=CONFLUENCE_STATEMENTS,
    )
