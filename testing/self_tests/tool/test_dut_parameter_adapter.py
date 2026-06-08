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


def test_adapter_routes_local_playback_options_from_persisted_case_parameters(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
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


def test_adapter_returns_empty_options_and_error_when_dut_provider_fails() -> None:
    adapter = DutParameterAdapter(dut_factory=lambda serial: (_ for _ in ()).throw(RuntimeError("no dut")))

    result = adapter.refresh_case_parameter_options(
        "testing.tool.dut_tool.features.local_playback:list_media_files",
        "ABC123",
    )

    assert result.options == []
    assert result.error == "no dut"
