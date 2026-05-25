from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Any, Iterable

from testing.runtime import step_log
from testing.tool.adb import run_adb as _run_adb


DEFAULT_MEDIA_DIR = "/storage/emulated/0/Movies"
EXOPLAYER_ACTIVITY = "com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer"
SUPPORTED_MEDIA_SUFFIXES = (".mkv", ".mp4", ".ts", ".webm", ".avi", ".mov", ".m4v")
DEFAULT_MEDIA_SCAN_COMMAND = (
    "find /storage/emulated/0/Movies /storage/*/Movies -maxdepth 1 -type f 2>/dev/null"
)

ACTION_KEYEVENTS = {
    "pause": "KEYCODE_MEDIA_PAUSE",
    "play": "KEYCODE_MEDIA_PLAY",
    "seek_forward": "KEYCODE_MEDIA_FAST_FORWARD",
    "seek_backward": "KEYCODE_MEDIA_REWIND",
    "back_to_start": "KEYCODE_MEDIA_PREVIOUS",
    "seek_to_end": "KEYCODE_MEDIA_NEXT",
}


@dataclass(frozen=True)
class StressAction:
    loop_index: int
    file_path: str
    action: str


def list_media_files(selected_serial: str | None = None) -> list[str]:
    result = _run_adb(
        selected_serial=selected_serial,
        args=[
            "shell",
            DEFAULT_MEDIA_SCAN_COMMAND,
        ],
        timeout=15.0,
        check=False,
    )
    if result.returncode != 0:
        return []
    return parse_media_file_listing(result.stdout)


def parse_media_file_listing(output: str) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for raw_line in str(output or "").splitlines():
        path = raw_line.strip()
        if not path or path in seen:
            continue
        if not path.lower().endswith(SUPPORTED_MEDIA_SUFFIXES):
            continue
        seen.add(path)
        files.append(path)
    return files


def discover_media_files(media_dir: str, selected_serial: str | None) -> list[str]:
    directory = _normalize_media_dir(media_dir)
    result = _run_adb(
        selected_serial=selected_serial,
        args=["shell", "find", directory, "-maxdepth", "1", "-type", "f"],
        timeout=20.0,
        check=True,
    )
    return parse_media_file_listing(result.stdout)


def build_stress_plan(
    *,
    media_files: Iterable[str],
    actions: Iterable[str],
    loop_count: int,
    random_playback: bool,
) -> list[StressAction]:
    normalized_files = _normalize_string_list(media_files)
    normalized_actions = [action for action in _normalize_string_list(actions) if action in ACTION_KEYEVENTS]
    total_loops = max(int(loop_count), 1)
    plan: list[StressAction] = []
    for loop_index in range(1, total_loops + 1):
        loop_files = list(normalized_files)
        if random_playback:
            random.shuffle(loop_files)
        for file_path in loop_files:
            for action in normalized_actions:
                plan.append(StressAction(loop_index=loop_index, file_path=file_path, action=action))
    return plan


def action_shell_command(action: str) -> list[str]:
    keyevent = ACTION_KEYEVENTS.get(str(action or "").strip())
    if not keyevent:
        raise ValueError(f"Unsupported local playback stress action: {action}")
    return ["input", "keyevent", keyevent]


def start_playback(file_path: str, selected_serial: str | None, *, timeout: float = 15.0) -> None:
    path = str(file_path or "").strip()
    if not path:
        raise ValueError("Playback file path is required.")
    uri = "file://" + path
    command = (
        "am start -a android.intent.action.VIEW "
        f"-n {EXOPLAYER_ACTIVITY} "
        f"-d {_shell_quote(uri)}"
    )
    _run_adb(
        selected_serial=selected_serial,
        args=["shell", command],
        timeout=timeout,
        check=True,
    )


def run_action(action: str, selected_serial: str | None, *, timeout: float = 10.0) -> None:
    _run_adb(
        selected_serial=selected_serial,
        args=["shell", *action_shell_command(action)],
        timeout=timeout,
        check=True,
    )


def run_local_playback_stress(
    *,
    params: dict[str, Any],
    selected_serial: str | None,
    trigger: str,
) -> None:
    media_dir = _normalize_media_dir(params.get("local_playback_stress:media_dir", DEFAULT_MEDIA_DIR))
    selected_files = _normalize_string_list(params.get("local_playback_stress:media_files", []))
    if not selected_files:
        selected_files = discover_media_files(media_dir, selected_serial)
    if not selected_files:
        raise AssertionError(f"No supported media files found in {media_dir}.")

    actions = _normalize_string_list(params.get("local_playback_stress:actions", []))
    if not actions:
        raise AssertionError("Select at least one local playback stress action.")

    loop_count = max(_int_param(params.get("local_playback_stress:loop_count", 1)), 1)
    random_playback = bool(params.get("local_playback_stress:random_playback", False))
    action_interval_sec = max(_float_param(params.get("local_playback_stress:action_interval_sec", 3)), 0.0)
    start_wait_sec = max(_float_param(params.get("local_playback_stress:start_wait_sec", 10)), 0.0)
    plan = build_stress_plan(
        media_files=selected_files,
        actions=actions,
        loop_count=loop_count,
        random_playback=random_playback,
    )
    step_log(
        "local_playback_stress "
        f"trigger={trigger} dut={selected_serial or '<default>'} "
        f"files={len(selected_files)} actions={len(actions)} loops={loop_count}"
    )

    active_file = ""
    for item in plan:
        if item.file_path != active_file:
            step_log(f"loop={item.loop_index}/{loop_count} start file={item.file_path}")
            start_playback(item.file_path, selected_serial)
            active_file = item.file_path
            if start_wait_sec:
                time.sleep(start_wait_sec)
        step_log(f"loop={item.loop_index}/{loop_count} action={item.action} file={item.file_path}")
        run_action(item.action, selected_serial)
        if action_interval_sec:
            time.sleep(action_interval_sec)


def _normalize_media_dir(value: Any) -> str:
    directory = str(value or "").strip()
    return directory or DEFAULT_MEDIA_DIR


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_values = [str(item or "").strip() for item in value]
    else:
        raw_values = [str(value or "").strip()]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        if item and item not in seen:
            seen.add(item)
            normalized.append(item)
    return normalized


def _int_param(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_param(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"
