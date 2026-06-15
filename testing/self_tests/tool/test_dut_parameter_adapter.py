from __future__ import annotations

from testing.tool.dut_tool.parameter_adapter import DutParameterAdapter
from ui import jsonTool


class _FakeDut:
    def __init__(self, serial: str) -> None:
        self.serial = serial
        self.commands: list[str] = []

    def run_device_shell(self, command: str) -> str:
        self.commands.append(command)
        return "\n".join(
            [
                "/storage/emulated/0/Movies/movie_a.mp4",
                "/storage/emulated/0/Movies/readme.txt",
                "/storage/A4F1-6FB4/Video/movie_b.mkv",
            ]
        )


def test_adapter_refreshes_dut_list_through_injected_lister() -> None:
    adapter = DutParameterAdapter(device_lister=lambda: ["ABC123", "XYZ789"])

    assert adapter.refresh_duts() == ["ABC123", "XYZ789"]


def test_adapter_refresh_duts_ensures_apk_for_selected_device() -> None:
    ensure_calls: list[tuple[str, bool]] = []
    adapter = DutParameterAdapter(
        device_lister=lambda: ["ABC123", "XYZ789"],
        apk_ensurer=lambda *, adb_serial=None, require_privileged=True: ensure_calls.append(
            (adb_serial or "<default>", require_privileged)
        ) or False,
    )

    assert adapter.refresh_duts(selected_serial="XYZ789") == ["ABC123", "XYZ789"]
    assert ensure_calls == [("XYZ789", True)]


def test_adapter_refresh_duts_does_not_install_single_device_without_selection() -> None:
    ensure_calls: list[str] = []
    adapter = DutParameterAdapter(
        device_lister=lambda: ["ABC123"],
        apk_ensurer=lambda *, adb_serial=None, require_privileged=True: ensure_calls.append(adb_serial or "<default>") or False,
    )

    assert adapter.refresh_duts() == ["ABC123"]
    assert ensure_calls == []


def test_adapter_refresh_duts_does_not_install_when_multiple_devices_without_selection() -> None:
    ensure_calls: list[str] = []
    adapter = DutParameterAdapter(
        device_lister=lambda: ["ABC123", "XYZ789"],
        apk_ensurer=lambda *, adb_serial=None, require_privileged=True: ensure_calls.append(adb_serial or "<default>") or False,
    )

    assert adapter.refresh_duts() == ["ABC123", "XYZ789"]
    assert ensure_calls == []


def test_adapter_refresh_duts_keeps_devices_when_apk_ensure_fails() -> None:
    adapter = DutParameterAdapter(
        device_lister=lambda: ["ABC123"],
        apk_ensurer=lambda *, adb_serial=None, require_privileged=True: (_ for _ in ()).throw(RuntimeError("install failed")),
    )

    assert adapter.refresh_duts(selected_serial="ABC123") == ["ABC123"]


def test_adapter_routes_local_playback_options_from_persisted_case_parameters(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {
            "case_parameters": {
                nodeid: {
                    "local_playback_stress:media_dir": "/storage/A4F1-6FB4/Video",
                }
            }
        },
    )
    created: list[_FakeDut] = []

    def make_dut(serial: str | None) -> _FakeDut:
        dut = _FakeDut(str(serial or ""))
        created.append(dut)
        return dut

    adapter = DutParameterAdapter(dut_factory=make_dut)

    result = adapter.refresh_case_parameter_options(
        "testing.tool.dut_tool.features.local_playback:list_media_files",
        "ABC123",
        nodeid=nodeid,
    )

    assert result.error == ""
    assert result.options == [
        "/storage/emulated/0/Movies/movie_a.mp4",
        "/storage/A4F1-6FB4/Video/movie_b.mkv",
    ]
    assert created[0].serial == "ABC123"
    assert created[0].commands == [
        "find '/storage/A4F1-6FB4/Video' -maxdepth 1 -type f 2>/dev/null",
    ]


def test_adapter_routes_local_playback_directory_options_through_dut() -> None:
    created: list[_FakeDut] = []

    def make_dut(serial: str | None) -> _FakeDut:
        dut = _FakeDut(str(serial or ""))
        dut.run_device_shell = lambda command: "\n".join(  # type: ignore[method-assign]
            [
                "/storage/A4F1-6FB4/Movies",
                "/storage/A4F1-6FB4/Download",
            ]
        )
        created.append(dut)
        return dut

    adapter = DutParameterAdapter(dut_factory=make_dut)

    result = adapter.refresh_case_parameter_options(
        "testing.tool.dut_tool.features.local_playback:list_media_dirs",
        "ABC123",
    )

    assert result.error == ""
    assert result.options == ["/storage/A4F1-6FB4/Movies"]
    assert created[0].serial == "ABC123"


def test_adapter_refreshes_connected_bluetooth_targets_from_dut(monkeypatch) -> None:
    from testing.tool.dut_tool.features import bluetooth

    monkeypatch.setattr(
        bluetooth,
        "list_connected_bluetooth_targets",
        lambda selected_serial=None: ["None", "Speaker [11:22:33:44:55:66]"],
    )
    adapter = DutParameterAdapter()

    result = adapter.refresh_case_parameter_options(
        "testing.tool.dut_tool.features.bluetooth:list_connected_bluetooth_targets",
        "ABC123",
    )

    assert result.error == ""
    assert result.options == ["None", "Speaker [11:22:33:44:55:66]"]


def test_adapter_returns_empty_options_and_error_when_dut_provider_fails() -> None:
    adapter = DutParameterAdapter(dut_factory=lambda serial: (_ for _ in ()).throw(RuntimeError("no dut")))

    result = adapter.refresh_case_parameter_options(
        "testing.tool.dut_tool.features.local_playback:list_media_files",
        "ABC123",
    )

    assert result.options == []
    assert result.error == "no dut"
