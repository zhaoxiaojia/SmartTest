from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any


@dataclass(frozen=True)
class JiraAttachmentMetadata:
    available: bool
    enabled: bool | None
    upload_limit: int | None

    def __post_init__(self) -> None:
        if self.upload_limit is not None and self.upload_limit < 0:
            raise ValueError("Attachment upload limit cannot be negative")


class AttachmentUploadCancelled(Exception):
    pass


class AttachmentCancellation:
    def __init__(self) -> None:
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

    def __post_init__(self) -> None:
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
