from jira_tool.services.workspace import (
    JiraWorkspaceService,
    _combine_jql,
    _has_natural_language_search_intent,
    _has_prompt_search_intent,
    _prompt_jql_clause,
    _strip_json_response,
)


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


class _FakeSummarizingAIService:
    def __init__(self):
        self.calls = []

    def ask(self, prompt, *, jira_context=None, max_tokens=None, temperature=None, **_kwargs):
        self.calls.append(
            {
                "prompt": prompt,
                "jira_context": jira_context,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )

        class _Response:
            text = '{"patterns": [{"name": "sample pattern", "count": 1, "evidence_keys": ["A-1"]}], "risks": []}'

        return _Response()


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
    assert service.requires_full_dataset("\u8bf7\u5206\u6790\u5168\u90e8\u95ee\u9898")
    assert service.requires_full_dataset(
        "\u8bf7\u7edf\u8ba1\u641c\u7d22\u7ed3\u679c\u91cc"
        "\u54ea\u4e00\u7c7b\u95ee\u9898\u6700\u591a"
    )


def test_large_analysis_context_uses_local_aggregate() -> None:
    ai_service = _FakeSummarizingAIService()
    service = JiraWorkspaceService(
        base_url="https://jira.example.com",
        issue_service=_FakeIssueService(),
        ai_service=ai_service,
    )
    issues = [
        {
            "keyId": f"A-{index}",
            "summary": f"Issue {index}",
            "status": "Open",
            "priority": "P2",
            "issueType": "Bug",
            "labels": [],
            "components": [],
            "detail": "detail",
        }
        for index in range(250)
    ]
    context = service._build_analysis_context(
        prompt="summarize common patterns",
        effective_jql='text ~ "keyword"',
        issues=issues,
        total_count=len(issues),
    )
    assert len(context["issues"]) == 80
    assert context["issue_aggregate"]["issue_count"] == 250
    assert context["issue_aggregate"]["by_status"] == [{"name": "Open", "count": 250}]
    assert len(ai_service.calls) == 0


def test_natural_language_search_intent_is_generic() -> None:
    assert _has_natural_language_search_intent(
        "\u641c\u7d22\u4e0b\u76f8\u5173bug\uff0c\u7136\u540e\u505a\u98ce\u9669\u5206\u6790"
    )
    assert _has_natural_language_search_intent("find issues related to boot failure")
    assert not _has_natural_language_search_intent("\u603b\u7ed3\u5f53\u524d\u8303\u56f4\u7684\u98ce\u9669")


def test_prompt_search_intent_handles_entity_analysis_request() -> None:
    assert _has_prompt_search_intent("\u5e2e\u6211\u5206\u6790\u4e0b \u8fd1\u534a\u5e74 w2l \u95ee\u9898\u7684\u5206\u5e03")
    assert not _has_prompt_search_intent("\u603b\u7ed3\u5f53\u524d\u8303\u56f4\u7684\u98ce\u9669")


def test_prompt_jql_clause_handles_keyword_and_time_without_ai_planning() -> None:
    clause = _prompt_jql_clause("\u5e2e\u6211\u5206\u6790\u4e0b \u8fd1\u534a\u5e74 w2l \u95ee\u9898\u7684\u5206\u5e03")
    assert 'text ~ "w2l"' in clause
    assert "created >= -26w" in clause


def test_prompt_scope_does_not_keep_previous_search_scope() -> None:
    service = JiraWorkspaceService(
        base_url="https://jira.example.com",
        issue_service=_FakeIssueService(),
        ai_service=_FakeAIService(),
    )
    base_jql = service._analysis_base_jql(
        raw_jql_text="",
        project_ids_csv="tv",
        board_id="open_work",
        timeframe_id="last_30_days",
        status_ids_csv="",
        priority_ids_csv="",
        issue_type_ids_csv="bug",
        keyword_text="TV",
        assignee_text="",
        reporter_text="",
        labels_text="",
        only_mine=False,
        prefer_prompt_scope=True,
    )
    effective_jql = _combine_jql(base_jql, 'text ~ "w2l" AND issuetype = Bug')

    assert "TV" not in effective_jql
    assert 'text ~ "w2l"' in effective_jql
    assert effective_jql.endswith("ORDER BY updated DESC")


def test_strip_json_response_accepts_markdown_fence() -> None:
    assert _strip_json_response('```json\n{"jql_clause": "text ~ \\"w2l\\""}\n```') == (
        '{"jql_clause": "text ~ \\"w2l\\""}'
    )
