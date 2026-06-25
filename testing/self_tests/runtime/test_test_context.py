from __future__ import annotations

import json
from pathlib import Path

from testing.runner.config import RUN_CONFIG_ENV
from testing.runner.config import RunConfig
from testing.test_context import reset_test_context_for_tests, smarttest_context
from testing.runtime.config import current_dut_serial, equipment_config, runtime_config


def test_runtime_case_and_step_state_are_owned_by_smarttest_context():
    reset_test_context_for_tests()
    context = smarttest_context()
    previous_case_nodeid = context.current_case_nodeid()

    token = context.cases.set_current_nodeid("case::one")
    try:
        step_token = context.push_step({"id": "step-1", "title": "Prepare"})
        try:
            assert context.current_case_nodeid() == "case::one"
            assert context.current_step()["id"] == "step-1"
        finally:
            context.pop_step(step_token)
    finally:
        context.cases.reset_current_nodeid(token)

    assert context.current_case_nodeid() == previous_case_nodeid
    assert context.current_step() is None


def test_runtime_config_and_params_are_mounted_on_test_context(monkeypatch):
    reset_test_context_for_tests()
    payload = {
        "nodeids": ["case::one"],
        "dut_serial": "dut-123",
        "equipment": {"relay": "r1"},
        "global_context": {"operator": "qa"},
    }
    monkeypatch.setenv(RUN_CONFIG_ENV, json.dumps(payload))

    context = smarttest_context()

    assert runtime_config() == context.runtime_config()
    assert current_dut_serial() == "dut-123"
    assert equipment_config() == {"relay": "r1"}
    assert smarttest_context().params is context.params


def test_emit_event_writes_through_test_context_event_store(tmp_path, monkeypatch):
    reset_test_context_for_tests()
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_path))

    smarttest_context().events.emit("case_started", case_nodeid="case::one", title="one")

    rows = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "type": "case_started",
            "case_nodeid": "case::one",
            "title": "one",
            "timestamp": rows[0]["timestamp"],
        }
    ]
    assert smarttest_context().events.snapshot()[0]["type"] == "case_started"


def test_begin_run_initializes_cases_steps_and_report_snapshot(monkeypatch, tmp_path):
    reset_test_context_for_tests()

    def fake_plan(*, root_dir: Path, nodeid: str, **_kwargs):
        return [
            {
                "id": "prepare",
                "title": f"Prepare {nodeid}",
                "kind": "setup",
                "definition_id": "case.prepare",
                "expected": "ready",
            }
        ]

    monkeypatch.setattr("testing.steps.planner.build_step_plan", fake_plan)
    context = smarttest_context()

    context.begin_run(
        root_dir=tmp_path,
        run_config=RunConfig(nodeids=["case::one"], dut_serial="dut-1"),
        started_at="2026-06-24T10:00:00+08:00",
    )

    rows = context.step_rows()
    assert [row["kind"] for row in rows] == ["case", "setup"]
    assert rows[0]["case_nodeid"] == "case::one"
    assert rows[0]["status"] == "planned"
    assert rows[1]["id"] == "plan:case::one:prepare"
    snapshot = context.report_snapshot()
    assert snapshot["run_id"]
    assert snapshot["started_at"] == "2026-06-24T10:00:00+08:00"
    assert snapshot["selected_nodeids"] == ["case::one"]
    assert snapshot["adb_serial"] == "dut-1"


def test_apply_event_updates_context_and_snapshots_are_read_only(monkeypatch, tmp_path):
    reset_test_context_for_tests()
    monkeypatch.setattr(
        "testing.steps.planner.build_step_plan",
        lambda *, root_dir, nodeid, **_kwargs: [
            {
                "id": "prepare",
                "title": "Prepare",
                "kind": "setup",
                "definition_id": "case.prepare",
                "expected": "ready",
            }
        ],
    )
    context = smarttest_context()
    context.begin_run(
        root_dir=tmp_path,
        run_config=RunConfig(nodeids=["case::one"], dut_serial="dut-1"),
        started_at="2026-06-24T10:00:00+08:00",
    )

    context.apply_event({"type": "case_started", "case_nodeid": "case::one", "title": "one"})
    context.apply_event(
        {
            "type": "step_started",
            "step_id": "runtime:prepare",
            "case_nodeid": "case::one",
            "title": "Prepare",
            "kind": "setup",
            "definition_id": "case.prepare",
            "timestamp": 1.0,
        }
    )
    context.apply_event(
        {
            "type": "step_evidence",
            "step_id": "runtime:prepare",
            "case_nodeid": "case::one",
            "title": "Log",
            "evidence_type": "log",
            "level": "info",
            "content": "ready",
        }
    )
    context.apply_event(
        {
            "type": "step_finished",
            "step_id": "runtime:prepare",
            "case_nodeid": "case::one",
            "status": "passed",
            "definition_id": "case.prepare",
            "timestamp": 2.0,
        }
    )
    context.apply_event({"type": "case_finished", "case_nodeid": "case::one", "status": "passed", "duration_ms": 1000})
    context.append_log({"line": "hello", "domain": "runner", "level": "info"})

    ui_snapshot = context.ui_snapshot()
    ui_snapshot["steps"][0]["status"] = "failed"
    ui_snapshot["logs"].append({"line": "mutated"})

    assert context.step_rows()[0]["status"] == "passed"
    assert context.log_rows()[0]["line"] == "hello"
    assert context.log_rows()[0]["domain"] == "runner"
    assert context.log_rows()[0]["level"] == "info"
    report = context.finish_run(returncode=0, stopped=False, finished_at="2026-06-24T10:01:00+08:00")
    assert report["returncode"] == 0
    assert report["steps"][0]["status"] == "passed"
    assert report["logs"][0]["line"] == "hello"


