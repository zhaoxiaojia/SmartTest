import asyncio
from pathlib import Path
from threading import Event
import time

import pytest

from support.jira_integration.core.create_schema import (
    CreateFieldControl,
    CreateFieldSchema,
)
from support.jira_integration.core.models import (
    AttachmentSyncResult,
    AttachmentTransferResult,
    CreateIssueAttachment,
    CreateIssueResult,
    JiraAttachmentMetadata,
)
from support.jira_integration.core.third_party_bug import ThirdPartyBugAttachment
from tool.SmartHome.redmine.attachment_transfer import duplicate_upload_filename
from tool.SmartHome.redmine.clone_controller import RedmineCloneController
from tool.SmartHome.redmine.clone_draft import CloneDraft, CloneDraftField


class IssueOwner:
    def __init__(self):
        self.results = []

    def record_clone_results(self, resolved):
        self.results.append(resolved)


def draft(issue_id="1", *, required_value="ready", source_attachments=()):
    return CloneDraft(
        source_id=issue_id,
        source_url=f"https://redmine/issues/{issue_id}",
        fields=(
            CloneDraftField(
                CreateFieldSchema(
                    "summary", "Summary", True, CreateFieldControl.TEXT
                ),
                required_value,
                "" if required_value else "Summary is required",
            ),
            CloneDraftField(
                CreateFieldSchema(
                    "reporter", "Reporter", True, CreateFieldControl.USER
                ),
                "alice",
            ),
            CloneDraftField(
                CreateFieldSchema(
                    "labels", "Labels", False, CreateFieldControl.MULTI
                ),
                [],
            ),
            CloneDraftField(
                CreateFieldSchema(
                    "attachment", "Attachment links", False, CreateFieldControl.TEXT
                ),
                f"https://redmine/issues/{issue_id}",
            ),
        ),
        source_attachments=tuple(source_attachments),
    )


def records(*drafts):
    return [
        {
            "draft": item,
            "error": "",
            "errorFieldId": "",
            "result": None,
        }
        for item in drafts
    ]


def test_selection_rejects_cloned_rows_and_preserves_source_order():
    controller = RedmineCloneController(IssueOwner())
    rows = [
        {"id": "3", "cloneStatus": "not_cloned"},
        {"id": "1", "cloneStatus": "cloned"},
        {"id": "2", "cloneStatus": "not_cloned"},
    ]

    assert controller.begin_selection()
    controller.toggle_selection("2", True, rows)
    controller.toggle_selection("1", True, rows)
    controller.toggle_selection("3", True, rows)

    assert controller.snapshot.state == "selecting"
    assert controller.snapshot.selected_ids == ("3", "2")


def test_prepare_result_owns_visible_schema_projection_and_seeded_user_options():
    controller = RedmineCloneController(IssueOwner())

    controller.apply_result(
        "prepare", (records(draft()), {"alice": "Alice Reporter"})
    )

    snapshot = controller.snapshot
    assert snapshot.state == "editing"
    assert snapshot.loaded == 1
    assert [item["fieldId"] for item in snapshot.drafts[0]["fields"]] == [
        "summary",
        "reporter",
        "attachment",
    ]
    reporter = snapshot.drafts[0]["fields"][1]
    assert reporter["options"] == [
        {
            "value": "alice",
            "label": "Alice Reporter",
            "avatarUrl": "",
            "children": [],
        }
    ]


def test_local_validation_identifies_first_invalid_field_before_submit():
    controller = RedmineCloneController(IssueOwner())
    controller.apply_result("prepare", (records(draft(required_value="")), {}))

    assert controller.start_submit() is None
    assert controller.snapshot.state == "editing"
    assert controller.snapshot.first_invalid_issue_id == "1"
    assert controller.snapshot.first_invalid_field_id == "summary"

    assert controller.update_draft("1", "summary", "reviewed")
    assert controller.snapshot.first_invalid_issue_id == ""


