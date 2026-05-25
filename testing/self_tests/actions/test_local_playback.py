from __future__ import annotations

import subprocess

from testing.actions import local_playback
from testing.tool import adb as adb_tool


def test_parse_media_file_listing_keeps_supported_files_with_absolute_paths() -> None:
    output = "\n".join(
        [
            "/storage/emulated/0/Movies/srt001.mkv",
            "/storage/emulated/0/Movies/readme.txt",
            "/storage/1234-5678/Movies/demo.MP4",
            "",
        ]
    )

    assert local_playback.parse_media_file_listing(output) == [
        "/storage/emulated/0/Movies/srt001.mkv",
        "/storage/1234-5678/Movies/demo.MP4",
    ]


def test_list_media_files_queries_default_and_usb_movies_dirs_with_selected_serial(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, b"/storage/emulated/0/Movies/srt001.mkv\n", b"")

    monkeypatch.setattr(adb_tool.subprocess, "run", fake_run)

    assert local_playback.list_media_files("ABC123") == ["/storage/emulated/0/Movies/srt001.mkv"]
    assert calls == [
        [
            "adb",
            "-s",
            "ABC123",
            "shell",
            "find /storage/emulated/0/Movies /storage/*/Movies -maxdepth 1 -type f 2>/dev/null",
        ]
    ]


def test_build_stress_plan_expands_loop_files_and_actions() -> None:
    plan = local_playback.build_stress_plan(
        media_files=["/a.mkv", "/b.mp4"],
        actions=["pause", "play"],
        loop_count=2,
        random_playback=False,
    )

    assert [(item.loop_index, item.file_path, item.action) for item in plan] == [
        (1, "/a.mkv", "pause"),
        (1, "/a.mkv", "play"),
        (1, "/b.mp4", "pause"),
        (1, "/b.mp4", "play"),
        (2, "/a.mkv", "pause"),
        (2, "/a.mkv", "play"),
        (2, "/b.mp4", "pause"),
        (2, "/b.mp4", "play"),
    ]


def test_action_command_uses_media_keyevents_for_exoplayer_controls() -> None:
    assert local_playback.action_shell_command("pause") == ["input", "keyevent", "KEYCODE_MEDIA_PAUSE"]
    assert local_playback.action_shell_command("play") == ["input", "keyevent", "KEYCODE_MEDIA_PLAY"]
    assert local_playback.action_shell_command("seek_forward") == [
        "input",
        "keyevent",
        "KEYCODE_MEDIA_FAST_FORWARD",
    ]
    assert local_playback.action_shell_command("seek_backward") == [
        "input",
        "keyevent",
        "KEYCODE_MEDIA_REWIND",
    ]


def test_start_playback_quotes_file_uri_with_spaces(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(adb_tool.subprocess, "run", fake_run)

    local_playback.start_playback("/storage/A4F1-6FB4/Movies/Recording 2025.mp4", "ABC123")

    assert calls == [
        [
            "adb",
            "-s",
            "ABC123",
            "shell",
            "am start -a android.intent.action.VIEW "
            "-n com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer "
            "-d 'file:///storage/A4F1-6FB4/Movies/Recording 2025.mp4'",
        ]
    ]
