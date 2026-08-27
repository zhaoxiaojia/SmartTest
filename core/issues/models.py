from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event
from typing import Any


@dataclass(frozen=True)
class SearchPage:
    issues: list[dict[str, Any]]
    start_at: int
    max_results: int
    total: int
    is_last: bool = False


@dataclass(frozen=True)
class IssueRecord:
    key: str
    id: str | None
    raw: dict[str, Any]
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JiraFieldMetadata:
    field_id: str
    name: str
    schema_type: str | None = None
    schema_items: str | None = None
    custom: bool = False
    custom_id: int | None = None
    schema_custom: str | None = None
    clause_names: tuple[str, ...] = ()
    navigable: bool = True
    searchable: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["clause_names"] = list(self.clause_names)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JiraFieldMetadata":
        return cls(
            field_id=str(data.get("field_id", "")),
            name=str(data.get("name", "")),
            schema_type=data.get("schema_type"),
            schema_items=data.get("schema_items"),
            custom=bool(data.get("custom", False)),
            custom_id=data.get("custom_id"),
            schema_custom=data.get("schema_custom"),
            clause_names=tuple(data.get("clause_names") or ()),
            navigable=bool(data.get("navigable", True)),
            searchable=bool(data.get("searchable", True)),
        )


@dataclass(frozen=True)
class JiraAttachmentMetadata:
    available: bool
    enabled: bool | None
    upload_limit: int | None

    def __post_init__(self):
        if self.upload_limit is not None and self.upload_limit < 0:
            raise ValueError("Attachment upload limit cannot be negative")


class AttachmentUploadCancelled(Exception):
    pass


class AttachmentCancellation:
    def __init__(self):
        self._event = Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise AttachmentUploadCancelled()


@dataclass(frozen=True)
class CreateIssueAttachment:
    filename: str
    path: Path
    source_id: str = ""
    upload_filename: str = ""

    def __post_init__(self):
        if not self.filename or any(character in self.filename for character in "\r\n"):
            raise ValueError("Attachment filename is invalid")
        upload_filename = self.upload_filename or self.filename
        if any(character in upload_filename for character in "\r\n"):
            raise ValueError("Attachment upload filename is invalid")
        path = Path(self.path)
        if not path.is_file():
            raise ValueError("Attachment path must be an existing regular file")
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "upload_filename", upload_filename)

    @property
    def size(self) -> int:
        return self.path.stat().st_size


@dataclass(frozen=True)
class AttachmentTransferResult:
    source_id: str
    filename: str
    size: int | None
    state: str
    reason_code: str = ""
    reason_args: dict[str, Any] = field(default_factory=dict)
    retryable: bool = False


@dataclass(frozen=True)
class AttachmentSyncResult:
    state: str
    results: tuple[AttachmentTransferResult, ...] = ()


@dataclass(frozen=True)
class CreateIssueRequest:
    project_key: str
    issue_type: str
    summary: str
    description: str = ""
    priority: str = ""
    assignee: str = ""
    labels: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    source_system: str = ""
    source_id: str = ""
    source_url: str = ""
    description_includes_source_identity: bool = False
    extra_fields: dict[str, Any] = field(default_factory=dict)
    field_controls: dict[str, str] = field(default_factory=dict)
    attachments: tuple[CreateIssueAttachment, ...] = ()


@dataclass(frozen=True)
class CreateIssueResult:
    created: bool
    issue_state: str = ""
    issue_key: str = ""
    issue_id: str = ""
    issue_url: str = ""
    existing_key: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    issue_error: str = ""
    attachment_state: str = "none"
    attachment_results: tuple[AttachmentTransferResult, ...] = ()

    def __post_init__(self):
        if not self.issue_state:
            object.__setattr__(
                self,
                "issue_state",
                "created" if self.created else ("duplicate" if self.existing_key else "create_failed"),
            )

@dataclass(frozen=True)
class ExistingIssue:
    key: str
    web_url: str = ""
    summary: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
