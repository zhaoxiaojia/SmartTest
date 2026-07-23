import pytest

from support.jira_integration.core.models import CreateIssueAttachment, CreateIssueRequest
from support.jira_integration.services.create_issue_service import CreateIssueService


class Client:
    def __init__(self, *, existing=(), fail=(), found_issue=None):
        self.existing = list(existing)
        self.fail = set(fail)
        self.found_issue = found_issue
        self.created = []
        self.uploaded = []

    def search_page(self, *_args, **_kwargs):
        from support.jira_integration.core.models import SearchPage

        issues = [self.found_issue] if self.found_issue else []
        return SearchPage(issues, 0, 1, len(issues))

    def create_issue(self, payload):
        self.created.append(payload)
        return {"key": "SH-1", "id": "10", "self": "jira/SH-1"}

    def list_attachments(self, issue_key):
        assert issue_key == "SH-1"
        return list(self.existing)

    def upload_attachment(self, issue_key, attachment):
        self.uploaded.append((issue_key, attachment.filename, attachment.size))
        if attachment.filename in self.fail:
            raise RuntimeError("upload failed")
        return {"filename": attachment.filename}


def request(*attachments):
    return CreateIssueRequest(
        project_key="SH",
        issue_type="Bug",
        summary="bug",
        source_system="redmine",
        source_id="1",
        attachments=tuple(attachments),
    )


def attachment(name, data):
    return CreateIssueAttachment(filename=name, data=data)


def test_create_then_upload_skips_matching_filename_and_size():
    client = Client(existing=({"filename": "same.log", "size": 4},))
    result = CreateIssueService(client).create_issue(
        request(attachment("same.log", b"same"), attachment("new.log", b"new"))
    )

    assert result.created
    assert "attachments" not in client.created[0]["fields"]
    assert client.uploaded == [("SH-1", "new.log", 3)]
    assert result.attachment_errors == ()


def test_same_filename_with_different_size_is_conflict_without_upload():
    client = Client(existing=({"filename": "same.log", "size": 8},))

    result = CreateIssueService(client).create_issue(
        request(attachment("same.log", b"same"))
    )

    assert client.uploaded == []
    assert result.issue_key == "SH-1"
    assert result.attachment_errors == (
        "same.log: Jira already has an attachment with a different size",
    )


def test_partial_upload_failure_preserves_issue_and_retry_only_uploads_missing():
    first = Client(fail={"b.log"})
    service = CreateIssueService(first)
    result = service.create_issue(
        request(attachment("a.log", b"a"), attachment("b.log", b"bb"))
    )

    assert result.issue_key == "SH-1"
    assert result.attachment_errors == ("b.log: RuntimeError",)

    retry = Client(existing=({"filename": "a.log", "size": 1},))
    retried = CreateIssueService(retry).sync_attachments(
        "SH-1", request(attachment("a.log", b"a"), attachment("b.log", b"bb")).attachments
    )
    assert retry.uploaded == [("SH-1", "b.log", 2)]
    assert retried == ()


def test_existing_issue_only_syncs_missing_attachments_without_recreating():
    client = Client(
        existing=({"filename": "a.log", "size": 1},),
        found_issue={"key": "SH-1", "fields": {"summary": "existing"}},
    )
    result = CreateIssueService(
        client, browse_base_url="https://jira.example"
    ).create_issue(
        request(attachment("a.log", b"a"), attachment("b.log", b"bb"))
    )

    assert not result.created
    assert result.existing_key == "SH-1"
    assert result.issue_url == "https://jira.example/browse/SH-1"
    assert client.created == []
    assert client.uploaded == [("SH-1", "b.log", 2)]


def test_attachment_filename_rejects_header_injection():
    with pytest.raises(ValueError):
        attachment('bad"\r\nX-Evil: yes', b"x")
