from __future__ import annotations

import json

import pytest

from testing.runtime.events import (
    reset_current_case_nodeid,
    reset_current_case_stress_tolerant,
    set_current_case_nodeid,
    set_current_case_stress_tolerant,
)
from testing.runtime.steps import case_step, loop_step, step, step_log


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
        "step_planned",
        "step_started",
        "log",
        "step_evidence",
        "step_planned",
        "step_started",
        "log",
        "step_evidence",
        "step_finished",
        "step_finished",
    ]
    assert events[0]["title"] == "Outer step"
    assert events[0]["definition_id"] == "example.outer"
    assert events[0]["meta"]["definition_id"] == "example.outer"
    assert events[4]["title"] == "Loop body (2/5)"
    assert events[4]["definition_id"] == "example.loop"
    assert events[6]["message"] == "world"


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


def test_stress_step_soft_failure_logs_and_continues(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    node_token = set_current_case_nodeid("pkg/test_stress.py::test_case")
    stress_token = set_current_case_stress_tolerant(True)
    continued = False
    try:
        with step("Stress check", definition_id="stress.check"):
            raise AssertionError("checkpoint failed")
        continued = True
    finally:
        reset_current_case_stress_tolerant(stress_token)
        reset_current_case_nodeid(node_token)

    assert continued
    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    assert any(
        event["type"] == "log"
        and event["level"] == "warning"
        and "[stress.soft_failure]" in event["message"]
        and "checkpoint failed" in event["message"]
        for event in events
    )
    finished = [event for event in events if event["type"] == "step_finished"][-1]
    assert finished["status"] == "passed"
    assert finished["actual"]["stress_soft_failure"] is True
    assert "checkpoint failed" in finished["actual"]["error"]


def test_stress_step_soft_failure_handles_pytest_fail(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    node_token = set_current_case_nodeid("pkg/test_stress.py::test_case")
    stress_token = set_current_case_stress_tolerant(True)
    continued = False
    try:
        with step("Stress pytest fail", definition_id="stress.pytest_fail"):
            pytest.fail("checkpoint failed through pytest.fail")
        continued = True
    finally:
        reset_current_case_stress_tolerant(stress_token)
        reset_current_case_nodeid(node_token)

    assert continued
    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    finished = [event for event in events if event["type"] == "step_finished"][-1]
    assert finished["status"] == "passed"
    assert finished["actual"]["stress_soft_failure"] is True
    assert "checkpoint failed through pytest.fail" in finished["actual"]["error"]


def test_non_stress_step_still_raises_assertion(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    token = set_current_case_nodeid("pkg/test_functional.py::test_case")
    try:
        try:
            with step("Functional check", definition_id="functional.check"):
                raise AssertionError("strict failure")
        except AssertionError as exc:
            assert "strict failure" in str(exc)
        else:
            raise AssertionError("Expected non-stress step to raise.")
    finally:
        reset_current_case_nodeid(token)


def test_stress_step_does_not_hide_unexpected_code_errors(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    node_token = set_current_case_nodeid("pkg/test_stress.py::test_case")
    stress_token = set_current_case_stress_tolerant(True)
    try:
        try:
            with step("Stress code path", definition_id="stress.code"):
                raise TypeError("bad call")
        except TypeError as exc:
            assert "bad call" in str(exc)
        else:
            raise AssertionError("Expected unexpected code error to raise.")
    finally:
        reset_current_case_stress_tolerant(stress_token)
        reset_current_case_nodeid(node_token)


def test_stress_step_can_opt_out_of_soft_failure(tmp_path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    node_token = set_current_case_nodeid("pkg/test_stress.py::test_case")
    stress_token = set_current_case_stress_tolerant(True)
    try:
        try:
            with step("Strict stress setup", definition_id="stress.strict", stress_tolerant=False):
                raise AssertionError("must stop")
        except AssertionError as exc:
            assert "must stop" in str(exc)
        else:
            raise AssertionError("Expected stress_tolerant=False to preserve strict failure.")
    finally:
        reset_current_case_stress_tolerant(stress_token)
        reset_current_case_nodeid(node_token)
