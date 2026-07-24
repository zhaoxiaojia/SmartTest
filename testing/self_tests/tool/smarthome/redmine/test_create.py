from support.jira_integration.core.models import CreateIssueResult
from tool.SmartHome.redmine.create import clone_issues_to_jira
from tool.SmartHome.redmine.models import RedmineIssueDetail


class FakeCreateService:
    def __init__(self):
        self.requests = []

    def create_issue(self, request):
        self.requests.append(request)
        if request.source_id == "1":
            return CreateIssueResult(created=True, issue_key="TV-1")
        return CreateIssueResult(created=False, existing_key="TV-2")


def test_clone_issues_to_jira_maps_redmine_trackers_and_summarizes_results():
    service = FakeCreateService()
    result = clone_issues_to_jira(
        [
            RedmineIssueDetail(id="1", url="https://support/issues/1", tracker="Bug", subject="bug", description="bug desc"),
            RedmineIssueDetail(id="2", url="https://support/issues/2", tracker="Support", subject="support", description="support desc"),
        ],
        project_key="TV",
        create_service=service,
    )

    assert [request.issue_type for request in service.requests] == ["Bug", "Feature"]
    assert result.created == [CreateIssueResult(created=True, issue_key="TV-1")]
    assert result.skipped == [CreateIssueResult(created=False, existing_key="TV-2")]
    assert result.failed == []


def test_clone_issues_to_jira_classifies_create_failed_result_as_failure():
    class FailedCreateService:
        def create_issue(self, _request):
            return CreateIssueResult(
                created=False,
                issue_state="create_failed",
                issue_error="offline",
            )

    result = clone_issues_to_jira(
        [
            RedmineIssueDetail(
                id="1",
                url="https://support/issues/1",
                tracker="Bug",
                subject="bug",
            )
        ],
        project_key="TV",
        create_service=FailedCreateService(),
    )

    assert result.created == []
    assert result.skipped == []
    assert result.failed[0].issue_id == "1"
    assert result.failed[0].message == "offline"
