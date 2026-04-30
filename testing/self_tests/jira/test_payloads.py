from jira_tool.services.payloads import (
    build_analysis_result,
    build_browse_result,
    build_detail_result,
    build_scope_context,
)


def _translated_state(template: str, **values):
    return {"kind": "translated", "template": template, "values": dict(values)}


def _raw_state(text: str):
    return {"kind": "raw", "text": text}


def test_build_scope_context_keeps_filter_state() -> None:
    context = build_scope_context(
        raw_jql_text="project = TV",
        project_ids_csv="tv",
        board_label="Open Work",
        timeframe_label="Last 30 Days",
        status_ids_csv="blocked",
        priority_ids_csv="high",
        issue_type_ids_csv="bug",
        keyword_text="wifi",
        assignee_text="alice",
        reporter_text="bob",
        labels_text="regression",
        include_comments=True,
        include_links=False,
        only_mine=False,
    )
    assert context["raw_jql_text"] == "project = TV"
    assert context["labels_text"] == "regression"
    assert context["include_comments"] is True


def test_build_browse_result_shapes_common_ui_payload() -> None:
    payload = build_browse_result(
        worker_id=3,
        base_url="https://jira.example.com",
        loaded_count=25,
        total_count=100,
        issues=[{"keyId": "FQ-1"}],
        append=False,
        selected_issue_index=0,
        next_start_at=25,
        can_load_more=True,
        scope={"project_ids_csv": "tv"},
        translated_state=_translated_state,
    )
    assert payload["worker_id"] == 3
    assert payload["displayed_total"] == 100
    assert payload["can_load_more"] is True
    assert payload["status_state"]["kind"] == "translated"


def test_build_detail_result_keeps_worker_and_issue() -> None:
    payload = build_detail_result(worker_id=2, issue={"keyId": "FQ-2"})
    assert payload == {"worker_id": 2, "issue": {"keyId": "FQ-2"}}


def test_build_analysis_result_shapes_analysis_payload() -> None:
    payload = build_analysis_result(
        worker_id=4,
        base_url="https://jira.example.com",
        returned_count=10,
        total_count=30,
        issues=[{"keyId": "FQ-3"}],
        analysis_text="summary",
        append=False,
        next_start_at=10,
        can_load_more=True,
        scope={"project_ids_csv": "tv"},
        translated_state=_translated_state,
        raw_state=_raw_state,
        assistant_timestamp="Just now",
    )
    assert payload["analysis_summary_state"] == {"kind": "raw", "text": "summary"}
    assert payload["assistant_timestamp"] == "Just now"
    assert payload["connected"] is True
