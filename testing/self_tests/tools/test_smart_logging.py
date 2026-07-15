from __future__ import annotations

import json
import sys

from testing.test_context import smarttest_context
from testing.runtime.steps import step_log
from support.logging import SMARTTEST_LOG_DIR_ENV, SMARTTEST_STEP_EVENTS_OUT_ENV, smart_log


def test_smart_log_writes_static_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path))
    record = smart_log(
        "hello",
        domain="runner",
        level="warn",
        source="unit",
        case_nodeid="case::id",
        step_id="step-1",
        extra={"k": "v"},
        emit_runtime_event=False,
    )

    log_path = tmp_path / "smarttest.log"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert record.level == "warning"
    assert rows == [
        {
            "timestamp": record.timestamp,
            "level": "warning",
            "domain": "runner",
            "source": "unit",
            "case_nodeid": "case::id",
            "step_id": "step-1",
            "message": "hello",
            "extra": {"k": "v"},
        }
    ]
    readable = (tmp_path / "smarttest_readable.log").read_text(encoding="utf-8")
    assert "[runner] [WARNING] [unit] hello" in readable


def test_smart_log_emits_runtime_event(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path / "logs"))
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv(SMARTTEST_STEP_EVENTS_OUT_ENV, str(event_path))

    smart_log("event message", domain="test", source="step", case_nodeid="case-a", step_id="step-a")

    payload = json.loads(event_path.read_text(encoding="utf-8").strip())
    assert payload["type"] == "log"
    assert payload["domain"] == "test"
    assert payload["source"] == "step"
    assert payload["case_nodeid"] == "case-a"
    assert payload["step_id"] == "step-a"
    assert payload["message"] == "event message"
    assert payload["line"] == "[test][step] event message"


def test_smart_log_runtime_event_does_not_echo_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path / "logs"))
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv(SMARTTEST_STEP_EVENTS_OUT_ENV, str(event_path))

    smart_log("child message", domain="test", source="step")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "child message" in event_path.read_text(encoding="utf-8")


def test_smart_log_tolerates_windowed_runtime_without_stdout(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)

    smart_log("windowed message", domain="framework", source="unit", emit_runtime_event=False)

    readable = (tmp_path / "smarttest_readable.log").read_text(encoding="utf-8")
    assert "windowed message" in readable


def test_step_log_uses_smart_log_runtime_event(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path / "logs"))
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv(SMARTTEST_STEP_EVENTS_OUT_ENV, str(event_path))
    token = smarttest_context().cases.set_current_nodeid("case-from-step-log")
    try:
        step_log("step message", level="warning", extra={"reason": "unit"})
    finally:
        smarttest_context().cases.reset_current_nodeid(token)

    payloads = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    log_events = [payload for payload in payloads if payload.get("type") == "log"]
    evidence_events = [payload for payload in payloads if payload.get("type") == "step_evidence"]

    assert log_events[0]["domain"] == "test"
    assert log_events[0]["level"] == "warning"
    assert log_events[0]["source"] == "step"
    assert log_events[0]["case_nodeid"] == "case-from-step-log"
    assert log_events[0]["message"] == "step message"
    assert evidence_events[0]["evidence_type"] == "log"