def test_partial_success_patches_issue_owner_and_retry_selects_failed_only():
    owner = IssueOwner()
    submitted = []

    async def submit(batch):
        submitted.append([item["draft"].source_id for item in batch])
        return []

    controller = RedmineCloneController(owner, submit_records=submit)
    controller.apply_result(
        "prepare", (records(draft("1"), draft("2"), draft("3")), {})
    )
    created = CreateIssueResult(
        created=True, issue_key="SH-1", issue_url="https://jira/SH-1"
    )
    duplicate = CreateIssueResult(
        created=False,
        existing_key="SH-2",
        issue_url="https://jira/SH-2",
    )

    controller.apply_result(
        "submit",
        [
            ("1", created),
            ("2", duplicate),
            (
                "3",
                CreateIssueResult(
                    created=False,
                    issue_state="create_failed",
                    issue_error="offline",
                ),
            ),
        ],
    )

    assert controller.snapshot.state == "partial_failed"
    assert [item["state"] for item in controller.snapshot.drafts] == [
        "created",
        "duplicate",
        "failed",
    ]
    assert set(owner.results[0]) == {"1", "2"}
    operation = controller.retry_failed()
    assert operation is not None and operation.kind == "submit"
    assert controller.snapshot.state == "submitting"
    operation.awaitable.close()


def test_current_submit_owner_classifies_create_failure_and_continues_batch():
    owner = IssueOwner()

    class Service:
        def __init__(self):
            self.source_ids = []

        def check_issue_by_external_url(self, **_kwargs):
            return None

        def create_issue(self, request):
            self.source_ids.append(request.source_id)
            if request.source_id == "1":
                raise RuntimeError("offline")
            return CreateIssueResult(
                created=True,
                issue_state="created",
                issue_key="SH-2",
            )

    service = Service()
    controller = RedmineCloneController(
        owner,
        jira_dependencies=lambda: (object(), service, object()),
    )
    controller.apply_result(
        "prepare",
        (records(draft("1"), draft("2")), {}),
    )

    operation = controller.start_submit()
    controller.apply_result("submit", asyncio.run(operation.awaitable))

    assert service.source_ids == ["1", "2"]
    assert [item["state"] for item in controller.snapshot.drafts] == [
        "failed",
        "created",
    ]
    assert controller.snapshot.drafts[0]["error"] == "offline"
    assert controller.snapshot.state == "partial_failed"
    assert owner.results[0]["2"].key == "SH-2"


def test_user_result_replaces_search_hits_but_keeps_current_value_option():
    controller = RedmineCloneController(IssueOwner())
    controller.apply_result("prepare", (records(draft()), {"alice": "Alice"}))

    controller.apply_result(
        "users",
        (
            "1",
            "reporter",
            [
                {
                    "account": "bob",
                    "display_name": "Bob",
                    "avatar_url": "bob.png",
                }
            ],
        ),
    )

    options = controller.snapshot.drafts[0]["fields"][1]["options"]
    assert [item["value"] for item in options] == ["bob", "alice"]


