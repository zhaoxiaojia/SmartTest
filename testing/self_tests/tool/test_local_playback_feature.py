from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from testing.tool.dut_tool.features import local_playback
from ui import jsonTool


class DummyDut:
    EXOPLAYER_DEMO_COMPONENT = "com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer"

    def __init__(self, shell_outputs: list[str] | None = None) -> None:
        self.shell_commands: list[str] = []
        self.keyevents: list[str] = []
        self.taps: list[tuple[int, int]] = []
        self.swipes: list[tuple[int, int, int, int, int]] = []
        self.shell_outputs = list(shell_outputs or [])
        self.media_session_output = ""

    def run_device_shell(self, command: str) -> str:
        self.shell_commands.append(command)
        if command == "dumpsys media_session":
            return self.media_session_output
        if self.shell_outputs:
            return self.shell_outputs.pop(0)
        return ""

    def keyevent(self, keycode: str) -> None:
        self.keyevents.append(keycode)

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))

    def swipe(self, x_start: int, y_start: int, x_end: int, y_end: int, duration: int) -> None:
        self.swipes.append((x_start, y_start, x_end, y_end, duration))


def progress_image(
    *,
    current: str = "00:10",
    duration: str = "2:28:08",
    width: int = 1920,
    height: int = 1200,
    thumb_ratio: float | None = None,
) -> Image.Image:
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    y = height - 150
    draw.line((12, y, width - 12, y), fill=(80, 80, 80), width=4)
    if thumb_ratio is not None:
        thumb_x = 12 + int((width - 24) * thumb_ratio)
        draw.ellipse((thumb_x - 10, y - 10, thumb_x + 10, y + 10), fill=(255, 255, 255))
    draw.text((22, height - 79), current, font=font, fill=(255, 255, 255))
    draw.text((88, height - 79), ".", font=font, fill=(170, 170, 170))
    draw.text((106, height - 79), duration, font=font, fill=(170, 170, 170))
    return image


def resume_dialog_image(*, width: int = 1920, height: int = 1200, buttons: int = 2) -> Image.Image:
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    dialog = (
        int(width * 0.292),
        int(height * 0.402),
        int(width * 0.707),
        int(height * 0.597),
    )
    draw.rectangle(dialog, fill=(64, 64, 64))
    try:
        title_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 32)
        body_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.text((dialog[0] + 24, dialog[1] + 28), "Resume playback", font=title_font, fill=(230, 230, 230))
    draw.text((dialog[0] + 24, dialog[1] + 88), "Resume from last position?", font=body_font, fill=(210, 210, 210))
    button_y = dialog[1] + int((dialog[3] - dialog[1]) * 0.72)
    button_positions = [dialog[0] + int((dialog[2] - dialog[0]) * 0.62)]
    if buttons >= 2:
        button_positions.append(dialog[0] + int((dialog[2] - dialog[0]) * 0.84))
    for index, x in enumerate(button_positions[:buttons]):
        draw.text((x, button_y), "Cancel" if index == 0 else "OK", font=body_font, fill=(0, 188, 174))
    return image


def media_session(state: str = "PLAYING", file_name: str = "demo.mp4") -> str:
    state_code = {"STOPPED": 1, "PAUSED": 2, "PLAYING": 3, "BUFFERING": 6}.get(state, 0)
    return (
        "MoviePlayer com.droidlogic.exoplayer2.demo/MoviePlayer (userId=0)\n"
        "active=true\n"
        f"state=PlaybackState {{state={state}({state_code}), position=0, buffered position=0, speed=1.0}}\n"
        f"metadata: size=2, description={file_name}, null, null"
    )


def bluetooth_error_session_with_stale_exoplayer_package() -> str:
    return (
        "BluetoothMediaBrowserService com.android.bluetooth/BluetoothMediaBrowserService (userId=0)\n"
        "package=com.android.bluetooth\n"
        "active=false\n"
        "state=PlaybackState {state=ERROR(7), position=0, buffered position=0, speed=0.0, error=Bluetooth disconnected}\n"
        "metadata: null\n"
        "Audio playback (lastly played comes first)\n"
        "uid=10029 packages=com.droidlogic.exoplayer2.demo\n"
    )


