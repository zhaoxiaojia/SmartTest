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


def media_session(state: str = "PLAYING", file_name: str = "demo.mp4") -> str:
    state_code = {"PLAYING": 3, "PAUSED": 2}.get(state, 0)
    return (
        "MoviePlayer com.droidlogic.exoplayer2.demo/MoviePlayer (userId=0)\n"
        "active=true\n"
        f"state=PlaybackState {{state={state}({state_code}), position=0, buffered position=0, speed=1.0}}\n"
        f"metadata: size=2, description={file_name}, null, null"
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
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {"case_parameters": {nodeid: {"local_playback_stress:media_dir": "/storage/0E9D-A5F9/Video"}}},
    )
    dut = DummyDut(["/storage/0E9D-A5F9/Video/demo.mp4\n"])

    assert local_playback.list_media_files(dut, nodeid=nodeid) == ["/storage/0E9D-A5F9/Video/demo.mp4"]
    assert dut.shell_commands == ["find '/storage/0E9D-A5F9/Video' -maxdepth 1 -type f 2>/dev/null"]


def test_list_media_files_falls_back_to_default_scan_when_selected_directory_is_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
    nodeid = "testing/tests/android/stress/test_local_playback_stress.py::test_local_playback_stress"
    jsonTool.write_json(
        "test_page_state.json",
        {"case_parameters": {nodeid: {"local_playback_stress:media_dir": "/storage/0E9D-A5F9/Movies"}}},
    )
    dut = DummyDut(["", "/storage/A4F1-6FB4/Movies/demo.mp4\n"])

    assert local_playback.list_media_files(dut, nodeid=nodeid) == ["/storage/A4F1-6FB4/Movies/demo.mp4"]


def test_legacy_media_rw_directory_uses_storage_default_scan(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTTEST_APP_DATA_DIR", str(tmp_path))
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


def test_start_playback_quotes_file_uri_with_spaces() -> None:
    dut = DummyDut(["<hierarchy/>"] * 5)
    local_playback.LocalPlaybackFeature(dut).start_file("/storage/A4F1-6FB4/Movies/Recording 2025.mp4")

    assert dut.shell_commands[0] == (
        "am start -a android.intent.action.VIEW "
        "-n com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer "
        "-t video/mp4 "
        "-d 'file:///storage/A4F1-6FB4/Movies/Recording 2025.mp4'"
    )
    assert dut.taps == []


def test_start_playback_normalizes_media_rw_path_and_ts_mime() -> None:
    dut = DummyDut(["<hierarchy/>"] * 5)
    local_playback.LocalPlaybackFeature(dut).start_file("/mnt/media_rw/A4F1-6FB4/Movies/yulepingdao-hd.ts")

    assert dut.shell_commands[0] == (
        "am start -a android.intent.action.VIEW "
        "-n com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer "
        "-t video/mp2t "
        "-d 'file:///storage/A4F1-6FB4/Movies/yulepingdao-hd.ts'"
    )


def test_start_playback_dismisses_resume_dialog(monkeypatch) -> None:
    dump = (
        '<hierarchy>'
        '<node text="Resume playback from last position?" bounds="[300,300][1200,360]"/>'
        '<node text="Cancel" clickable="true" bounds="[500,500][680,580]"/>'
        '<node text="OK" clickable="true" bounds="[800,500][980,580]"/>'
        '</hierarchy>'
    )
    dut = DummyDut(["", "", dump])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)

    local_playback.LocalPlaybackFeature(dut).start_file("/storage/Movies/demo.mp4")

    assert dut.taps == [(590, 540)]


def test_dismiss_resume_dialog_ignores_cancel_without_resume_prompt(monkeypatch) -> None:
    dump = '<hierarchy><node text="Cancel" clickable="true" bounds="[500,500][680,580]"/></hierarchy>'
    dut = DummyDut(["", dump] * 5)
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)

    local_playback.dismiss_resume_dialog(dut)

    assert dut.taps == []


def test_stop_and_exit_player_use_package_and_back_key() -> None:
    dut = DummyDut()
    playback = local_playback.LocalPlaybackFeature(dut)

    playback.stop_player()
    playback.exit_player()

    assert dut.shell_commands == ["am force-stop com.droidlogic.exoplayer2.demo"]
    assert dut.keyevents == ["KEYCODE_BACK"]


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


def test_assert_media_session_state_rejects_wrong_state() -> None:
    dut = DummyDut()
    dut.media_session_output = media_session("PAUSED", "demo.mp4")

    try:
        local_playback.assert_media_session_state(dut, file_path="/storage/Movies/demo.mp4", expected_state="PLAYING")
    except AssertionError as exc:
        assert "media session state mismatch" in str(exc)
    else:
        raise AssertionError("Expected wrong media session state to fail")


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


def test_seek_to_end_sends_seek_swipe(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "capture_screen_image", lambda device: progress_image(height=1200, thumb_ratio=0.02))

    local_playback.run_action("seek_to_end", dut)

    assert dut.swipes == [(49, 1051, 1435, 1051, 700)]


def test_back_to_start_sends_seek_swipe(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        local_playback,
        "capture_screen_image",
        lambda device: progress_image(current="02:53", duration="05:09", height=1200, thumb_ratio=0.56),
    )

    local_playback.run_action("back_to_start", dut)

    assert dut.swipes == [(1073, 1051, 107, 1051, 700)]


def test_seek_swipe_falls_back_to_current_time_ratio_when_thumb_is_missing(monkeypatch) -> None:
    dut = DummyDut(["Physical size: 1920x1200"])
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        local_playback,
        "capture_screen_image",
        lambda device: progress_image(current="00:15", duration="00:28", height=1200),
    )

    local_playback.run_action("seek_to_end", dut)

    assert dut.swipes == [(1029, 1051, 1435, 1051, 700)]


def test_stress_action_safety_skips_seek_to_end_at_or_after_75_percent() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_to_end",
        local_playback.PlaybackProgress(21, 28),
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
    assert reason == "remaining_time_too_short"


def test_stress_action_safety_allows_forward_when_more_than_five_seconds_remain() -> None:
    allowed, reason = local_playback._stress_action_safety(
        "seek_forward",
        local_playback.PlaybackProgress(20, 28),
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


def test_verify_pause_sends_pause_and_play_without_post_action_assert(monkeypatch) -> None:
    dut = DummyDut()
    monkeypatch.setattr(local_playback.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(local_playback, "read_playback_progress", lambda device, **kwargs: local_playback.PlaybackProgress(10, 100))

    executed = local_playback.verify_stress_action(dut=dut, file_path="/storage/Movies/demo.mp4", action="pause")

    assert executed
    assert dut.keyevents == ["KEYCODE_MEDIA_PAUSE", "KEYCODE_MEDIA_PLAY"]
