from support.jira_integration.auth.basic import JiraBasicAuth
from support.jira_integration.core.models import CreateIssueAttachment
from support.jira_integration.transport.client import JiraClient, JiraClientConfig


def test_multipart_upload_uses_jira_headers_and_escaped_filename(monkeypatch):
    client = JiraClient(
        JiraClientConfig("https://jira.example"),
        JiraBasicAuth("user", "password"),
    )
    seen = {}

    def request(method, url, **kwargs):
        seen.update(method=method, url=url, **kwargs)
        return type("Response", (), {"data": [{"id": "1"}]})()

    monkeypatch.setattr(client, "_request", request)
    result = client.upload_attachment(
        "SH-1", CreateIssueAttachment(filename='report "one".txt', data=b"payload")
    )

    assert result == {"id": "1"}
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/rest/api/2/issue/SH-1/attachments")
    assert seen["headers"]["X-Atlassian-Token"] == "no-check"
    assert seen["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    body = seen["data"]
    assert b'name="file"' in body
    assert b'filename="report \\"one\\".txt"' in body
    assert body.count(b"payload") == 1


def test_list_attachments_reads_issue_attachment_field(monkeypatch):
    client = JiraClient(
        JiraClientConfig("https://jira.example"),
        JiraBasicAuth("user", "password"),
    )
    monkeypatch.setattr(
        client,
        "fetch_issue",
        lambda key, fields=None: {
            "key": key,
            "fields": {"attachment": [{"filename": "a.log", "size": 3}]},
        },
    )
    assert client.list_attachments("SH-1") == [{"filename": "a.log", "size": 3}]