def test_parse_media_file_listing_keeps_supported_files_with_absolute_paths() -> None:
    output = "\n".join(["/storage/1234-5678/Movies/demo.MP4", "/storage/1234-5678/Movies/readme.txt", ""])

    assert local_playback.parse_media_file_listing(output) == ["/storage/1234-5678/Movies/demo.MP4"]


def test_list_media_files_queries_usb_storage_movies_and_video_dirs() -> None:
    dut = DummyDut(["/storage/1234-5678/Movies/demo.mp4\n"])

    assert local_playback.list_media_files(dut) == ["/storage/1234-5678/Movies/demo.mp4"]
    assert dut.shell_commands == [
        "find /storage/*/Movies /storage/*/Video -maxdepth 1 -type f 2>/dev/null",
    ]


def test_list_media_dirs_queries_dut_storage_media_directories() -> None:
    dut = DummyDut(["/storage/A4F1-6FB4/Movies\n/storage/A4F1-6FB4/Video\n/storage/A4F1-6FB4/Download\n"])

    assert local_playback.list_media_dirs(dut=dut) == [
        "/storage/A4F1-6FB4/Movies",
        "/storage/A4F1-6FB4/Video",
    ]


def test_list_media_files_queries_selected_media_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {"case_parameters": {nodeid: {"local_playback_stress:media_dir": "/storage/0E9D-A5F9/Video"}}},
    )
    dut = DummyDut(["/storage/0E9D-A5F9/Video/demo.mp4\n"])

    assert local_playback.list_media_files(dut, nodeid=nodeid) == ["/storage/0E9D-A5F9/Video/demo.mp4"]
    assert dut.shell_commands == ["find '/storage/0E9D-A5F9/Video' -maxdepth 1 -type f 2>/dev/null"]


def test_list_media_files_does_not_fall_back_when_selected_directory_is_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {"case_parameters": {nodeid: {"local_playback_stress:media_dir": "/storage/0E9D-A5F9/Movies"}}},
    )
    dut = DummyDut(["", "/storage/A4F1-6FB4/Movies/demo.mp4\n"])

    assert local_playback.list_media_files(dut, nodeid=nodeid) == []
    assert dut.shell_commands == ["find '/storage/0E9D-A5F9/Movies' -maxdepth 1 -type f 2>/dev/null"]


def test_legacy_media_rw_directory_uses_storage_default_scan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {"case_parameters": {nodeid: {"local_playback_stress:media_dir": "/mnt/media_rw/*/Movies"}}},
    )
    dut = DummyDut(["/storage/0E9D-A5F9/Video/demo.mp4\n"])

    assert local_playback.list_media_files(dut, nodeid=nodeid) == ["/storage/0E9D-A5F9/Video/demo.mp4"]


def test_build_stress_plan_expands_loop_files_and_actions() -> None:
    plan = local_playback.build_stress_plan(
        media_files=["/a.mkv", "/b.mp4"],
        actions=["pause", "seek_forward"],
        loop_count=2,
        random_playback=False,
    )

    assert len(plan) == 16
    assert sorted({item.loop_index for item in plan}) == [1, 2]


def test_start_playback_quotes_file_uri_with_spaces(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: Image.new("RGB", (1920, 1200), "black"))

    local_playback.LocalPlaybackFeature(dut).start_file("/storage/A4F1-6FB4/Movies/Recording 2025.mp4")

    assert dut.shell_commands[0] == (
        "am start -a android.intent.action.VIEW "
        "-n com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer "
        "-t video/mp4 "
        "-d 'file:///storage/A4F1-6FB4/Movies/Recording 2025.mp4'"
    )
    assert dut.taps == []


def test_start_playback_normalizes_media_rw_path_and_ts_mime(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: Image.new("RGB", (1920, 1200), "black"))

    local_playback.LocalPlaybackFeature(dut).start_file("/mnt/media_rw/A4F1-6FB4/Movies/yulepingdao-hd.ts")

    assert dut.shell_commands[0] == (
        "am start -a android.intent.action.VIEW "
        "-n com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer "
        "-t video/mp2t "
        "-d 'file:///storage/A4F1-6FB4/Movies/yulepingdao-hd.ts'"
    )


