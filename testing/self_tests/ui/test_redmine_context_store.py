from tool.SmartHome.redmine import context_store


def test_context_store_load_view_reads_saved_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(context_store, "cache_path", lambda _account: tmp_path / "redmine.json")
    view = {
        "context_payload": {"account": "alice"},
        "filters": {"project": "BDS [AN40BF-A311D2]", "status": "Closed", "type": "Bug", "text": ""},
        "projectFilterLabels": ["All projects", "BDS [AN40BF-A311D2]"],
        "statusFilterLabels": ["All statuses", "New"],
        "issueRows": [{"id": "61043", "title": "panel issue"}],
        "selectedIssue": {"id": "61043", "title": "panel issue"},
    }

    context_store.save_view("alice", view)
    loaded = context_store.load_view("alice", all_projects="All projects", all_statuses="All statuses")

    assert loaded["issueRows"][0]["id"] == "61043"
    assert loaded["selectedIssueId"] == "61043"
    assert loaded["filters"]["status"] == "Closed"
    assert context_store.load_filters("alice")["type"] == "Bug"
