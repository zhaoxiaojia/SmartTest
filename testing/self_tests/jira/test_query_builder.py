from jira_tool.services.query_builder import build_base_jql, parse_csv_ids, parse_csv_terms


def test_parse_csv_ids_deduplicates_and_strips() -> None:
    assert parse_csv_ids(" tv,ott,tv , ,gh ") == ["tv", "ott", "gh"]


def test_parse_csv_terms_supports_commas_and_semicolons() -> None:
    assert parse_csv_terms("alice; bob,alice , carol") == ["alice", "bob", "carol"]


def test_build_base_jql_prefers_raw_jql() -> None:
    assert (
        build_base_jql(
            raw_jql_text="project = TV ORDER BY created DESC",
            project_ids_csv="tv",
            board_id="open_work",
            timeframe_id="last_30_days",
            status_ids_csv="",
            priority_ids_csv="",
            issue_type_ids_csv="bug",
            keyword_text="",
            assignee_text="",
            reporter_text="",
            labels_text="",
            only_mine=False,
        )
        == "project = TV ORDER BY created DESC"
    )


def test_build_base_jql_builds_common_scope_filters() -> None:
    jql = build_base_jql(
        raw_jql_text="",
        project_ids_csv="tv,ott",
        board_id="open_work",
        timeframe_id="last_30_days",
        status_ids_csv="blocked,ready_for_test",
        priority_ids_csv="high",
        issue_type_ids_csv="bug",
        keyword_text="wifi reconnect",
        assignee_text="alice,bob",
        reporter_text="carol",
        labels_text="regression,smoke",
        only_mine=False,
    )
    assert 'project in (TV, OTT)' in jql
    assert 'issuetype in ("Bug")' in jql
    assert 'status in ("Blocked", "Ready for Test")' in jql
    assert 'updated >= -30d' in jql
    assert 'assignee in ("alice", "bob")' in jql
    assert 'reporter in ("carol")' in jql
    assert 'priority in ("High")' in jql
    assert 'labels in ("regression", "smoke")' in jql
    assert 'text ~ "wifi reconnect"' in jql
    assert jql.endswith("ORDER BY updated DESC")


def test_build_base_jql_uses_current_user_when_only_mine() -> None:
    jql = build_base_jql(
        raw_jql_text="",
        project_ids_csv="all_supported_projects",
        board_id="open_work",
        timeframe_id="last_7_days",
        status_ids_csv="",
        priority_ids_csv="",
        issue_type_ids_csv="bug",
        keyword_text="",
        assignee_text="alice",
        reporter_text="",
        labels_text="",
        only_mine=True,
    )
    assert "assignee = currentUser()" in jql
    assert '"alice"' not in jql