def test_report_snapshot_contains_display_model_without_consumer_inference(monkeypatch, tmp_path):
    reset_test_context_for_tests()
    monkeypatch.setattr(
        "testing.steps.planner.build_step_plan",
        lambda *, root_dir, nodeid, **_kwargs: [
            {
                "id": "cycle.copy",
                "title": "Cycle: copy",
                "kind": "step",
                "definition_id": "storage.copy",
                "expected": "copy passes",
            }
        ],
    )
    context = smarttest_context()
    context.begin_run(
        root_dir=tmp_path,
        run_config=RunConfig(nodeids=["case::storage"], dut_serial="dut-1"),
        started_at="2026-06-24T10:00:00+08:00",
    )
    context.set_case_loop_summary(
        "case::storage",
        {
            "observed": 10,
            "total": 10,
            "actions": {"storage.copy": {"passed": 10}},
        },
    )
    context.set_case_summary("case::storage", {"headline": "Storage loop complete"})
    context.add_case_artifact("case::storage", {"title": "Result file", "path": "result.json"})
    context.set_case_failure("case::storage", {"status": "passed", "primary_failure": {}})

    snapshot = context.report_snapshot()
    snapshot["cases"][0]["loop_summary"]["observed"] = 999
    snapshot["cases"][0]["artifacts"].append({"title": "mutated"})

    fresh = context.report_snapshot()
    assert fresh["summary"]["total"] == 1
    assert fresh["cases"][0]["case"]["case_nodeid"] == "case::storage"
    assert fresh["cases"][0]["case_summary"] == {"headline": "Storage loop complete"}
    assert fresh["cases"][0]["loop_summary"] == {
        "observed": 10,
        "total": 10,
        "actions": {"storage.copy": {"passed": 10}},
    }
    assert fresh["cases"][0]["artifacts"] == [{"title": "Result file", "path": "result.json"}]
    assert fresh["failure_analysis"] == {"status": "passed", "primary_failure": {}}


def test_loop_summary_is_derived_from_finished_loop_steps(monkeypatch, tmp_path):
    reset_test_context_for_tests()
    monkeypatch.setattr(
        "testing.steps.planner.build_step_plan",
        lambda *, root_dir, nodeid, **_kwargs: [
            {
                "id": "domain.loop.action_a",
                "title": "Loop: action A",
                "kind": "step",
                "definition_id": "domain.action_a",
            },
            {
                "id": "domain.loop.action_b",
                "title": "Loop: action B",
                "kind": "step",
                "definition_id": "domain.action_b",
            },
        ],
    )
    context = smarttest_context()
    context.begin_run(
        root_dir=tmp_path,
        run_config=RunConfig(nodeids=["case::looped"], dut_serial="dut-1"),
        started_at="2026-06-24T10:00:00+08:00",
    )

    context.apply_event(
        {
            "type": "step_finished",
            "case_nodeid": "case::looped",
            "step_id": "request:domain.loop.1.action_a",
            "definition_id": "domain.loop.action_a",
            "title": "Loop 1/2: action A",
            "status": "passed",
        }
    )
    context.apply_event(
        {
            "type": "step_finished",
            "case_nodeid": "case::looped",
            "step_id": "request:domain.loop.2.action_a",
            "definition_id": "domain.loop.action_a",
            "title": "Loop 2/2: action A",
            "status": "failed",
        }
    )
    context.apply_event(
        {
            "type": "step_finished",
            "case_nodeid": "case::looped",
            "step_id": "runtime:plain",
            "definition_id": "domain.action_b",
            "title": "Loop 2/2: action B",
            "status": "passed",
        }
    )

    loop_summary = context.report_snapshot()["cases"][0]["loop_summary"]
    assert loop_summary == {
        "observed": 2,
        "total": 2,
        "actions": {
            "domain.loop.action_a": {"failed": 1, "passed": 1},
            "domain.action_b": {"passed": 1},
        },
    }
