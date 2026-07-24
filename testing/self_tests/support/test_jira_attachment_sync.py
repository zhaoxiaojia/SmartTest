from pathlib import Path

import pytest

from support.jira_integration.core.models import (
    CreateIssueAttachment,
    CreateIssueRequest,
    JiraAttachmentMetadata,
)
from support.jira_integration.services.create_issue_service import CreateIssueService


class Client:
    def __init__(
        self,
        *,
        existing=(),
        fail=(),
        found_issue=None,
        metadata=JiraAttachmentMetadata(available=True, enabled=True, upload_limit=10),
    ):
        self.existing = list(existing)
        self.fail = set(fail)
        self.found_issue = found_issue
        self.metadata = metadata
        self.created = []
        self.uploaded = []

    def search_page(self, *_args, **_kwargs):
        from support.jira_integration.core.models import SearchPage

        issues = [self.found_issue] if self.found_issue else []
        return SearchPage(issues, 0, 1, len(issues))

    def create_issue(self, payload):
        self.created.append(payload)
        return {"key": "SH-1", "id": "10", "self": "jira/SH-1"}

    def attachment_metadata(self):
        return self.metadata

    def list_attachments(self, issue_key):
        assert issue_key == "SH-1"
        return list(self.existing)

    def upload_attachment(self, issue_key, attachment, *, cancellation=None):
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


def attachment(
    tmp_path: Path,
    name: str,
    data: bytes,
    *,
    source_id: str = "",
    upload_filename: str = "",
):
    path = tmp_path / name
    path.write_bytes(data)
    return CreateIssueAttachment(
        source_id=source_id,
        filename=name,
        upload_filename=upload_filename,
        path=path,
    )


def test_create_then_upload_skips_matching_filename_and_size(tmp_path):
    client = Client(existing=({"filename": "same.log", "size": 4},))
    result = CreateIssueService(client).create_issue(
        request(
            attachment(tmp_path, "same.log", b"same"),
            attachment(tmp_path, "new.log", b"new"),
        )
    )

    assert result.issue_state == "created"
    assert "attachments" not in client.created[0]["fields"]
    assert client.uploaded == [("SH-1", "new.log", 3)]
    assert result.attachment_state == "complete"
    assert [item.state for item in result.attachment_results] == [
        "already_present",
        "uploaded",
    ]


def test_known_limit_skips_oversized_before_upload_but_preserves_created_issue(tmp_path):
    client = Client(
        metadata=JiraAttachmentMetadata(
            available=True, enabled=True, upload_limit=3
        )
    )

    result = CreateIssueService(client).create_issue(
        request(attachment(tmp_path, "large.log", b"four"))
    )

    assert result.issue_state == "created"
    assert result.issue_key == "SH-1"
    assert result.attachment_state == "oversized"
    assert client.uploaded == []
    assert result.attachment_results[0].state == "oversized"
    assert result.attachment_results[0].size == 4
    assert result.attachment_results[0].reason_code == "attachment_oversized"
    assert result.attachment_results[0].reason_args["limit_bytes"] == 3


@pytest.mark.parametrize(
    "metadata, expected_state",
    [
        (
            JiraAttachmentMetadata(
                available=True, enabled=False, upload_limit=100
            ),
            "partial_failed",
        ),
        (
            JiraAttachmentMetadata(
                available=False, enabled=None, upload_limit=None
            ),
            "complete",
        ),
        (
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=None
            ),
            "complete",
        ),
    ],
)
def test_disabled_and_unknown_attachment_metadata_are_explicit(
    tmp_path, metadata, expected_state
):
    client = Client(metadata=metadata)

    result = CreateIssueService(client).create_issue(
        request(attachment(tmp_path, "a.log", b"a"))
    )

    assert result.attachment_state == expected_state
    if metadata.enabled is False:
        assert client.uploaded == []
        assert result.attachment_results[0].retryable is False
    else:
        assert client.uploaded == [("SH-1", "a.log", 1)]


def test_partial_upload_failure_preserves_issue_and_retry_only_uploads_missing(
    tmp_path,
):
    first = Client(fail={"b.log"})
    result = CreateIssueService(first).create_issue(
        request(
            attachment(tmp_path, "a.log", b"a"),
            attachment(tmp_path, "b.log", b"bb"),
        )
    )

    assert result.issue_state == "created"
    assert result.issue_key == "SH-1"
    assert result.attachment_state == "partial_failed"
    assert [item.state for item in result.attachment_results] == [
        "uploaded",
        "failed",
    ]
    assert result.attachment_results[1].retryable

    retry = Client(existing=({"filename": "a.log", "size": 1},))
    retried = CreateIssueService(retry).sync_attachments(
        "SH-1",
        request(
            attachment(tmp_path, "a2.log", b"a"),
            attachment(tmp_path, "b2.log", b"bb"),
        ).attachments,
    )
    assert [item.state for item in retried.results] == ["uploaded", "uploaded"]


