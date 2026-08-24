from __future__ import annotations

import asyncio

from testing.tool.dut_tool.parameter_helper import ParameterHelper
from client.app.ui.example.bridge.TestPageBridge import TestPageBridge as PageBridge


def test_dut_scan_publishes_without_waiting_for_android_client_prepare() -> None:
    calls: list[str] = []
    helper = ParameterHelper(
        device_lister=lambda: calls.append("scan") or ["dut-1"],
        apk_ensurer=lambda **_kwargs: calls.append("prepare") or True,
    )

    assert helper.refresh_duts() == ["dut-1"]
    assert calls == ["scan"]


def test_android_client_prepare_reports_real_stage_callback() -> None:
    stages: list[tuple[str, int, str]] = []
    helper = ParameterHelper(
        device_lister=lambda: ["dut-1"],
        apk_ensurer=lambda **kwargs: (
            kwargs["stage_callback"]("verify", 100, "verified") or True
        ),
    )

    result = asyncio.run(
        helper.prepare_android_client_async(
            "dut-1", stage_callback=lambda stage, value, detail: stages.append((stage, value, detail))
        )
    )

    assert result is True
    assert stages == [("verify", 100, "verified")]


def test_bridge_publishes_dut_list_before_awaiting_prepare() -> None:
    events: list[str] = []

    class FakeHelper:
        async def refresh_duts_async(self, **_kwargs):
            events.append("scan")
            return ["dut-1"]

        async def prepare_android_client_async(self, _serial, **_kwargs):
            events.append("prepare")
            return True

    bridge = PageBridge.__new__(PageBridge)
    bridge._parameter_helper = FakeHelper()
    bridge._adb_devices = []
    bridge._adb_refresh_phase = "scan"
    bridge._publish_adb_devices = lambda devices, _elapsed: (
        setattr(bridge, "_adb_devices", list(devices)), events.append("publish")
    )
    bridge._finish_adb_refresh = lambda **_kwargs: events.append("finish")

    asyncio.run(bridge._refresh_adb_devices_task(""))

    assert events == ["scan", "publish", "prepare", "finish"]


def test_duplicate_refresh_is_ignored_while_sequence_is_running() -> None:
    bridge = PageBridge.__new__(PageBridge)
    bridge._adb_refresh_running = True
    traces: list[tuple[str, str]] = []
    bridge._trace = lambda stage, **values: traces.append((stage, values["reason"]))
    bridge._create_task = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("scheduled twice"))

    bridge._schedule_adb_refresh("user_refresh")

    assert traces == [("adb_refresh_skip_running", "user_refresh")]