def test_start_playback_dismisses_resume_dialog(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: resume_dialog_image())

    local_playback.LocalPlaybackFeature(dut).start_file("/storage/Movies/demo.mp4")

    assert len(dut.taps) == 1
    x, y = dut.taps[0]
    assert 1040 <= x <= 1135
    assert 640 <= y <= 675


def test_dismiss_resume_dialog_ignores_plain_black_screen(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: Image.new("RGB", (1920, 1200), "black"))

    local_playback.dismiss_resume_dialog(dut)

    assert dut.taps == []


def test_dismiss_resume_dialog_requires_two_resume_buttons(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: resume_dialog_image(buttons=1))

    local_playback.dismiss_resume_dialog(dut)

    assert dut.taps == []


def test_stop_and_exit_player_use_package_and_back_key(monkeypatch) -> None:
    dut = DummyDut()
    playback = local_playback.LocalPlaybackFeature(dut)
    logs: list[str] = []
    monkeypatch.setattr(local_playback, "step_log", logs.append)

    playback.stop_player()
    playback.exit_player()

    assert dut.shell_commands == ["am force-stop com.droidlogic.exoplayer2.demo"]
    assert dut.keyevents == ["KEYCODE_BACK"]
    assert logs[-1] == "local_playback_exit_player keyevent=KEYCODE_BACK"


def test_direct_stress_actions_use_media_keyevents() -> None:
    dut = DummyDut()

    local_playback.run_action("pause", dut)
    local_playback.run_action("seek_forward", dut)
    local_playback.run_action("seek_backward", dut)

    assert dut.keyevents == ["KEYCODE_MEDIA_PAUSE", "KEYCODE_MEDIA_FAST_FORWARD", "KEYCODE_MEDIA_REWIND"]


def test_assert_media_session_state_accepts_matching_file() -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PLAYING", "demo.mp4")

    local_playback.assert_media_session_state(dut, file_path="/storage/Movies/demo.mp4", expected_state="PLAYING")


def test_assert_media_session_state_waits_for_start_buffering(monkeypatch) -> None:
    dut = DummyDut()
    states = iter([media_session("BUFFERING", "demo.mp4"), media_session("PLAYING", "demo.mp4")])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)

    def shell(command: str) -> str:
        dut.shell_commands.append(command)
        if command == "dumpsys media_session":
            return next(states)
        return ""

    dut.run_device_shell = shell

    local_playback.assert_media_session_state(dut, file_path="/storage/Movies/demo.mp4", expected_state="PLAYING")

    assert dut.shell_commands == ["dumpsys media_session", "dumpsys media_session"]


def test_assert_media_session_state_rejects_wrong_state() -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PAUSED", "demo.mp4")

    try:
        local_playback.assert_media_session_state(dut, file_path="/storage/Movies/demo.mp4", expected_state="PLAYING")
    except AssertionError as exc:
        assert "media session state mismatch" in str(exc)
    else:
        raise AssertionError("Expected wrong media session state to fail")


def test_media_session_parser_ignores_non_movieplayer_error_session() -> None:
    dump = bluetooth_error_session_with_stale_exoplayer_package()

    assert local_playback._media_session_state(dump) is None
    assert not local_playback._media_session_matches_file(dump, "/storage/Movies/demo.mp4")
    assert local_playback._media_session_state_summary(dump) == "pkg=False active=unknown state=unknown"


def test_media_session_parser_reads_only_movieplayer_session_when_bluetooth_error_exists() -> None:
    dump = media_session("PLAYING", "demo.mp4") + "\n" + bluetooth_error_session_with_stale_exoplayer_package()

    assert local_playback._media_session_state(dump) == "PLAYING"
    assert local_playback._media_session_matches_file(dump, "/storage/Movies/demo.mp4")
    assert local_playback._media_session_state_summary(dump) == "pkg=True active=true state=PLAYING(3)"


