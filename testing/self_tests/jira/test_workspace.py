from jira.services.workspace import JiraWorkspaceService


class _FakeClient:
    def fetch_favourite_filters(self):
        return [
            {"id": "1", "name": "My open issues", "jql": "assignee = currentUser()"},
            {"id": "1", "name": "duplicate", "jql": "ignored"},
            {"id": "", "name": "invalid", "jql": "ignored"},
        ]


class _FakeIssueService:
    def __init__(self):
        self._client = _FakeClient()


class _FakeAIService:
    pass


def test_fetch_saved_filters_normalizes_duplicates() -> None:
    service = JiraWorkspaceService(
        base_url="https://jira.example.com",
        issue_service=_FakeIssueService(),
        ai_service=_FakeAIService(),
    )
    assert service.fetch_saved_filters() == [
        {"id": "1", "name": "My open issues", "jql": "assignee = currentUser()"}
    ]


def test_requires_full_dataset_supports_english_and_chinese_markers() -> None:
    service = JiraWorkspaceService(
        base_url="https://jira.example.com",
        issue_service=_FakeIssueService(),
        ai_service=_FakeAIService(),
    )
    assert service.requires_full_dataset("analyze all issues in this sprint")
    assert service.requires_full_dataset("请分析全部问题")
