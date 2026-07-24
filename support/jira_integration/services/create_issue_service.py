from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from support.jira_integration.core.errors import JiraRequestError
from support.jira_integration.core.models import (
    AttachmentCancellation,
    AttachmentSyncResult,
    AttachmentTransferResult,
    AttachmentUploadCancelled,
    CreateIssueAttachment,
    CreateIssueRequest,
    CreateIssueResult,
    ExistingIssue,
    JiraAttachmentMetadata,
)

if TYPE_CHECKING:
    from support.jira_integration.transport.client import JiraClient


class CreateIssueService:
    def __init__(self, client: "JiraClient", *, browse_base_url: str = ""):
        self._client = client
        self._browse_base_url = browse_base_url.rstrip("/")

    def check_issue(self, request: CreateIssueRequest) -> ExistingIssue | None:
        if not request.source_system or not request.source_id:
            return None
        page = self._client.search_page(
            self._third_party_jql(request),
            start_at=0,
            max_results=1,
            fields=["summary"],
        )
        return self._existing_issue(page.issues[0]) if page.issues else None

    def check_issue_by_external_url(self, *, project_key: str, external_url: str) -> ExistingIssue | None:
        clean_url = str(external_url or "").strip()
        if not project_key or not clean_url:
            return None
        for jql in self._external_url_jqls(project_key=project_key, external_url=clean_url):
            try:
                page = self._client.search_page(jql, start_at=0, max_results=1, fields=["summary"])
            except JiraRequestError:
                continue
            if page.issues:
                return self._existing_issue(page.issues[0])
        return None

    def create_issue(self, request: CreateIssueRequest) -> CreateIssueResult:
        try:
            existing = self.check_issue(request)
        except Exception as exc:
            return CreateIssueResult(
                created=False,
                issue_state="create_failed",
                issue_error=str(exc) or type(exc).__name__,
            )
        if existing:
            attachment_sync = self.sync_attachments(
                existing.key, request.attachments
            )
            return CreateIssueResult(
                created=False,
                issue_state="duplicate",
                existing_key=existing.key,
                issue_url=existing.web_url,
                raw=existing.raw,
                attachment_state=attachment_sync.state,
                attachment_results=attachment_sync.results,
            )
        try:
            created = self._client.create_issue(self._payload(request))
        except Exception as exc:
            return CreateIssueResult(
                created=False,
                issue_state="create_failed",
                issue_error=str(exc) or type(exc).__name__,
            )
        issue_key = str(created.get("key", ""))
        attachment_sync = self.sync_attachments(issue_key, request.attachments)
        return CreateIssueResult(
            created=True,
            issue_state="created",
            issue_key=issue_key,
            issue_id=str(created.get("id", "")),
            issue_url=(
                f"{self._browse_base_url}/browse/{issue_key}"
                if self._browse_base_url and issue_key
                else str(created.get("self", ""))
            ),
            raw=created,
            attachment_state=attachment_sync.state,
            attachment_results=attachment_sync.results,
        )

    def attachment_metadata(self) -> JiraAttachmentMetadata:
        try:
            return self._client.attachment_metadata()
        except Exception:
            return JiraAttachmentMetadata(
                available=False,
                enabled=None,
                upload_limit=None,
            )

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
            return AttachmentSyncResult(
                state=_attachment_state(prior_results),
                results=prior_results,
            )
        metadata = metadata or self.attachment_metadata()
        if cancellation is not None and cancellation.cancelled:
            results = prior_results + _cancelled_results(attachments)
            return AttachmentSyncResult(
                state=_attachment_state(results),
                results=results,
            )
        if metadata.enabled is False:
            results = prior_results + tuple(
                AttachmentTransferResult(
                    source_id=attachment.source_id,
                    filename=attachment.filename,
                    size=attachment.size,
                    state="failed",
                    reason_code="jira_attachments_disabled",
                    retryable=False,
                )
                for attachment in attachments
            )
            return AttachmentSyncResult(
                state=_attachment_state(results),
                results=results,
            )
        existing: dict[str, set[int]] = {}
        try:
            remote_attachments = self._client.list_attachments(issue_key)
        except Exception as exc:
            results = prior_results + tuple(
                AttachmentTransferResult(
                    source_id=attachment.source_id,
                    filename=attachment.filename,
                    size=attachment.size,
                    state="failed",
                    reason_code="jira_list_failed",
                    reason_args={
                        "detail": str(exc) or type(exc).__name__,
                        "error_type": type(exc).__name__,
                    },
                    retryable=True,
                )
                for attachment in attachments
            )
            return AttachmentSyncResult(
                state=_attachment_state(results),
                results=results,
            )
        for item in remote_attachments:
            filename = str(item.get("filename") or "")
            if filename:
                try:
                    size = int(item.get("size"))
                except (TypeError, ValueError):
                    continue
                existing.setdefault(filename, set()).add(size)
        results = list(prior_results)
        for index, attachment in enumerate(attachments):
            if cancellation is not None and cancellation.cancelled:
                results.extend(_cancelled_results(attachments[index:]))
                break
            if (
                metadata.upload_limit is not None
                and attachment.size > metadata.upload_limit
            ):
                results.append(
                    AttachmentTransferResult(
                        source_id=attachment.source_id,
                        filename=attachment.filename,
                        size=attachment.size,
                        state="oversized",
                        reason_code="attachment_oversized",
                        reason_args={
                            "actual_bytes": attachment.size,
                            "limit_bytes": metadata.upload_limit,
                        },
                        retryable=False,
                    )
                )
                continue
            if attachment.upload_filename in existing:
                if attachment.size not in existing[attachment.upload_filename]:
                    results.append(
                        AttachmentTransferResult(
                            source_id=attachment.source_id,
                            filename=attachment.filename,
                            size=attachment.size,
                            state="failed",
                            reason_code="jira_existing_size_conflict",
                            retryable=False,
                        )
                    )
                else:
                    results.append(
                        AttachmentTransferResult(
                            source_id=attachment.source_id,
                            filename=attachment.filename,
                            size=attachment.size,
                            state="already_present",
                        )
                    )
                continue
            try:
                self._client.upload_attachment(
                    issue_key,
                    attachment,
                    cancellation=cancellation,
                )
                existing[attachment.upload_filename] = {attachment.size}
            except AttachmentUploadCancelled:
                results.extend(_cancelled_results(attachments[index:]))
                break
            except Exception as exc:
                results.append(
                    AttachmentTransferResult(
                        source_id=attachment.source_id,
                        filename=attachment.filename,
                        size=attachment.size,
                        state="failed",
                        reason_code="jira_upload_failed",
                        reason_args={
                            "detail": str(exc) or type(exc).__name__,
                            "error_type": type(exc).__name__,
                        },
                        retryable=True,
                    )
                )
            else:
                results.append(
                    AttachmentTransferResult(
                        source_id=attachment.source_id,
                        filename=attachment.filename,
                        size=attachment.size,
                        state="uploaded",
                    )
                )
        frozen_results = tuple(results)
        return AttachmentSyncResult(
            state=_attachment_state(frozen_results),
            results=frozen_results,
        )

    def _payload(self, request: CreateIssueRequest) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": request.project_key},
            "issuetype": {"name": request.issue_type},
            "summary": request.summary,
            "description": self._description(request),
            "labels": self._labels(request),
        }
        if request.priority:
            fields["priority"] = self._field_value(
                request.priority,
                request.field_controls.get("priority", ""),
                default_kind="name",
            )
        if request.assignee:
            fields["assignee"] = {"name": request.assignee}
        if request.components:
            control = request.field_controls.get("components", "")
            fields["components"] = (
                self._field_value(list(request.components), control)
                if control
                else [{"name": component} for component in request.components if component]
            )
        fields.update(
            {
                key: self._field_value(value, request.field_controls.get(key, ""))
                for key, value in request.extra_fields.items()
                if value not in (None, "", [], {})
            }
        )
        return {"fields": fields}

    @staticmethod
    def _field_value(value: Any, control: str, *, default_kind: str = "") -> Any:
        if control in {"text", "multiline"}:
            return value
        if control == "single":
            return {"id": str(value)}
        if control == "multi":
            return [{"id": str(item)} for item in value if item]
        if control == "cascade":
            payload = {"id": str(value.get("parent") or "")}
            if value.get("child"):
                payload["child"] = {"id": str(value["child"])}
            return payload
        if control == "user":
            return {"name": str(value)}
        if default_kind:
            return {default_kind: value}
        return value

    def _labels(self, request: CreateIssueRequest) -> list[str]:
        labels = list(request.labels)
        if request.source_system and request.source_id:
            labels.extend(["clone_external", f"source_{_safe_label(request.source_system)}", self._source_id_label(request)])
        return list(dict.fromkeys(label for label in labels if label))

    def _description(self, request: CreateIssueRequest) -> str:
        if request.description_includes_source_identity:
            return request.description
        lines = [request.description]
        if request.source_system and request.source_id:
            lines.extend(["", f"Source: {request.source_system}", f"Source ID: {request.source_id}"])
            if request.source_url:
                lines.append(f"Source URL: {request.source_url}")
        return "\n".join(lines).strip()

    def _third_party_jql(self, request: CreateIssueRequest) -> str:
        return (
            f'project = "{_jql_quote(request.project_key)}" '
            f'AND labels = "source_{_safe_label(request.source_system)}" '
            f'AND labels = "{self._source_id_label(request)}"'
        )

    def _external_url_jqls(self, *, project_key: str, external_url: str) -> list[str]:
        project = _jql_quote(project_key)
        url = _jql_quote(external_url)
        return [
            f'project = "{project}" AND "Attachment links" = "{url}"',
            f'project = "{project}" AND text ~ "{url}"',
        ]

    @staticmethod
    def _source_id_label(request: CreateIssueRequest) -> str:
        return f"{_safe_label(request.source_system)}_{_safe_label(request.source_id)}"

    def _existing_issue(self, issue: dict[str, Any]) -> ExistingIssue:
        key = str(issue.get("key", ""))
        fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
        return ExistingIssue(
            key=key,
            web_url=f"{self._browse_base_url}/browse/{key}" if self._browse_base_url and key else "",
            summary=str(fields.get("summary", "")),
            raw=issue,
        )


def _safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._") or "unknown"


def _jql_quote(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _attachment_state(
    results: tuple[AttachmentTransferResult, ...],
) -> str:
    if not results:
        return "none"
    if any(item.state == "failed" for item in results):
        return "partial_failed"
    if any(item.state == "oversized" for item in results):
        return "oversized"
    return "complete"


def _cancelled_results(
    attachments: tuple[CreateIssueAttachment, ...],
) -> tuple[AttachmentTransferResult, ...]:
    return tuple(
        AttachmentTransferResult(
            source_id=attachment.source_id,
            filename=attachment.filename,
            size=attachment.size,
            state="failed",
            reason_code="upload_cancelled",
            retryable=True,
        )
        for attachment in attachments
    )