def test_read_playback_progress_reads_visible_controls_before_tapping(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: progress_image(current="02:53", duration="05:09"))

    progress = local_playback.read_playback_progress(dut)

    assert progress.current_seconds == 173
    assert progress.duration_seconds == 309
    assert dut.taps == []


def test_read_playback_progress_retries_three_times_before_failing(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1080"] * 3)
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: Image.new("RGB", (1920, 1200), "black"))

    try:
        local_playback.read_playback_progress(dut)
    except AssertionError as exc:
        assert "Unable to read local playback progress from screenshot" in str(exc)
        assert "attempts=3" in str(exc)
    else:
        raise AssertionError("Expected missing progress controls to fail")
    assert len(dut.taps) == 2


def test_read_playback_progress_retries_until_controls_are_captured(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1080"] * 2)
    images = iter([Image.new("RGB", (1920, 1200), "black"), progress_image(current="00:44", duration="2:28:08")])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: next(images))

    progress = local_playback.read_playback_progress(dut)

    assert progress.current_seconds == 44
    assert progress.duration_seconds == 8888
    assert len(dut.taps) == 1


def test_read_playback_progress_retries_when_ocr_current_exceeds_duration(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1080"] * 2)
    images = iter([progress_image(current="80:02", duration="18:53"), progress_image(current="00:21", duration="18:53")])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: next(images))

    progress = local_playback.read_playback_progress(dut)

    assert progress.current_seconds == 21
    assert progress.duration_seconds == 1133
    assert len(dut.taps) == 1


def test_read_playback_progress_allows_tiny_end_of_file_ocr_overshoot(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: progress_image(current="18:54", duration="18:53"))

    progress = local_playback.read_playback_progress(dut)

    assert progress.current_seconds == 1133
    assert progress.duration_seconds == 1133
    assert dut.taps == []


def test_seek_to_end_taps_target_progress(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: progress_image(height=1200, thumb_ratio=0.02))

    local_playback.run_action("seek_to_end", dut)

    assert dut.taps == [(1435, 1051)]
    assert dut.swipes == []


def test_back_to_start_taps_target_progress(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        local_playback,
        "capture_screen_image",
        lambda device: progress_image(current="02:53", duration="05:09", height=1200, thumb_ratio=0.56),
    )

    local_playback.run_action("back_to_start", dut)

    assert dut.taps == [(107, 1051)]
    assert dut.swipes == []


def test_seek_tap_does_not_depend_on_thumb_when_thumb_is_missing(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        local_playback,
        "capture_screen_image",
        lambda device: progress_image(current="00:15", duration="00:28", height=1200),
    )

    local_playback.run_action("seek_to_end", dut)

    assert dut.taps == [(1435, 1051)]
    assert dut.swipes == []


def test_verify_stress_action_uses_50_percent_seek_to_end_for_short_video(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    dut.media_session_output = media_session("PLAYING", "short.mp4")
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        local_playback,
        "capture_screen_image",
        lambda device: progress_image(current="00:15", duration="01:59", height=1200, thumb_ratio=0.1),
    )

    executed = local_playback.verify_stress_action(
        dut=dut,
        file_path="/storage/Movies/short.mp4",
        action="seek_to_end",
    )

    assert executed is True
    assert dut.taps == [(961, 1051)]
    assert dut.swipes == []


def test_verify_stress_action_keeps_75_percent_seek_to_end_for_two_minute_video(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    dut.media_session_output = media_session("PLAYING", "two_minutes.mp4")
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        local_playback,
        "capture_screen_image",
        lambda device: progress_image(current="00:15", duration="02:00", height=1200, thumb_ratio=0.1),
    )

    executed = local_playback.verify_stress_action(
        dut=dut,
        file_path="/storage/Movies/two_minutes.mp4",
        action="seek_to_end",
    )

    assert executed is True
    assert dut.taps == [(1435, 1051)]
    assert dut.swipes == []


def test_stress_action_safety_skips_seek_to_end_at_or_after_75_percent() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_to_end",
        local_playback.PlaybackProgress(21, 28),
        action_interval_sec=3,
    )

    assert not allowed
    assert reason == "seek_to_end_already_near_target"


