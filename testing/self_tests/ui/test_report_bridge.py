from __future__ import annotations

from datetime import datetime

from ui.example.bridge.ReportBridge import ReportBridge


def test_report_bridge_formats_utc_timestamp_as_local_time() -> None:
    bridge = ReportBridge.__new__(ReportBridge)
    raw = "2026-04-27T03:32:07+00:00"
    expected = datetime.fromisoformat(raw).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    assert bridge._format_timestamp(raw) == expected
