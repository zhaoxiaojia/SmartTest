import asyncio
from pathlib import Path

import pytest

from support.jira_integration.core.models import JiraAttachmentMetadata
from support.jira_integration.core.third_party_bug import ThirdPartyBugAttachment
from tool.SmartHome.redmine.attachment_transfer import (
    RedmineAttachmentTransfer,
    duplicate_upload_filename,
    parse_redmine_attachment_size,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", None),
        ("unknown", None),
        ("1 B", 1),
        ("1 KB", 1024),
        ("1.5 MB", 1572864),
        ("2,048 bytes", 2048),
        ({"bytes": 7}, 7),
        (7, 7),
        (-1, None),
    ],
)
def test_redmine_attachment_size_parsing(value, expected):
    assert parse_redmine_attachment_size(value) == expected


def test_staging_skips_trustworthy_oversized_source_and_cleans_batch(tmp_path):
    class Request:
        calls = []

        async def get(self, url):
            self.calls.append(url)
            raise AssertionError("oversized attachment must not download")

    page = type("Page", (), {"request": Request()})()
    source = ThirdPartyBugAttachment(
        id="1",
        filename="large.log",
        size="4 KB",
        download_url="https://redmine/large.log",
    )
    transfer = RedmineAttachmentTransfer(temp_root=tmp_path)

    batch = asyncio.run(
        transfer.stage(
            page,
            (source,),
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=1024
            ),
        )
    )
    directory = batch.directory
    assert Path(directory).is_dir()
    assert batch.attachments == ()
    assert batch.results[0].state == "oversized"
    assert batch.results[0].size == 4096
    batch.close()
    assert not Path(directory).exists()


def test_unknown_size_is_checked_after_file_download_and_failure_cleans(tmp_path):
    class Response:
        ok = True
        status = 200

        async def body(self):
            return b"12345"

    class Request:
        async def get(self, _url):
            return Response()

    page = type("Page", (), {"request": Request()})()
    source = ThirdPartyBugAttachment(
        id="1",
        filename="../unsafe.log",
        download_url="https://redmine/unsafe.log",
    )
    transfer = RedmineAttachmentTransfer(temp_root=tmp_path)

    batch = asyncio.run(
        transfer.stage(
            page,
            (source,),
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=4
            ),
        )
    )
    directory = Path(batch.directory)
    assert batch.attachments == ()
    assert batch.results[0].state == "oversized"
    assert batch.results[0].size == 5
    assert list(directory.iterdir()) == []
    batch.close()
    assert not directory.exists()


def test_downloaded_attachment_is_file_backed_and_batch_cleanup_removes_it(tmp_path):
    class Response:
        ok = True
        status = 200

        async def body(self):
            return b"downloaded"

    class Request:
        async def get(self, _url):
            return Response()

    page = type("Page", (), {"request": Request()})()
    source = ThirdPartyBugAttachment(
        id="1",
        filename="trace.log",
        size="not known",
        download_url="https://redmine/trace.log",
    )
    transfer = RedmineAttachmentTransfer(temp_root=tmp_path)
    batch = asyncio.run(
        transfer.stage(
            page,
            (source,),
            JiraAttachmentMetadata(
                available=False, enabled=None, upload_limit=None
            ),
        )
    )

    staged = batch.attachments[0]
    assert staged.filename == "trace.log"
    assert staged.path.read_bytes() == b"downloaded"
    assert staged.size == 10
    assert str(staged.path).startswith(str(batch.directory))
    directory = Path(batch.directory)
    batch.close()
    assert not directory.exists()


def test_http_failure_is_a_per_file_outcome_and_batch_cleanup_still_works(tmp_path):
    class Response:
        ok = False
        status = 500

    class Request:
        async def get(self, _url):
            return Response()

    page = type("Page", (), {"request": Request()})()
    source = ThirdPartyBugAttachment(
        id="1",
        filename="trace.log",
        download_url="https://redmine/trace.log",
    )

    batch = asyncio.run(
        RedmineAttachmentTransfer(temp_root=tmp_path).stage(
            page,
            (source,),
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=100
            ),
        )
    )

    assert batch.results[0].reason_code == "source_http_error"
    batch.close()
    assert list(tmp_path.iterdir()) == []


