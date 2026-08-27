from __future__ import annotations

import json

from core.logging import (
    SMARTTEST_LOG_DIR_ENV,
    SMARTTEST_STEP_EVENTS_OUT_ENV,
    configure_platform,
    current_platform,
    smart_log,
)


def _shared_core_operation():
    return smart_log(
        "shared", domain="jira", source="core.jira.shared", emit_runtime_event=False
    )


def test_process_entry_owns_platform_for_same_core_operation(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path))
    previous = current_platform()
    try:
        configure_platform("client")
        client_record = _shared_core_operation()
        configure_platform("tool")
        tool_record = _shared_core_operation()
    finally:
        configure_platform(previous)

    assert client_record.platform == "client"
    assert tool_record.platform == "tool"
    assert client_record.domain == tool_record.domain == "jira"


def test_explicit_domain_keeps_configured_process_platform(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path))
    previous = current_platform()
    try:
        configure_platform("runner")
        record = smart_log("step", domain="test", emit_runtime_event=False)
    finally:
        configure_platform(previous)

    assert record.platform == "runner"


def test_shared_record_preserves_files_events_colors_and_platform_fields(tmp_path, monkeypatch):
    monkeypatch.setenv(SMARTTEST_LOG_DIR_ENV, str(tmp_path / "logs"))
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv(SMARTTEST_STEP_EVENTS_OUT_ENV, str(event_path))

    record = smart_log(
        "hello", platform="runner", domain="test", level="warn", source="step",
        request_id="req-1", case_nodeid="case-1", step_id="step-1", extra={"key": "value"},
    )

    static = json.loads((tmp_path / "logs" / "smarttest.log").read_text(encoding="utf-8"))
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert static == {
        "timestamp": record.timestamp, "platform": "runner", "level": "warning", "domain": "test",
        "message": "hello", "source": "step", "request_id": "req-1", "case_nodeid": "case-1",
        "step_id": "step-1", "extra": {"key": "value"},
    }
    assert event["line"] == "[runner][test][step] hello"
    assert event["accent_color_light"]
    assert f"{record.timestamp} [runner] [test] [WARNING] [step] hello" in (
        tmp_path / "logs" / "smarttest_readable.log"
    ).read_text(encoding="utf-8")
