from jira.core.models import IssueRecord
from jira.services.presenter import extract_actions, record_to_issue_row


def test_record_to_issue_row_normalizes_nested_text_and_comments() -> None:
    record = IssueRecord(
        key="FQ-123",
        id="123",
        raw={},
        fields={
            "summary": "Example summary",
            "status": "In Progress",
            "priority": "P1",
            "assignee": "Alice",
            "reporter": "Bob",
            "labels": ["wifi", "regression"],
            "components": ["Connectivity"],
            "project": "TV",
            "updated": "2026-04-20",
            "description": {"content": [{"text": "Line 1"}, {"text": "Line 2"}]},
            "comments": [{"content": [{"text": "First comment"}]}, "Second comment"],
            "issuelinks": [{"id": "1"}, {"id": "2"}],
            "issueType": "Bug",
            "resolution": "Unresolved",
        },
    )
    row = record_to_issue_row(record)
    assert row["keyId"] == "FQ-123"
    assert row["detail"] == "Line 1\nLine 2"
    assert row["comments"] == ["First comment", "Second comment"]
    assert row["commentCount"] == 2
    assert row["linkCount"] == 2


def test_extract_actions_returns_bulleted_lines_only() -> None:
    text = "Summary\n- first\n* second\n1. third\nplain line"
    assert extract_actions(text) == ["first", "second", "third"]
