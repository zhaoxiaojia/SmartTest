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


def test_project_options_cache_is_account_specific_and_preserved_with_view(tmp_path, monkeypatch):
    monkeypatch.setattr(context_store, "cache_path", lambda account: tmp_path / f"{account}.json")
    alice = [{"id": "a", "label": "Alice"}]
    bob = [{"id": "b", "label": "Bob"}]
    context_store.save_project_options("alice", alice)
    context_store.save_project_options("bob", bob)
    assert context_store.load_project_options("alice") == alice
    assert context_store.load_project_options("bob") == bob
    context_store.save_view("alice", {"filters": {}, "issueRows": []})
    assert context_store.load_project_options("alice") == alice


def test_my_page_cache_is_account_specific_and_not_overwritten_by_search(tmp_path, monkeypatch):
    monkeypatch.setattr(context_store, "cache_path", lambda account: tmp_path / f"{account}.json")
    my_page = {"filters": {}, "issueRows": [{"id": "mine"}], "selectedIssue": {"id": "mine"}}
    context_store.save_quick_view("alice", "my_assigned", my_page)
    context_store.save_view("alice", {"filters": {"text": "search"}, "issueRows": [{"id": "search"}]})
    context_store.save_quick_view("bob", "my_assigned", {"filters": {}, "issueRows": [{"id": "bob"}]})
    assert context_store.load_quick_view("alice", "my_assigned", all_projects="All projects", all_statuses="All statuses")["issueRows"] == [{"id": "mine"}]
    assert context_store.load_quick_view("bob", "my_assigned", all_projects="All projects", all_statuses="All statuses")["issueRows"] == [{"id": "bob"}]


def test_legacy_my_page_selected_list_shell_is_not_restored_as_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(context_store, "cache_path", lambda _account: tmp_path / "alice.json")
    context_store.save_quick_view("alice", "my_assigned", {"issueRows": [{"id": "1"}], "selectedIssue": {"id": "1", "title": "shell"}})
    loaded = context_store.load_quick_view("alice", "my_assigned", all_projects="All projects", all_statuses="All statuses")
    assert loaded["selectedIssue"] == {}
    assert loaded["selectedIssueId"] == ""


def test_enriched_my_page_selected_detail_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(context_store, "cache_path", lambda _account: tmp_path / "alice.json")
    selected = {"id": "1", "title": "full", "description": "body", "detailsFields": [{"label": "Status", "value": "New"}]}
    context_store.save_quick_view("alice", "my_assigned", {"issueRows": [{"id": "1"}], "selectedIssue": selected})
    loaded = context_store.load_quick_view("alice", "my_assigned", all_projects="All projects", all_statuses="All statuses")
    assert loaded["selectedIssue"]["description"] == "body"
