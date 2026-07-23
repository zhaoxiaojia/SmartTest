from tool.SmartHome.redmine.query import RedmineQuery, parse_terms


def test_terms_use_agreed_separators_and_stable_dedupe():
    assert parse_terms("60371,播放失败；60371\n黑屏") == ("60371", "播放失败", "黑屏")


def test_text_query_builds_fulltext_and_numeric_id_union():
    branches = RedmineQuery(status="open", subject="Highlight", text="60371 播放失败").branches()
    assert [branch.kind for branch in branches] == ["fulltext", "issue_id"]
    assert ("op[any_searchable]", "*~") in branches[0].params(1, 100)
    assert ("v[issue_id][]", "60371") in branches[1].params(1, 100)


def test_each_numeric_id_uses_one_native_exact_branch_and_one_value():
    branches = RedmineQuery(text="60371 60372 播放失败").branches()
    assert [branch.kind for branch in branches] == ["fulltext", "issue_id", "issue_id"]
    assert [
        [value for key, value in branch.params(1, 100) if key == "v[issue_id][]"]
        for branch in branches[1:]
    ] == [["60371"], ["60372"]]


def test_empty_subject_is_not_sent():
    assert not any(key == "v[subject][]" for key, _ in RedmineQuery(subject="").branches()[0].params(1, 100))


def test_status_semantics_use_native_operator_without_value():
    opened = RedmineQuery(status="Open").branches()[0].params(1, 100)
    closed = RedmineQuery(status="Closed").branches()[0].params(1, 100)
    all_statuses = RedmineQuery(status="All statuses").branches()[0].params(1, 100)
    assert ("f[]", "status_id") in opened and ("op[status_id]", "o") in opened
    assert ("f[]", "status_id") in closed and ("op[status_id]", "c") in closed
    assert not any(key == "v[status_id][]" for key, _ in opened + closed)
    assert not any(value == "status_id" for key, value in all_statuses if key == "f[]")


def test_unknown_status_and_noncanonical_tracker_are_rejected():
    import pytest
    with pytest.raises(ValueError, match="status"):
        RedmineQuery(status="Feedback").branches()
    with pytest.raises(ValueError, match="tracker"):
        RedmineQuery(tracker="Bug").branches()