def test_existing_issue_only_syncs_missing_attachments_without_recreating(tmp_path):
    client = Client(
        existing=({"filename": "a.log", "size": 1},),
        found_issue={"key": "SH-1", "fields": {"summary": "existing"}},
    )
    result = CreateIssueService(
        client, browse_base_url="https://jira.example"
    ).create_issue(
        request(
            attachment(tmp_path, "a.log", b"a"),
            attachment(tmp_path, "b.log", b"bb"),
        )
    )

    assert result.issue_state == "duplicate"
    assert result.existing_key == "SH-1"
    assert result.issue_url == "https://jira.example/browse/SH-1"
    assert client.created == []
    assert client.uploaded == [("SH-1", "b.log", 2)]
    assert result.attachment_state == "complete"


def test_attachment_filename_rejects_header_injection(tmp_path):
    source = tmp_path / "safe"
    source.write_bytes(b"x")
    with pytest.raises(ValueError):
        CreateIssueAttachment(filename='bad"\r\nX-Evil: yes', path=source)
    with pytest.raises(ValueError):
        CreateIssueAttachment(
            filename="safe.log",
            upload_filename='bad"\r\nX-Evil: yes',
            path=source,
        )


def test_attachment_requires_an_existing_regular_file(tmp_path):
    with pytest.raises(ValueError, match="regular file"):
        CreateIssueAttachment(filename="missing.log", path=tmp_path / "missing")


def test_unavailable_metadata_is_reported_as_unknown_instead_of_a_guessed_limit():
    class UnavailableClient(Client):
        def attachment_metadata(self):
            raise RuntimeError("offline")

    metadata = CreateIssueService(UnavailableClient()).attachment_metadata()

    assert metadata == JiraAttachmentMetadata(
        available=False, enabled=None, upload_limit=None
    )


def test_created_issue_result_uses_the_browse_url_for_ui_navigation():
    result = CreateIssueService(
        Client(), browse_base_url="https://jira.example"
    ).create_issue(request())

    assert result.issue_url == "https://jira.example/browse/SH-1"


def test_same_filename_and_size_sources_use_distinct_upload_names_on_retry(
    tmp_path,
):
    class SourceClient(Client):
        def __init__(self):
            super().__init__()
            self.remote = []
            self.failed_b = False

        def list_attachments(self, issue_key):
            assert issue_key == "SH-1"
            return list(self.remote)

        def upload_attachment(
            self, issue_key, attachment, *, cancellation=None
        ):
            self.uploaded.append(
                (
                    issue_key,
                    attachment.source_id,
                    attachment.upload_filename,
                )
            )
            if attachment.source_id == "b" and not self.failed_b:
                self.failed_b = True
                raise RuntimeError("second upload failed once")
            self.remote.append(
                {
                    "filename": attachment.upload_filename,
                    "size": attachment.size,
                }
            )
            return {"filename": attachment.upload_filename}

    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first = attachment(
        first_dir,
        "same.log",
        b"same",
        source_id="a",
        upload_filename="same--a.log",
    )
    second = attachment(
        second_dir,
        "same.log",
        b"same",
        source_id="b",
        upload_filename="same--b.log",
    )
    client = SourceClient()
    service = CreateIssueService(client)
    result = service.create_issue(
        request(
            first,
            second,
        )
    )

    assert [
        (item.source_id, item.filename, item.state)
        for item in result.attachment_results
    ] == [
        ("a", "same.log", "uploaded"),
        ("b", "same.log", "failed"),
    ]
    retried = service.sync_attachments(
        "SH-1",
        (second,),
        prior_results=(result.attachment_results[0],),
    )
    assert [
        (item.source_id, item.filename, item.state)
        for item in retried.results
    ] == [
        ("a", "same.log", "uploaded"),
        ("b", "same.log", "uploaded"),
    ]
    assert client.uploaded == [
        ("SH-1", "a", "same--a.log"),
        ("SH-1", "b", "same--b.log"),
        ("SH-1", "b", "same--b.log"),
    ]
