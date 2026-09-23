import http.server
import json
import socket
import threading

import pytest

from core.jira.analyze_source import JiraAnalyzeError, JiraAnalyzeSource


def _issue(key):
    return {
        "key": key,
        "creator": "jira.autocreat",
        "reporter": "cong.zhang",
        "components": ["System Android(SH)(L1 Component)"],
        "created": "2026-09-01",
        "resolved": "2026-09-15",
        "manager": "Niko He",
        "qa_assignee": "",
        "project_id": "BR30AB-T950D5",
        "project_name": "TV Projects",
        "summary": "【T950D5】【32S5L Pro】播放视频，切换比例为4:3，按返回键退出时视频画面有拉伸",
        "priority": "P1",
        "status": "Closed",
        "issuetype": "Bug",
        "channel_of_reporter": "Customer-Feedback",
        "verify": {"verifier": "cong.zhang", "verified_date": "2026-09-16"},
        "comments": [{"author": "hui.an", "date": "2026-09-04", "count": 3}],
    }


def _ndjson(*lines):
    return ("\n".join(json.dumps(line) for line in lines) + "\n").encode("utf-8")


def _stream(*lines):
    """一个返回给定 NDJSON 行的桩响应。"""
    return lambda: (200, "application/x-ndjson", _ndjson(*lines))


class _AnalyzeStub(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.server.requests.append(json.loads(self.rfile.read(length) or b"{}"))
        status, content_type, body = self.server.responder()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stub_service():
    servers = []

    def start(responder):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _AnalyzeStub)
        server.responder = responder
        server.requests = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _source(server):
    host, port = server.server_address
    return JiraAnalyzeSource(f"http://{host}:{port}", "coco", "secret")


def test_fetch_returns_server_fields_and_effective_jql(stub_service):
    server = stub_service(_stream(
        {"type": "total", "total": 2, "jql": "project = TV ORDER BY created DESC"},
        {"type": "progress", "phase": "issues", "current": 2, "total": 2},
        {"type": "progress", "phase": "verify", "current": 2, "total": 2},
        {"type": "progress", "phase": "comments", "current": 2, "total": 2},
        {"type": "issue", "data": _issue("TV-1")},
        {"type": "issue", "data": _issue("TV-2")},
        {"type": "done", "total": 2, "jql": "project = TV ORDER BY created DESC"},
    ))

    jql, issues = _source(server).fetch("project = TV")

    assert jql == "project = TV ORDER BY created DESC"
    assert issues == [_issue("TV-1"), _issue("TV-2")]


def test_fetch_posts_credentials_jql_and_filters(stub_service):
    server = stub_service(_stream({"type": "done", "total": 0, "jql": "project = TV"}))

    _source(server).fetch(
        "project = TV",
        include_verify=False,
        include_comments=True,
        date_from="2026-09-01",
        date_to="2026-09-30",
    )

    assert server.requests == [{
        "jql": "project = TV",
        "username": "coco",
        "password": "secret",
        "include_verify": False,
        "include_comments": True,
        "date_from": "2026-09-01",
        "date_to": "2026-09-30",
    }]


def test_fetch_passes_jira_url_only_when_given(stub_service):
    server = stub_service(_stream({"type": "done", "total": 0, "jql": "project = TV"}))

    _source(server).fetch("project = TV", jira_url="https://jira.example.com")

    assert server.requests[0]["jira_url"] == "https://jira.example.com"


def test_fetch_reports_phase_progress(stub_service):
    server = stub_service(_stream(
        {"type": "progress", "phase": "issues", "current": 1, "total": 3},
        {"type": "progress", "phase": "verify", "current": 2, "total": 3},
        {"type": "progress", "phase": "comments", "current": 3, "total": 3},
        {"type": "done", "total": 3, "jql": "project = TV"},
    ))
    seen = []

    _source(server).fetch("project = TV", on_progress=lambda phase, current, total: seen.append((phase, current, total)))

    assert seen == [("issues", 1, 3), ("verify", 2, 3), ("comments", 3, 3)]


def test_fetch_returns_empty_list_when_jql_matches_nothing(stub_service):
    server = stub_service(_stream(
        {"type": "total", "total": 0, "jql": "project = TV ORDER BY created DESC"},
        {"type": "done", "total": 0, "jql": "project = TV ORDER BY created DESC"},
    ))

    assert _source(server).fetch("project = TV") == ("project = TV ORDER BY created DESC", [])


def test_fetch_raises_server_message_when_response_is_not_ndjson(stub_service):
    server = stub_service(lambda: (
        200,
        "application/json",
        json.dumps({"success": False, "message": "请提供 username 和 password/token"}).encode("utf-8"),
    ))

    with pytest.raises(JiraAnalyzeError, match="请提供 username 和 password/token"):
        _source(server).fetch("project = TV")


def test_fetch_raises_on_error_line_instead_of_returning_partial_issues(stub_service):
    server = stub_service(_stream(
        {"type": "total", "total": 2, "jql": "project = TV"},
        {"type": "issue", "data": _issue("TV-1")},
        {"type": "error", "message": "401 Unauthorized"},
    ))

    with pytest.raises(JiraAnalyzeError, match="401 Unauthorized"):
        _source(server).fetch("project = TV")


def test_fetch_raises_when_stream_ends_before_done(stub_service):
    server = stub_service(_stream(
        {"type": "total", "total": 2, "jql": "project = TV"},
        {"type": "issue", "data": _issue("TV-1")},
    ))

    with pytest.raises(JiraAnalyzeError, match="未返回 done"):
        _source(server).fetch("project = TV")


def test_fetch_reports_http_failure_status(stub_service):
    server = stub_service(lambda: (502, "text/html", b"<html>bad gateway</html>"))

    with pytest.raises(JiraAnalyzeError, match="HTTP 502"):
        _source(server).fetch("project = TV")


def test_fetch_reports_unreachable_service():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        host, port = probe.getsockname()

    with pytest.raises(JiraAnalyzeError, match="无法访问 analyze 服务"):
        JiraAnalyzeSource(f"http://{host}:{port}", "coco", "secret").fetch("project = TV")