def test_stress_action_safety_skips_short_video_seek_to_end_at_or_after_50_percent() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_to_end",
        local_playback.PlaybackProgress(60, 119),
        action_interval_sec=3,
    )

    assert not allowed
    assert reason == "seek_to_end_already_near_target"


def test_stress_action_safety_skips_forward_when_remaining_time_is_small() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_forward",
        local_playback.PlaybackProgress(24, 28),
        action_interval_sec=3,
    )

    assert not allowed
    assert reason == "video_too_short_for_seek_forward"


def test_stress_action_safety_skips_forward_for_short_video() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_forward",
        local_playback.PlaybackProgress(20, 28),
        action_interval_sec=3,
    )

    assert not allowed
    assert reason == "video_too_short_for_seek_forward"


def test_stress_action_safety_allows_forward_when_long_video_has_enough_remaining_time() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_forward",
        local_playback.PlaybackProgress(20, 120),
        action_interval_sec=3,
    )

    assert allowed
    assert reason == "safe"


def test_stress_action_safety_allows_backward_even_when_remaining_time_is_small() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_backward",
        local_playback.PlaybackProgress(21, 28),
        action_interval_sec=3,
    )

    assert allowed
    assert reason == "safe"


def test_stress_action_safety_allows_long_video_seek_to_end() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_to_end",
        local_playback.PlaybackProgress(5, 360),
        action_interval_sec=3,
    )

    assert allowed
    assert reason == "safe"


def test_stress_action_safety_allows_short_video_back_to_start() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "back_to_start",
        local_playback.PlaybackProgress(21, 28),
        action_interval_sec=3,
    )

    assert allowed
    assert reason == "safe"


def test_verify_stress_action_skips_unsafe_action_with_diagnostic_log(monkeypatch) -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PLAYING", "short.mp4")
    logs: list[str] = []
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(21, 28))
    monkeypatch.setattr(local_playback, "step_log", logs.append)

    executed = local_playback.verify_stress_action(
        dut=dut,
        file_path="/storage/Movies/short.mp4",
        action="seek_to_end",
        action_interval_sec=3,
    )

    assert executed is False
    assert dut.swipes == []
    assert logs == [
        "local_playback_action_skipped action=seek_to_end file=/storage/Movies/short.mp4 "
        "current=21 duration=28 remaining=7 reason=seek_to_end_already_near_target"
    ]


def test_verify_stress_action_skips_when_preflight_progress_is_unreadable(monkeypatch) -> None:
    dut = DummyDut()
    logs: list[str] = []

    def raise_unreadable(device, **kwargs) -> local_playback.PlaybackProgress:
        raise AssertionError("Unable to read local playback progress from screenshot after retries.")

    monkeypatch.setattr(local_playback, "read_playback_progress", raise_unreadable)
    monkeypatch.setattr(local_playback, "step_log", logs.append)

    executed = local_playback.verify_stress_action(
        dut=dut,
        file_path="/storage/Movies/short.mp4",
        action="seek_forward",
        action_interval_sec=3,
    )

    assert executed is None
    assert dut.keyevents == []
    assert logs == [
        "local_playback_action_skipped action=seek_forward file=/storage/Movies/short.mp4 "
        "current=unknown duration=unknown remaining=unknown "
        "reason=playback_progress_unreadable media=pkg=False active=unknown state=unknown "
        "detail=Unable to read local playback progress from screenshot after retries."
    ]


def test_verify_stress_action_keeps_file_plan_when_unreadable_but_media_is_playing(monkeypatch) -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PLAYING", "short.mp4")

    def raise_unreadable(device, **kwargs) -> local_playback.PlaybackProgress:
        raise AssertionError("no progress")

    monkeypatch.setattr(local_playback, "read_playback_progress", raise_unreadable)

    executed = local_playback.verify_stress_action(
        dut=dut,
        file_path="/storage/Movies/short.mp4",
        action="seek_forward",
        action_interval_sec=3,
    )

    assert executed is False