def test_cancelled_download_cleans_the_controlled_directory(tmp_path):
    started = asyncio.Event()

    class Response:
        ok = True
        status = 200

        async def body(self):
            started.set()
            await asyncio.Event().wait()

    class Request:
        async def get(self, _url):
            return Response()

    page = type("Page", (), {"request": Request()})()
    source = ThirdPartyBugAttachment(
        id="1",
        filename="trace.log",
        download_url="https://redmine/trace.log",
    )

    async def cancel_staging():
        task = asyncio.create_task(
            RedmineAttachmentTransfer(temp_root=tmp_path).stage(
                page,
                (source,),
                JiraAttachmentMetadata(
                    available=True, enabled=True, upload_limit=100
                ),
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_staging())

    assert list(tmp_path.iterdir()) == []


def test_staging_isolates_per_source_failures_and_preserves_prior_outcomes(
    tmp_path,
):
    class Response:
        def __init__(self, status, body=b"", error=None):
            self.status = status
            self.ok = status == 200
            self._body = body
            self._error = error

        async def body(self):
            if self._error:
                raise self._error
            return self._body

    class Request:
        async def get(self, url):
            if url.endswith("http.log"):
                return Response(500)
            if url.endswith("broken.log"):
                return Response(200, error=RuntimeError("connection reset"))
            return Response(200, body=b"ok")

    sources = (
        ThirdPartyBugAttachment(
            id="oversized-id",
            filename="same.log",
            size="10 B",
            download_url="https://redmine/oversized.log",
        ),
        ThirdPartyBugAttachment(
            id="missing-id",
            filename="same.log",
        ),
        ThirdPartyBugAttachment(
            id="http-id",
            filename="same.log",
            download_url="https://redmine/http.log",
        ),
        ThirdPartyBugAttachment(
            id="broken-id",
            filename="same.log",
            download_url="https://redmine/broken.log",
        ),
        ThirdPartyBugAttachment(
            id="ok-id",
            filename="same.log",
            download_url="https://redmine/ok.log",
        ),
    )

    batch = asyncio.run(
        RedmineAttachmentTransfer(temp_root=tmp_path).stage(
            type("Page", (), {"request": Request()})(),
            sources,
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=5
            ),
        )
    )

    assert [(item.source_id, item.state, item.reason_code) for item in batch.results] == [
        ("oversized-id", "oversized", "attachment_oversized"),
        ("missing-id", "failed", "source_url_missing"),
        ("http-id", "failed", "source_http_error"),
        ("broken-id", "failed", "source_download_failed"),
    ]
    assert batch.results[0].retryable is False
    assert [(item.source_id, item.filename) for item in batch.attachments] == [
        ("ok-id", "same.log")
    ]
    batch.close()


def test_malformed_http_status_isolated_to_its_source(tmp_path):
    class Response:
        def __init__(self, ok, status, body=b""):
            self.ok = ok
            self.status = status
            self._body = body

        async def body(self):
            return self._body

    class Request:
        async def get(self, url):
            if url.endswith("bad.log"):
                return Response(False, object())
            return Response(True, 200, b"ok")

    sources = (
        ThirdPartyBugAttachment(
            id="bad-id",
            filename="bad.log",
            download_url="https://redmine/bad.log",
        ),
        ThirdPartyBugAttachment(
            id="ok-id",
            filename="ok.log",
            download_url="https://redmine/ok.log",
        ),
    )

    batch = asyncio.run(
        RedmineAttachmentTransfer(temp_root=tmp_path).stage(
            type("Page", (), {"request": Request()})(),
            sources,
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=5
            ),
        )
    )

    assert [
        (item.source_id, item.reason_code) for item in batch.results
    ] == [("bad-id", "source_http_error")]
    assert [item.source_id for item in batch.attachments] == ["ok-id"]
    batch.close()


def test_duplicate_source_filenames_get_stable_safe_upload_names(tmp_path):
    class Response:
        ok = True
        status = 200

        async def body(self):
            return b"same"

    class Request:
        async def get(self, _url):
            return Response()

    sources = tuple(
        ThirdPartyBugAttachment(
            id=source_id,
            filename="same.log",
            download_url=f"https://redmine/{source_id}",
        )
        for source_id in ("a", "b/unsafe")
    )
    transfer = RedmineAttachmentTransfer(temp_root=tmp_path)
    batch = asyncio.run(
        transfer.stage(
            type("Page", (), {"request": Request()})(),
            sources,
            JiraAttachmentMetadata(
                available=True, enabled=True, upload_limit=10
            ),
            duplicate_filenames={"same.log"},
        )
    )

    assert [item.filename for item in batch.attachments] == [
        "same.log",
        "same.log",
    ]
    assert [item.upload_filename for item in batch.attachments] == [
        duplicate_upload_filename("same.log", "a"),
        duplicate_upload_filename("same.log", "b/unsafe"),
    ]
    assert len({item.upload_filename for item in batch.attachments}) == 2
    assert all(
        "/" not in item.upload_filename and "\r" not in item.upload_filename
        for item in batch.attachments
    )
    batch.close()
