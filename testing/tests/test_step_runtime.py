from __future__ import annotations

import json

from testing.runtime.events import reset_current_case_nodeid, set_current_case_nodeid
from testing.runtime.steps import case_step, loop_step, step_log


def test_step_context_writes_step_and_log_events(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    token = set_current_case_nodeid("pkg/test_example.py::test_case")
    try:
        with case_step("Outer step", definition_id="example.outer"):
            step_log("hello")
            with loop_step("Loop body", index=2, total=5, definition_id="example.loop"):
                step_log("world")
    finally:
        reset_current_case_nodeid(token)

    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    assert [event["type"] for event in events] == [
        "step_started",
        "log",
        "step_started",
        "log",
        "step_finished",
        "step_finished",
    ]
    assert events[0]["title"] == "Outer step"
    assert events[0]["definition_id"] == "example.outer"
    assert events[0]["meta"]["definition_id"] == "example.outer"
    assert events[2]["title"] == "Loop body (2/5)"
    assert events[2]["definition_id"] == "example.loop"
    assert events[3]["message"] == "world"


def test_step_definition_id_rejects_unstable_format(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    token = set_current_case_nodeid("pkg/test_example.py::test_case")
    try:
        try:
            with case_step("Bad step", definition_id="Bad Step"):
                pass
        except ValueError as exc:
            assert "definition_id" in str(exc)
        else:
            raise AssertionError("Expected invalid definition_id to be rejected.")
    finally:
        reset_current_case_nodeid(token)