def test_verify_action_aborts_when_preflight_media_session_is_not_playing(monkeypatch) -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("STOPPED", "demo.mp4")
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="pause")

    assert executed is None
    assert dut.keyevents == []


def test_verify_pause_requires_post_action_playing_state(monkeypatch) -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PLAYING", "demo.mp4")
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="pause")

    assert executed
    assert dut.keyevents == ["KEYCODE_MEDIA_PAUSE", "KEYCODE_MEDIA_PLAY"]


def test_verify_action_aborts_when_post_action_state_is_stopped(monkeypatch) -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PLAYING", "demo.mp4")
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    states = iter([media_session("PLAYING", "demo.mp4"), media_session("STOPPED", "demo.mp4")])

    def shell(command: str) -> str:
        dut.shell_commands.append(command)
        if command == "dumpsys media_session":
            return next(states)
        return ""

    dut.run_device_shell = shell

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="seek_backward")

    assert executed is None
    assert dut.keyevents == ["KEYCODE_MEDIA_REWIND"]


def test_verify_action_waits_for_buffering_to_return_to_playing(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    states = iter(
        [
            media_session("PLAYING", "demo.mp4"),
            media_session("BUFFERING", "demo.mp4"),
            media_session("PLAYING", "demo.mp4"),
        ]
    )

    def shell(command: str) -> str:
        dut.shell_commands.append(command)
        if command == "dumpsys media_session":
            return next(states)
        return ""

    dut.run_device_shell = shell

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="seek_backward")

    assert executed is True
    assert dut.keyevents == ["KEYCODE_MEDIA_REWIND"]


def test_verify_action_presses_play_once_when_buffering_persists(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    states = iter(
        [
            media_session("PLAYING", "demo.mp4"),
            media_session("BUFFERING", "demo.mp4"),
            media_session("BUFFERING", "demo.mp4"),
            media_session("BUFFERING", "demo.mp4"),
            media_session("PLAYING", "demo.mp4"),
        ]
    )

    def shell(command: str) -> str:
        dut.shell_commands.append(command)
        if command == "dumpsys media_session":
            return next(states)
        return ""

    dut.run_device_shell = shell

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="seek_backward")

    assert executed is True
    assert dut.keyevents == ["KEYCODE_MEDIA_REWIND", "KEYCODE_MEDIA_PLAY"]


def test_verify_action_resumes_when_post_action_state_is_paused(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    states = iter(
        [
            media_session("PLAYING", "demo.mp4"),
            media_session("PAUSED", "demo.mp4"),
            media_session("PLAYING", "demo.mp4"),
        ]
    )

    def shell(command: str) -> str:
        dut.shell_commands.append(command)
        if command == "dumpsys media_session":
            return next(states)
        return ""

    dut.run_device_shell = shell

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="seek_backward")

    assert executed is True
    assert dut.keyevents == ["KEYCODE_MEDIA_REWIND", "KEYCODE_MEDIA_PLAY"]


def test_wait_for_playback_finished_after_actions_detects_stopped(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device: local_playback.PlaybackProgress(90, 100))
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    ticks = iter([0.0, 1.0, 2.0, 3.0])
    monkeypatch.setattr(local_playback.time, "monotonic", lambda: next(ticks))
    states = iter([media_session("PLAYING", "demo.mp4"), media_session("STOPPED", "demo.mp4")])

    def shell(command: str) -> str:
        dut.shell_commands.append(command)
        if command == "dumpsys media_session":
            return next(states)
        return ""

    dut.run_device_shell = shell

    assert local_playback._wait_for_playback_finished_after_actions(dut, "/storage/Movies/demo.mp4")


def test_wait_for_playback_finished_after_actions_times_out_when_still_current_file(monkeypatch) -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PLAYING", "demo.mp4")
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device: local_playback.PlaybackProgress(99, 100))
    ticks = iter([0.0, 31.0])
    monkeypatch.setattr(local_playback.time, "monotonic", lambda: next(ticks))

    assert not local_playback._wait_for_playback_finished_after_actions(dut, "/storage/Movies/demo.mp4")
