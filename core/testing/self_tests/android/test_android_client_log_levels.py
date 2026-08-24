from __future__ import annotations

import subprocess

from mobile import android as android_client


def test_successful_adb_stderr_is_info_and_empty_streams_are_not_logged(monkeypatch) -> None:
    records: list[tuple[str, str]] = []
    monkeypatch.setattr(
        android_client,
        "smart_log",
        lambda message, **kwargs: records.append((str(message), str(kwargs.get("level", "info")))),
    )

    android_client._log_process_result(
        "adb remount",
        subprocess.CompletedProcess(["adb", "remount"], 0, "", "remount succeeded"),
    )

    assert records == [("adb remount stderr: remount succeeded", "info")]


def test_failed_adb_stderr_remains_error(monkeypatch) -> None:
    records: list[tuple[str, str]] = []
    monkeypatch.setattr(
        android_client,
        "smart_log",
        lambda message, **kwargs: records.append((str(message), str(kwargs.get("level", "info")))),
    )

    android_client._log_process_result(
        "adb remount",
        subprocess.CompletedProcess(["adb", "remount"], 1, "", "permission denied"),
    )

    assert records == [("adb remount stderr: permission denied", "error")]


def test_unexpected_success_stderr_remains_warning(monkeypatch) -> None:
    records: list[tuple[str, str]] = []
    monkeypatch.setattr(
        android_client,
        "smart_log",
        lambda message, **kwargs: records.append((str(message), str(kwargs.get("level", "info")))),
    )

    android_client._log_process_result(
        "install",
        subprocess.CompletedProcess(["adb", "install"], 0, "", "unexpected diagnostic"),
    )

    assert records == [("install stderr: unexpected diagnostic", "warning")]