def test_created_issue_with_attachment_failure_is_cloned_and_retry_does_not_recreate(
    tmp_path,
):
    owner = IssueOwner()
    sources = (
        ThirdPartyBugAttachment(
            id="a",
            filename="same.log",
            download_url="https://redmine/a.log",
        ),
        ThirdPartyBugAttachment(
            id="b",
            filename="same.log",
            download_url="https://redmine/b.log",
        ),
    )
    closed = []
    downloads = []

    async def download(attachments, metadata, *, duplicate_filenames):
        attachments = tuple(attachments)
        downloads.append(
            (
                [item.id for item in attachments],
                metadata.upload_limit,
                set(duplicate_filenames),
            )
        )
        staged = []
        for item in attachments:
            path = tmp_path / f"{len(downloads)}-{item.id}.log"
            path.write_bytes(item.id.encode())
            staged.append(
                CreateIssueAttachment(
                    source_id=item.id,
                    filename=item.filename,
                    upload_filename=(
                        duplicate_upload_filename(item.filename, item.id)
                        if item.filename in duplicate_filenames
                        else item.filename
                    ),
                    path=path,
                )
            )

        class Batch:
            attachments = tuple(staged)
            results = ()

            def close(self):
                closed.append(True)

        return Batch()

    class Service:
        def __init__(self):
            self.create_calls = 0
            self.sync_calls = 0

        def create_issue(self, request):
            self.create_calls += 1
            assert request.attachments == ()
            return CreateIssueResult(
                created=True,
                issue_state="created",
                issue_key="SH-1",
                issue_url="https://jira/SH-1",
            )

        def check_issue_by_external_url(self, **_kwargs):
            return None

        def attachment_metadata(self):
            return JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=100
            )

        def sync_attachments(
            self,
            issue_key,
            attachments,
            *,
            metadata,
            prior_results=(),
            cancellation=None,
        ):
            assert issue_key == "SH-1"
            self.sync_calls += 1
            if self.sync_calls == 1:
                assert [item.source_id for item in attachments] == ["a", "b"]
                assert [item.upload_filename for item in attachments] == [
                    duplicate_upload_filename("same.log", "a"),
                    duplicate_upload_filename("same.log", "b"),
                ]
                return AttachmentSyncResult(
                    state="partial_failed",
                    results=(
                            AttachmentTransferResult(
                            source_id="a",
                            filename="same.log",
                            size=1,
                            state="uploaded",
                        ),
                            AttachmentTransferResult(
                            source_id="b",
                            filename="same.log",
                            size=1,
                            state="failed",
                            reason_code="jira_upload_failed",
                            reason_args={"detail": "offline"},
                            retryable=True,
                        ),
                    ),
                )
            assert [item.source_id for item in attachments] == ["b"]
            assert attachments[0].upload_filename == duplicate_upload_filename(
                "same.log", "b"
            )
            return AttachmentSyncResult(
                state="complete",
                    results=(
                            AttachmentTransferResult(
                            source_id="b",
                            filename="same.log",
                            size=1,
                            state="uploaded",
                        ),
                    ),
            )

    service = Service()
    controller = RedmineCloneController(
        owner,
        jira_dependencies=lambda: (object(), service, object()),
        download_attachments=download,
    )
    controller.apply_result(
        "prepare", (records(draft(source_attachments=sources)), {})
    )

    first = controller.start_submit()
    controller.apply_result("submit", asyncio.run(first.awaitable))

    first_draft = controller.snapshot.drafts[0]
    assert first_draft["state"] == "created"
    assert first_draft["key"] == "SH-1"
    assert first_draft["attachmentState"] == "partial_failed"
    assert first_draft["attachmentWarnings"][0]["sourceId"] == "b"
    assert controller.snapshot.state == "partial_failed"
    assert owner.results[0]["1"].key == "SH-1"
    assert service.create_calls == 1
    assert closed == [True]

    retry = controller.retry_failed()
    controller.apply_result("submit", asyncio.run(retry.awaitable))

    retried = controller.snapshot.drafts[0]
    assert retried["state"] == "created"
    assert retried["attachmentState"] == "complete"
    assert retried["attachmentWarnings"] == []
    assert controller.snapshot.state == "completed"
    assert service.create_calls == 1
    assert service.sync_calls == 2
    assert downloads == [
        (["a", "b"], 100, {"same.log"}),
        (["b"], 100, {"same.log"}),
    ]
    assert closed == [True, True]


def test_oversized_attachment_warns_without_failing_created_issue():
    owner = IssueOwner()
    payload = CreateIssueResult(
        created=True,
        issue_state="created",
        issue_key="SH-1",
        issue_url="https://jira/SH-1",
        attachment_state="oversized",
        attachment_results=(
            AttachmentTransferResult(
                source_id="large-id",
                filename="large.log",
                size=10,
                state="oversized",
                reason_code="attachment_oversized",
                reason_args={"actual_bytes": 10, "limit_bytes": 5},
                retryable=False,
            ),
        ),
    )
    controller = RedmineCloneController(owner)
    controller.apply_result("prepare", (records(draft()), {}))

    controller.apply_result("submit", [("1", payload)])

    visible = controller.snapshot.drafts[0]
    assert visible["state"] == "created"
    assert visible["attachmentState"] == "oversized"
    assert visible["attachmentWarnings"][0]["filename"] == "large.log"
    assert controller.snapshot.state == "completed"
    assert owner.results[0]["1"].key == "SH-1"


