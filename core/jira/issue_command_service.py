from __future__ import annotations

from core.jira.attachments import (
    AttachmentCancellation,
    AttachmentSyncResult,
    AttachmentTransferResult,
    AttachmentUploadCancelled,
    CreateIssueAttachment,
    JiraAttachmentMetadata,
)
from core.jira.commands import CreateIssueCommand, CreateIssueResult
from core.jira.domain import IssueRef
from core.jira.mapper import JiraIssueMapper
from core.jira.repository import IssueRepository


class IssueCommandService:
    def __init__(self, gateway, *, browse_base_url: str = "") -> None:
        self._gateway = gateway
        self._repository = IssueRepository(gateway, JiraIssueMapper(browse_base_url))

    def check_issue(self, command: CreateIssueCommand) -> IssueRef | None:
        return self._repository.find_for_source(command)

    def check_issue_by_external_url(self, *, project_key: str, external_url: str) -> IssueRef | None:
        return self._repository.find_for_external_url(project_key, external_url)

    def create_issue(self, command: CreateIssueCommand) -> CreateIssueResult:
        try:
            existing = self.check_issue(command)
        except Exception as exc:
            return CreateIssueResult(False, "create_failed", issue_error=str(exc) or type(exc).__name__)
        if existing:
            attachment_sync = self.sync_attachments(existing.key, command.attachments)
            return CreateIssueResult(False, "duplicate", existing, attachment_state=attachment_sync.state, attachment_results=attachment_sync.results)
        try:
            created = self._repository.create(command)
        except Exception as exc:
            return CreateIssueResult(False, "create_failed", issue_error=str(exc) or type(exc).__name__)
        attachment_sync = self.sync_attachments(created.key, command.attachments)
        return CreateIssueResult(True, "created", created, attachment_state=attachment_sync.state, attachment_results=attachment_sync.results)

    def attachment_metadata(self) -> JiraAttachmentMetadata:
        try:
            return self._gateway.attachment_metadata()
        except Exception:
            return JiraAttachmentMetadata(False, None, None)

    def sync_attachments(
        self,
        issue_key: str,
        attachments: tuple[CreateIssueAttachment, ...],
        *,
        metadata: JiraAttachmentMetadata | None = None,
        prior_results: tuple[AttachmentTransferResult, ...] = (),
        cancellation: AttachmentCancellation | None = None,
    ) -> AttachmentSyncResult:
        if not attachments:
            return AttachmentSyncResult(_attachment_state(prior_results), prior_results)
        metadata = metadata or self.attachment_metadata()
        if cancellation is not None and cancellation.cancelled:
            results = prior_results + _cancelled_results(attachments)
            return AttachmentSyncResult(_attachment_state(results), results)
        if metadata.enabled is False:
            results = prior_results + tuple(
                AttachmentTransferResult(item.source_id, item.filename, item.size, "failed", "jira_attachments_disabled", retryable=False)
                for item in attachments
            )
            return AttachmentSyncResult(_attachment_state(results), results)
        try:
            remote = self._gateway.list_attachments(issue_key)
        except Exception as exc:
            results = prior_results + tuple(
                AttachmentTransferResult(item.source_id, item.filename, item.size, "failed", "jira_list_failed", {"detail": str(exc) or type(exc).__name__, "error_type": type(exc).__name__}, True)
                for item in attachments
            )
            return AttachmentSyncResult(_attachment_state(results), results)
        existing: dict[str, set[int]] = {}
        for item in remote:
            filename = str(item.get("filename") or "")
            try:
                size = int(item.get("size"))
            except (TypeError, ValueError):
                continue
            if filename:
                existing.setdefault(filename, set()).add(size)
        results = list(prior_results)
        for index, attachment in enumerate(attachments):
            if cancellation is not None and cancellation.cancelled:
                results.extend(_cancelled_results(attachments[index:]))
                break
            if metadata.upload_limit is not None and attachment.size > metadata.upload_limit:
                results.append(AttachmentTransferResult(attachment.source_id, attachment.filename, attachment.size, "oversized", "attachment_oversized", {"actual_bytes": attachment.size, "limit_bytes": metadata.upload_limit}, False))
                continue
            if attachment.upload_filename in existing:
                state = "already_present" if attachment.size in existing[attachment.upload_filename] else "failed"
                code = "" if state == "already_present" else "jira_existing_size_conflict"
                results.append(AttachmentTransferResult(attachment.source_id, attachment.filename, attachment.size, state, code, retryable=False))
                continue
            try:
                self._gateway.upload_attachment(issue_key, attachment, cancellation=cancellation)
                existing[attachment.upload_filename] = {attachment.size}
            except AttachmentUploadCancelled:
                results.extend(_cancelled_results(attachments[index:]))
                break
            except Exception as exc:
                results.append(AttachmentTransferResult(attachment.source_id, attachment.filename, attachment.size, "failed", "jira_upload_failed", {"detail": str(exc) or type(exc).__name__, "error_type": type(exc).__name__}, True))
            else:
                results.append(AttachmentTransferResult(attachment.source_id, attachment.filename, attachment.size, "uploaded"))
        frozen = tuple(results)
        return AttachmentSyncResult(_attachment_state(frozen), frozen)


def _attachment_state(results: tuple[AttachmentTransferResult, ...]) -> str:
    if not results:
        return "none"
    if any(item.state == "failed" for item in results):
        return "partial_failed"
    if any(item.state == "oversized" for item in results):
        return "oversized"
    return "complete"


def _cancelled_results(attachments: tuple[CreateIssueAttachment, ...]) -> tuple[AttachmentTransferResult, ...]:
    return tuple(AttachmentTransferResult(item.source_id, item.filename, item.size, "failed", "upload_cancelled", retryable=True) for item in attachments)
