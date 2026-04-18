from jira.auth.basic import JiraBasicAuth
from jira.transport.client import JiraClient, JiraClientConfig


def _client() -> JiraClient:
    return JiraClient(
        JiraClientConfig(base_url="https://jira.example.com"),
        JiraBasicAuth(username="demo", password="secret"),
    )


def test_post_validate_query_is_boolean_for_server_compatibility() -> None:
    client = _client()

    assert client._normalize_validate_query("strict", use_post=True) is True
    assert client._normalize_validate_query("warn", use_post=True) is True
    assert client._normalize_validate_query("false", use_post=True) is False
    assert client._normalize_validate_query(False, use_post=True) is False


def test_get_validate_query_keeps_jira_string_modes() -> None:
    client = _client()

    assert client._normalize_validate_query("strict", use_post=False) == "strict"
    assert client._normalize_validate_query("warn", use_post=False) == "warn"
    assert client._normalize_validate_query(True, use_post=False) == "true"
