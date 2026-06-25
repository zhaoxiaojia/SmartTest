from __future__ import annotations

from ui.example.bridge.StepStore import StepStore


def test_case_rows_start_planned_and_event_sets_running():
    changes: list[bool] = []
    logs: list[str] = []
    store = StepStore(log=logs.append, on_change=lambda: changes.append(True))

    first = store.ensure_case_row(case_nodeid="case::first", title="first")
    second = store.ensure_case_row(case_nodeid="case::second", title="second")

    rows = store.snapshot()
    assert first == "case:case::first"
    assert second == "case:case::second"
    assert rows[0]["status"] == "planned"
    assert rows[1]["status"] == "planned"

    store.mark_case_started({"case_nodeid": "case::second", "title": "second"})

    rows = store.snapshot()
    assert rows[0]["status"] == "planned"
    assert rows[1]["status"] == "running"


def test_step_update_does_not_reset_running_case_to_planned():
    store = StepStore(log=lambda _line: None, on_change=lambda: None)
    case = "case::wifi"
    case_row = store.ensure_case_row(case_nodeid=case, title="wifi")
    store.upsert_step_row(
        {
            "step_id": f"plan:{case}:wifi.prepare",
            "case_nodeid": case,
            "parent_id": case_row,
            "title": "Prepare Wi-Fi",
            "kind": "setup",
            "definition_id": "wifi.prepare",
        },
        status="planned",
    )
    store.mark_case_started({"case_nodeid": case, "title": "wifi"})

    store.mark_step_started(
        {
            "step_id": "runtime:wifi.prepare",
            "case_nodeid": case,
            "title": "Prepare Wi-Fi",
            "kind": "setup",
            "definition_id": "wifi.prepare",
        }
    )

    rows = store.snapshot()
    case_row = next(row for row in rows if row["kind"] == "case")
    assert case_row["status"] == "running"


def test_repeat_group_keeps_current_row_running_when_new_cycle_starts():
    store = StepStore(log=lambda _line: None, on_change=lambda: None)
    case = "case::wifi"
    case_row = store.ensure_case_row(case_nodeid=case, title="wifi")
    for step_id, definition_id, title in (
        ("wifi_onoff_scan.cycle.disable", "radio.wifi.disable", "Cycle: disable"),
        ("wifi_onoff_scan.cycle.enable", "radio.wifi.enable", "Cycle: enable"),
        ("wifi_onoff_scan.cycle.capture_radio_state", "power.capture_radio_state", "Cycle: capture radio state"),
    ):
        store.upsert_step_row(
            {
                "step_id": f"plan:{case}:{step_id}",
                "case_nodeid": case,
                "parent_id": case_row,
                "title": title,
                "kind": "step",
                "definition_id": definition_id,
            },
            status="planned",
        )

    store.mark_step_started(
        {
            "step_id": "request:wifi_onoff_scan.cycle.1.capture_radio_state",
            "case_nodeid": case,
            "title": "Cycle 1/2: capture radio state",
            "kind": "check",
            "definition_id": "wifi_onoff_scan.cycle.capture_radio_state",
        }
    )
    store.apply_step_finished(
        {
            "step_id": "request:wifi_onoff_scan.cycle.1.capture_radio_state",
            "case_nodeid": case,
            "title": "Cycle 1/2: capture radio state",
            "kind": "check",
            "definition_id": "wifi_onoff_scan.cycle.capture_radio_state",
            "status": "passed",
        },
        min_running_display_sec=0,
    )
    store.mark_step_started(
        {
            "step_id": "request:wifi_onoff_scan.cycle.2.disable",
            "case_nodeid": case,
            "title": "Cycle 2/2: disable",
            "kind": "step",
            "definition_id": "wifi_onoff_scan.cycle.disable",
        }
    )

    rows = {row["definition_id"]: row for row in store.snapshot()}
    assert rows["radio.wifi.disable"]["status"] == "running"
    assert rows["radio.wifi.enable"]["status"] == "planned"


def test_repeat_group_does_not_reset_when_terminal_snapshot_omits_total_count():
    store = StepStore(log=lambda _line: None, on_change=lambda: None)
    case = "case::wifi"
    case_row = store.ensure_case_row(case_nodeid=case, title="wifi")
    for step_id, definition_id, title in (
        ("wifi_onoff_scan.cycle.disable", "radio.wifi.disable", "Cycle: disable"),
        ("wifi_onoff_scan.cycle.enable", "radio.wifi.enable", "Cycle: enable"),
        ("wifi_onoff_scan.cycle.capture_radio_state", "power.capture_radio_state", "Cycle: capture radio state"),
    ):
        store.upsert_step_row(
            {
                "step_id": f"plan:{case}:{step_id}",
                "case_nodeid": case,
                "parent_id": case_row,
                "title": title,
                "kind": "step",
                "definition_id": definition_id,
            },
            status="planned",
        )

    for raw_id, definition_id, title in (
        ("wifi_onoff_scan.cycle.2.disable", "wifi_onoff_scan.cycle.disable", "Cycle 2/2: disable"),
        ("wifi_onoff_scan.cycle.2.enable", "wifi_onoff_scan.cycle.enable", "Cycle 2/2: enable"),
    ):
        payload = {
            "step_id": f"request:{raw_id}",
            "case_nodeid": case,
            "title": title,
            "kind": "step",
            "definition_id": definition_id,
        }
        store.mark_step_started(payload)
        store.apply_step_finished({**payload, "status": "passed"}, min_running_display_sec=0)

    store.mark_step_started(
        {
            "step_id": "request:wifi_onoff_scan.cycle.2.capture_radio_state",
            "case_nodeid": case,
            "title": "Cycle 2: capture radio state",
            "kind": "check",
            "definition_id": "wifi_onoff_scan.cycle.capture_radio_state",
        }
    )

    rows = {row["definition_id"]: row for row in store.snapshot()}
    assert rows["radio.wifi.disable"]["status"] == "passed"
    assert rows["radio.wifi.enable"]["status"] == "passed"
    assert rows["power.capture_radio_state"]["status"] == "running"


def test_single_loop_row_refreshes_runtime_loop_title():
    store = StepStore(log=lambda _line: None, on_change=lambda: None)
    case = "case::local_playback"
    case_row = store.ensure_case_row(case_nodeid=case, title="local playback")
    store.upsert_step_row(
        {
            "step_id": f"plan:{case}:local_playback_stress.loop",
            "case_nodeid": case,
            "parent_id": case_row,
            "title": "Run local playback stress loop",
            "kind": "step",
            "definition_id": "local_playback.loop",
        },
        status="planned",
    )

    store.mark_step_started(
        {
            "step_id": "local_playback_stress.loop",
            "case_nodeid": case,
            "title": "Loop 2/3: Run local playback stress loop",
            "kind": "step",
            "definition_id": "local_playback.loop",
        }
    )

    rows = [row for row in store.snapshot() if row["kind"] == "step"]
    assert len(rows) == 1
    assert rows[0]["title"] == "Loop 2/3: Run local playback stress loop"
    assert rows[0]["status"] == "running"
