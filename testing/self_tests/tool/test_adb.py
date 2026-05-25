from __future__ import annotations

from testing.tool.adb import build_adb_command


def test_build_adb_command_uses_selected_safe_serial() -> None:
    assert build_adb_command(selected_serial="ABC123", args=["shell", "id"]) == [
        "adb",
        "-s",
        "ABC123",
        "shell",
        "id",
    ]


def test_build_adb_command_falls_back_to_default_for_unsafe_serial() -> None:
    assert build_adb_command(selected_serial="0099360090052090260214801F41D0F脗", args=["shell", "id"]) == [
        "adb",
        "shell",
        "id",
    ]
