from pathlib import Path

from jira.cache.search_cache import JiraSearchCache
from jira.core.models import IssueRecord


def test_cache_round_trip(tmp_path: Path) -> None:
    cache = JiraSearchCache(tmp_path / "jira_cache.db")
    records = [
        IssueRecord(key="ST-1", id="10001", raw={"key": "ST-1"}, fields={"summary": "Hello"}),
        IssueRecord(key="ST-2", id="10002", raw={"key": "ST-2"}, fields={"summary": "World"}),
    ]

    cache.put_records(
        jql="project = ST",
        spec_names=["summary"],
        include_heavy=False,
        records=records,
    )

    cached = cache.get_records(
        jql="project = ST",
        spec_names=["summary"],
        include_heavy=False,
        ttl_seconds=60,
    )

    assert cached is not None
    assert [record.key for record in cached] == ["ST-1", "ST-2"]
    assert cached[0].fields["summary"] == "Hello"
