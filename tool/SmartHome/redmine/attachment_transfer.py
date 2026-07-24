from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from support.jira_integration.core.models import (
    AttachmentTransferResult,
    CreateIssueAttachment,
    JiraAttachmentMetadata,
)


_SIZE_FACTORS = {
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024**2,
    "mib": 1024**2,
    "gb": 1024**3,
    "gib": 1024**3,
}


def parse_redmine_attachment_size(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("bytes")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    text = str(value or "").strip().replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([A-Za-z]+)", text)
    if match is None:
        return None
    factor = _SIZE_FACTORS.get(match.group(2).casefold())
    if factor is None:
        return None
    return int(float(match.group(1)) * factor)


@dataclass
class StagedRedmineAttachmentBatch:
    directory: Path
    attachments: tuple[CreateIssueAttachment, ...]
    results: tuple[AttachmentTransferResult, ...]
    _temporary_directory: tempfile.TemporaryDirectory

    def close(self) -> None:
        self._temporary_directory.cleanup()


class RedmineAttachmentTransfer:
    def __init__(self, *, temp_root: Path | None = None):
        self._temp_root = temp_root

    async def stage(
        self,
        page,
        attachments: Iterable[Any],
        metadata: JiraAttachmentMetadata,
        *,
        duplicate_filenames: Iterable[str] = (),
    ) -> StagedRedmineAttachmentBatch:
        temporary_directory = tempfile.TemporaryDirectory(
            prefix="smarttest-redmine-attachments-",
            dir=self._temp_root,
        )
        directory = Path(temporary_directory.name)
        staged: list[CreateIssueAttachment] = []
        results: list[AttachmentTransferResult] = []
        duplicate_filenames = set(duplicate_filenames)
        try:
            for index, attachment in enumerate(attachments):
                source_id = str(attachment.id or "").strip()
                filename = str(attachment.filename or "").strip()
                source_size = parse_redmine_attachment_size(attachment.size)
                if metadata.enabled is False:
                    results.append(
                        AttachmentTransferResult(
                            source_id=source_id,
                            filename=filename,
                            size=source_size,
                            state="failed",
                            reason_code="jira_attachments_disabled",
                            retryable=False,
                        )
                    )
                    continue
                if (
                    metadata.upload_limit is not None
                    and source_size is not None
                    and source_size > metadata.upload_limit
                ):
                    results.append(
                        _oversized_result(
                            source_id,
                            filename,
                            source_size,
                            metadata.upload_limit,
                        )
                    )
                    continue
                url = str(
                    attachment.download_url or attachment.detail_url or ""
                ).strip()
                if not url:
                    results.append(
                        AttachmentTransferResult(
                            source_id=source_id,
                            filename=filename,
                            size=source_size,
                            state="failed",
                            reason_code="source_url_missing",
                            retryable=False,
                        )
                    )
                    continue
                try:
                    response = await page.request.get(url)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    results.append(
                        _download_failure(
                            source_id, filename, source_size, exc
                        )
                    )
                    continue
                if not response.ok:
                    results.append(
                        AttachmentTransferResult(
                            source_id=source_id,
                            filename=filename,
                            size=source_size,
                            state="failed",
                            reason_code="source_http_error",
                            reason_args={
                                "status": _http_status_value(response.status)
                            },
                            retryable=True,
                        )
                    )
                    continue
                path = directory / f"{index:04d}.attachment"
                try:
                    path.write_bytes(await response.body())
                except asyncio.CancelledError:
                    path.unlink(missing_ok=True)
                    raise
                except Exception as exc:
                    path.unlink(missing_ok=True)
                    results.append(
                        _download_failure(
                            source_id, filename, source_size, exc
                        )
                    )
                    continue
                actual_size = path.stat().st_size
                if (
                    metadata.upload_limit is not None
                    and actual_size > metadata.upload_limit
                ):
                    path.unlink()
                    results.append(
                        _oversized_result(
                            source_id,
                            filename,
                            actual_size,
                            metadata.upload_limit,
                        )
                    )
                    continue
                try:
                    staged.append(
                        CreateIssueAttachment(
                            source_id=source_id,
                            filename=filename,
                            upload_filename=(
                                duplicate_upload_filename(filename, source_id)
                                if filename in duplicate_filenames
                                else filename
                            ),
                            path=path,
                        )
                    )
                except (TypeError, ValueError):
                    path.unlink(missing_ok=True)
                    results.append(
                        AttachmentTransferResult(
                            source_id=source_id,
                            filename=filename,
                            size=actual_size,
                            state="failed",
                            reason_code="source_file_invalid",
                            retryable=False,
                        )
                    )
            return StagedRedmineAttachmentBatch(
                directory=directory,
                attachments=tuple(staged),
                results=tuple(results),
                _temporary_directory=temporary_directory,
            )
        except BaseException:
            temporary_directory.cleanup()
            raise


def _download_failure(
    source_id: str,
    filename: str,
    size: int | None,
    error: Exception,
) -> AttachmentTransferResult:
    return AttachmentTransferResult(
        source_id=source_id,
        filename=filename,
        size=size,
        state="failed",
        reason_code="source_download_failed",
        reason_args={
            "detail": str(error) or type(error).__name__,
            "error_type": type(error).__name__,
        },
        retryable=True,
    )


def duplicate_upload_filename(filename: str, source_id: str) -> str:
    safe_source_id = re.sub(
        r"[^A-Za-z0-9._-]+", "_", str(source_id or "")
    ).strip("._-")
    safe_source_id = (safe_source_id or "source")[:32]
    digest = sha256(str(source_id or "").encode("utf-8")).hexdigest()[:8]
    dot = filename.rfind(".")
    has_extension = dot > 0
    stem = filename[:dot] if has_extension else filename
    extension = filename[dot:] if has_extension else ""
    return f"{stem}--{safe_source_id}-{digest}{extension}"


def _http_status_value(value: Any) -> int | str:
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _oversized_result(
    source_id: str,
    filename: str,
    size: int,
    upload_limit: int,
) -> AttachmentTransferResult:
    return AttachmentTransferResult(
        source_id=source_id,
        filename=filename,
        size=size,
        state="oversized",
        reason_code="attachment_oversized",
        reason_args={
            "actual_bytes": size,
            "limit_bytes": upload_limit,
        },
        retryable=False,
    )
