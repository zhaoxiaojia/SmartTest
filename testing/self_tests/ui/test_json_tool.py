from __future__ import annotations

from ui import jsonTool


def test_json_tool_reads_writes_and_updates_app_data_json(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SMARTTEST_APP_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    jsonTool.write_json("test_page_state.json", {"case_parameters": {"case::one": {"loop": 2}}})
    assert jsonTool.read_json("test_page_state.json") == {"case_parameters": {"case::one": {"loop": 2}}}

    jsonTool.set_json_value("test_page_state.json", ["case_parameters", "case::one", "loop"], 3)
    assert jsonTool.get_json_value("test_page_state.json", ["case_parameters", "case::one", "loop"]) == 3


def test_json_tool_resolves_default_app_data_under_amlogic(monkeypatch) -> None:
    monkeypatch.delenv("SMARTTEST_APP_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/example/AppData/Local")

    path = jsonTool.app_data_dir()

    assert path.as_posix().endswith("AppData/Local/Amlogic/SmartTest")
