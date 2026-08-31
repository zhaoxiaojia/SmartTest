from __future__ import annotations

from core.jira.commands import CreateIssueCommand
from core.tools.SmartHome.redmine.issue_store import RedmineIssue, RedmineIssueStore
from core.tools.SmartHome.redmine.jira_mapper import RedmineToJiraMapper


def test_redmine_issue_store_owns_redmine_records_without_jira_entity() -> None:
    store = RedmineIssueStore([RedmineIssue(id="9", title="Source issue")])

    assert store.issue_list[0].id == "9"
    assert store.issue_list[0].title == "Source issue"
    assert not hasattr(store.issue_list[0], "identity")


def test_redmine_to_jira_mapper_returns_command_boundary() -> None:
    command = RedmineToJiraMapper().to_create_command(
        project_key="SH",
        issue_type="Bug",
        summary="Clone source",
        source_id="9",
        source_url="https://redmine/issues/9",
    )

    assert isinstance(command, CreateIssueCommand)
    assert command.source_system == "redmine"
    assert command.source_id == "9"
