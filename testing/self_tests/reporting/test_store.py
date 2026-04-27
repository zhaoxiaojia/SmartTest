from __future__ import annotations

from testing.reporting import ReportStore, build_run_report


def test_build_run_report_counts_case_rows_only() -> None:
    report = build_run_report(
        run_id="run-1",
        started_at="2026-04-27T01:00:00+00:00",
        finished_at="2026-04-27T01:00:03+00:00",
        duration_ms=3000,
        returncode=1,
        stopped=False,
        adb_serial="ABC123",
        selected_nodeids=["testing/tests/test_sample.py::test_a"],
        steps=[
            {"kind": "case", "status": "failed", "case_nodeid": "a"},
            {"kind": "step", "status": "passed", "case_nodeid": "a"},
        ],
        logs=[{"line": "hello"}],
    )

    assert report["status"] == "failed"
    assert report["counts"] == {
        "total": 1,
        "passed": 0,
        "failed": 1,
        "skipped": 0,
        "running": 0,
    }


def test_report_store_lists_newest_finished_report_first(tmp_path) -> None:
    store = ReportStore(tmp_path)
    older = build_run_report(
        run_id="older",
        started_at="2026-04-27T01:00:00+00:00",
        finished_at="2026-04-27T01:00:01+00:00",
        duration_ms=1000,
        returncode=0,
        stopped=False,
        adb_serial=None,
        selected_nodeids=[],
        steps=[{"kind": "case", "status": "passed"}],
        logs=[],
    )
    newer = build_run_report(
        run_id="newer",
        started_at="2026-04-27T02:00:00+00:00",
        finished_at="2026-04-27T02:00:01+00:00",
        duration_ms=1000,
        returncode=0,
        stopped=False,
        adb_serial=None,
        selected_nodeids=[],
        steps=[{"kind": "case", "status": "passed"}],
        logs=[],
    )

    store.save(older)
    store.save(newer)

    assert [item["run_id"] for item in store.list_reports()] == ["newer", "older"]
