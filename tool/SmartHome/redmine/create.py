from __future__ import annotations

from dataclasses import dataclass, field

from support.jira_integration.core.models import CreateIssueResult
from support.jira_integration.services.create_issue_service import CreateIssueService
from tool.SmartHome.redmine.clone_draft import CloneDraft
from tool.SmartHome.redmine.mapping import redmine_tracker_to_jira_type
from tool.SmartHome.redmine.models import RedmineIssueDetail


@dataclass(frozen=True)
class RedmineCloneFailure:
    issue_id: str
    message: str


@dataclass(frozen=True)
class RedmineCloneResult:
    created: list[CreateIssueResult] = field(default_factory=list)
    skipped: list[CreateIssueResult] = field(default_factory=list)
    failed: list[RedmineCloneFailure] = field(default_factory=list)


def clone_issues_to_jira(
    clone_list: (
        list[RedmineIssueDetail | CloneDraft]
        | tuple[RedmineIssueDetail | CloneDraft, ...]
    ),
    *,
    project_key: str,
    create_service: CreateIssueService,
) -> RedmineCloneResult:
    created: list[CreateIssueResult] = []
    skipped: list[CreateIssueResult] = []
    failed: list[RedmineCloneFailure] = []
    for issue in clone_list:
        try:
            request = (
                issue.to_request()
                if isinstance(issue, CloneDraft)
                else issue.to_create_issue_request(
                    project_key=project_key,
                    issue_type=redmine_tracker_to_jira_type(issue.tracker),
                    source_system="redmine",
                )
            )
            result = create_service.create_issue(request)
            (created if result.created else skipped).append(result)
        except Exception as exc:
            failed.append(RedmineCloneFailure(issue_id=issue.id, message=str(exc)))
    return RedmineCloneResult(created=created, skipped=skipped, failed=failed)