def test_temp_cleanup_failure_preserves_created_issue_and_adds_warning(
    tmp_path, monkeypatch
):
    source = ThirdPartyBugAttachment(
        id="a",
        filename="trace.log",
        download_url="https://redmine/trace.log",
    )
    path = tmp_path / "trace.log"
    path.write_bytes(b"trace")
    logs = []
    monkeypatch.setattr(
        "tool.SmartHome.redmine.clone_controller.smart_log",
        lambda message, **kwargs: logs.append((message, kwargs)),
        raising=False,
    )

    class Batch:
        attachments = (
            CreateIssueAttachment(
                source_id="a", filename="trace.log", path=path
            ),
        )
        results = ()

        def close(self):
            raise OSError("cleanup denied")

    async def download(
        _attachments, _metadata, *, duplicate_filenames
    ):
        assert duplicate_filenames == set()
        return Batch()

    class Service:
        def check_issue_by_external_url(self, **_kwargs):
            return None

        def create_issue(self, _request):
            return CreateIssueResult(
                created=True,
                issue_state="created",
                issue_key="SH-1",
                issue_url="https://jira/SH-1",
            )

        def attachment_metadata(self):
            return JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=100
            )

        def sync_attachments(self, *_args, **_kwargs):
            return AttachmentSyncResult(
                state="complete",
                results=(
                    AttachmentTransferResult(
                        source_id="a",
                        filename="trace.log",
                        size=5,
                        state="uploaded",
                    ),
                ),
            )

    owner = IssueOwner()
    controller = RedmineCloneController(
        owner,
        jira_dependencies=lambda: (object(), Service(), object()),
        download_attachments=download,
    )
    controller.apply_result(
        "prepare",
        (records(draft(source_attachments=(source,))), {}),
    )

    operation = controller.start_submit()
    controller.apply_result("submit", asyncio.run(operation.awaitable))

    visible = controller.snapshot.drafts[0]
    assert visible["state"] == "created"
    assert visible["key"] == "SH-1"
    assert visible["attachmentWarnings"][0]["reasonCode"] == "temp_cleanup_failed"
    assert visible["attachmentWarnings"][0]["retryable"] is False
    assert controller.snapshot.state == "completed"
    assert owner.results[0]["1"].key == "SH-1"
    assert logs and logs[0][1]["level"] == "warning"


def test_cancel_timeout_defers_cleanup_until_blocking_upload_finishes(
    tmp_path, monkeypatch
):
    source = ThirdPartyBugAttachment(
        id="a",
        filename="trace.log",
        download_url="https://redmine/trace.log",
    )
    path = tmp_path / "trace.log"
    path.write_bytes(b"trace")
    entered = Event()
    release = Event()
    cleaned = Event()
    early_cleanup = Event()
    logs = []
    monkeypatch.setattr(
        "tool.SmartHome.redmine.clone_controller.smart_log",
        lambda message, **kwargs: logs.append((message, kwargs)),
    )

    class Batch:
        attachments = (
            CreateIssueAttachment(
                source_id="a", filename="trace.log", path=path
            ),
        )
        results = ()

        def close(self):
            if not release.is_set():
                early_cleanup.set()
            path.unlink(missing_ok=True)
            cleaned.set()

    async def download(
        _attachments, _metadata, *, duplicate_filenames
    ):
        assert duplicate_filenames == set()
        return Batch()

    class Service:
        def check_issue_by_external_url(self, **_kwargs):
            return None

        def create_issue(self, _request):
            return CreateIssueResult(
                created=True,
                issue_state="created",
                issue_key="SH-1",
            )

        def attachment_metadata(self):
            return JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=100
            )

        def sync_attachments(self, *_args, **_kwargs):
            entered.set()
            release.wait(timeout=2)
            return AttachmentSyncResult(state="complete")

    async def cancel_during_blocking_upload():
        controller = RedmineCloneController(
            IssueOwner(),
            jira_dependencies=lambda: (object(), Service(), object()),
            download_attachments=download,
            attachment_cancel_wait=0.02,
        )
        controller.apply_result(
            "prepare",
            (records(draft(source_attachments=(source,))), {}),
        )
        operation = controller.start_submit()
        task = asyncio.create_task(operation.awaitable)
        assert await asyncio.to_thread(entered.wait, 1)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return time.monotonic() - started

    elapsed = asyncio.run(cancel_during_blocking_upload())
    assert elapsed < 0.25
    assert not cleaned.is_set()
    assert not early_cleanup.is_set()
    assert path.exists()
    assert any("cancellation reached timeout" in item[0] for item in logs)

    release.set()
    assert cleaned.wait(timeout=1)
    assert not early_cleanup.is_set()
    assert not path.exists()
