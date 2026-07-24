from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.core.models import (
    AttachmentCancellation,
    AttachmentUploadCancelled,
    CreateIssueAttachment,
    JiraAttachmentMetadata,
)
from support.jira_integration.transport.client import JiraClient, JiraClientConfig


def client():
    return JiraClient(
        JiraClientConfig("https://jira.example"),
        JiraBasicAuth("user", "password"),
    )


def test_multipart_upload_streams_file_with_content_length_and_safe_filename(
    monkeypatch, tmp_path
):
    jira = client()
    path = tmp_path / "report.txt"
    path.write_bytes(b"payload")
    seen = {}

    def request(method, url, **kwargs):
        seen.update(method=method, url=url, **kwargs)
        seen["body"] = b"".join(kwargs["data"])
        return type("Response", (), {"data": [{"id": "1"}]})()

    monkeypatch.setattr(jira, "_request", request)
    result = jira.upload_attachment(
        "SH-1", CreateIssueAttachment(filename='report "one".txt', path=path)
    )

    assert result == {"id": "1"}
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/rest/api/2/issue/SH-1/attachments")
    assert seen["headers"]["X-Atlassian-Token"] == "no-check"
    assert seen["headers"]["Content-Type"].startswith(
        "multipart/form-data; boundary="
    )
    assert int(seen["headers"]["Content-Length"]) == len(seen["body"])
    assert b'name="file"' in seen["body"]
    assert b'filename="report \\"one\\".txt"' in seen["body"]
    assert seen["body"].count(b"payload") == 1
    assert not isinstance(seen["data"], bytes)


def test_multipart_iterator_stops_cooperatively_when_cancelled(
    monkeypatch, tmp_path
):
    jira = client()
    path = tmp_path / "report.txt"
    path.write_bytes(b"x" * (128 * 1024))
    cancellation = AttachmentCancellation()

    def request(_method, _url, **kwargs):
        body = iter(kwargs["data"])
        assert next(body).startswith(b"--SmartTest-")
        cancellation.cancel()
        with pytest.raises(AttachmentUploadCancelled):
            next(body)
        raise AttachmentUploadCancelled()

    monkeypatch.setattr(jira, "_request", request)

    with pytest.raises(AttachmentUploadCancelled):
        jira.upload_attachment(
            "SH-1",
            CreateIssueAttachment(filename="report.txt", path=path),
            cancellation=cancellation,
        )


def test_actual_urllib_http_transport_sends_iterable_body_once(tmp_path):
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            received["content_length"] = length
            received["body"] = self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'[{"id":"1"}]')

        def log_message(self, _format, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = tmp_path / "report.txt"
    path.write_bytes(b"unique-payload")
    jira = JiraClient(
        JiraClientConfig(
            f"http://127.0.0.1:{server.server_port}",
            timeout_seconds=2,
        ),
        JiraBasicAuth("user", "password"),
    )
    try:
        result = jira.upload_attachment(
            "SH-1",
            CreateIssueAttachment(filename="report.txt", path=path),
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result == {"id": "1"}
    assert received["content_length"] == len(received["body"])
    assert received["body"].count(b"unique-payload") == 1


def test_attachment_metadata_preserves_disabled_unknown_and_known_limit(monkeypatch):
    jira = client()
    payloads = iter(
        [
            {"enabled": False},
            {"enabled": True},
            {"enabled": True, "uploadLimit": 123},
        ]
    )

    monkeypatch.setattr(
        jira,
        "_request",
        lambda *_args, **_kwargs: type(
            "Response", (), {"data": next(payloads)}
        )(),
    )

    assert jira.attachment_metadata() == JiraAttachmentMetadata(
        available=True, enabled=False, upload_limit=None
    )
    assert jira.attachment_metadata() == JiraAttachmentMetadata(
        available=True, enabled=True, upload_limit=None
    )
    assert jira.attachment_metadata() == JiraAttachmentMetadata(
        available=True, enabled=True, upload_limit=123
    )


def test_list_attachments_reads_issue_attachment_field(monkeypatch):
    jira = client()
    monkeypatch.setattr(
        jira,
        "fetch_issue",
        lambda key, fields=None: {
            "key": key,
            "fields": {"attachment": [{"filename": "a.log", "size": 3}]},
        },
    )
    assert jira.list_attachments("SH-1") == [{"filename": "a.log", "size": 3}]
