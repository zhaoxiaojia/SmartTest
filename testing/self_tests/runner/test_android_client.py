from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

import android_client
from testing.runner import android_client as runner_android_client
from testing.runtime.events import reset_current_case_nodeid, set_current_case_nodeid


@pytest.fixture(autouse=True)
def disable_android_auto_build(monkeypatch) -> None:
    monkeypatch.setattr(android_client, "_ensure_debug_apk_built", lambda apk_path: None)


def test_install_test_apk_rejects_missing_apk(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)

    with pytest.raises(RuntimeError) as exc:
        android_client.install_test_apk(apk_path=tmp_path / "missing.apk")

    assert "test APK was not found" in str(exc.value)


def test_root_android_client_omits_unsafe_serial_from_adb_commands() -> None:
    assert android_client._adb_base_cmd(
        adb_executable="adb",
        adb_serial="0099360090052090260214801F41D0F脗",
    ) == ["adb"]


def test_root_android_client_keeps_safe_serial_in_adb_commands() -> None:
    assert android_client._adb_base_cmd(adb_executable="adb", adb_serial="ABC123") == ["adb", "-s", "ABC123"]


def test_android_client_installed_returns_true_for_pm_path(monkeypatch) -> None:
    monkeypatch.setattr(runner_android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123", "XYZ789"])

    def fake_run(cmd, capture_output, text, check, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 0, stdout="package:/data/app/com.smarttest.mobile/base.apk\n", stderr="")

    monkeypatch.setattr(runner_android_client.subprocess, "run", fake_run)

    assert runner_android_client.android_client_installed(adb_serial="ABC123") is True


def test_ensure_test_apk_installed_skips_when_already_installed(monkeypatch) -> None:
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/data/app/com.smarttest.mobile/base.apk")
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-1")
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "user:hash-1"})
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    called: list[str] = []
    monkeypatch.setattr(android_client, "install_test_apk", lambda apk_path=None, adb_serial=None: called.append("install"))
    monkeypatch.setattr(Path, "exists", lambda self: True)

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123")

    assert installed is False
    assert called == []


def test_trigger_android_client_case_runs_install_guard(monkeypatch) -> None:
    monkeypatch.setattr(runner_android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123"])
    ensure_calls: list[str] = []
    probe_calls: list[str] = []
    wait_calls: list[tuple[str, str, str]] = []
    force_stop_calls: list[str] = []

    monkeypatch.setattr(
        runner_android_client,
        "ensure_test_apk_installed",
        lambda adb_serial=None, require_privileged=False: ensure_calls.append(
            f"{adb_serial or '<default>'}|priv={require_privileged}"
        ) or False,
    )
    monkeypatch.setattr(
        runner_android_client,
        "android_client_installed",
        lambda adb_serial=None: probe_calls.append(adb_serial or "<default>") or True,
    )
    monkeypatch.setattr(
        runner_android_client,
        "wait_for_android_client_case_completion",
        lambda *, adb_executable, case_id, request_id, trigger, adb_serial=None, poll_interval_sec=1.0, timeout_sec=3600.0, baseline_signature=None, baseline_log_count=0, component=runner_android_client.DEFAULT_COMPONENT, source="pytest", params=None, stage_tracker=None: wait_calls.append(
            (adb_executable, case_id, adb_serial or "<default>")
        ) or {"phase": "Completed", "report": {"statusText": "ok", "totalCount": 1, "successCount": 1, "failedCount": 0}},
    )
    monkeypatch.setattr(
        runner_android_client,
        "_force_stop_android_client",
        lambda *, adb_executable, adb_serial=None, package_name=runner_android_client.PACKAGE_NAME: force_stop_calls.append(
            adb_serial or "<default>"
        ) or subprocess.CompletedProcess(["adb"], 0, stdout="", stderr=""),
    )

    def fake_run(cmd, capture_output, text, check, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 0, stdout="Starting: Intent { ... }\n", stderr="")

    monkeypatch.setattr(runner_android_client.subprocess, "run", fake_run)

    result = runner_android_client.trigger_android_client_case(
        case_id="emmc_rw",
        trigger="testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client",
        adb_serial="ABC123",
    )

    assert result.returncode == 0
    assert ensure_calls == ["ABC123|priv=False"]
    assert probe_calls == ["ABC123"]
    assert force_stop_calls == ["ABC123"]
    assert wait_calls == [("adb", "emmc_rw", "ABC123")]


def test_trigger_android_client_case_uses_default_adb_for_unsafe_serial(monkeypatch) -> None:
    monkeypatch.setattr(runner_android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    unsafe_serial = "0099360090052090260214801F41D0F脗"
    ensure_calls: list[str] = []
    probe_calls: list[str] = []
    force_stop_calls: list[str] = []
    wait_calls: list[str] = []
    start_commands: list[list[str]] = []

    monkeypatch.setattr(
        runner_android_client,
        "ensure_test_apk_installed",
        lambda adb_serial=None, require_privileged=False: ensure_calls.append(adb_serial or "<default>") or False,
    )
    monkeypatch.setattr(
        runner_android_client,
        "android_client_installed",
        lambda adb_serial=None: probe_calls.append(adb_serial or "<default>") or True,
    )
    monkeypatch.setattr(
        runner_android_client,
        "_force_stop_android_client",
        lambda *, adb_executable, adb_serial=None, package_name=runner_android_client.PACKAGE_NAME: force_stop_calls.append(
            adb_serial or "<default>"
        ) or subprocess.CompletedProcess(["adb"], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        runner_android_client,
        "read_android_client_snapshot",
        lambda *, adb_executable, adb_serial=None, package_name=runner_android_client.PACKAGE_NAME: (_ for _ in ()).throw(
            RuntimeError("no snapshot")
        ),
    )
    monkeypatch.setattr(
        runner_android_client,
        "wait_for_android_client_case_completion",
        lambda *, adb_executable, case_id, request_id, trigger, adb_serial=None, poll_interval_sec=1.0, timeout_sec=3600.0, baseline_signature=None, baseline_log_count=0, component=runner_android_client.DEFAULT_COMPONENT, source="pytest", params=None, stage_tracker=None: wait_calls.append(
            adb_serial or "<default>"
        ) or {"phase": "Completed", "report": {"statusText": "ok", "totalCount": 1, "successCount": 1, "failedCount": 0}},
    )

    def fake_run(cmd, capture_output, text, check, **kwargs):  # noqa: ANN001
        start_commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="Starting: Intent { ... }\n", stderr="")

    monkeypatch.setattr(runner_android_client.subprocess, "run", fake_run)

    result = runner_android_client.trigger_android_client_case(
        case_id="emmc_rw",
        trigger="testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client",
        adb_serial=unsafe_serial,
    )

    assert result.returncode == 0
    assert ensure_calls == [unsafe_serial]
    assert probe_calls == [unsafe_serial]
    assert force_stop_calls == [unsafe_serial]
    assert wait_calls == [unsafe_serial]
    assert start_commands
    assert "-s" not in start_commands[0]


def test_trigger_android_client_case_rejects_when_install_still_missing(monkeypatch) -> None:
    monkeypatch.setattr(runner_android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(
        runner_android_client,
        "ensure_test_apk_installed",
        lambda adb_serial=None, require_privileged=False: False,
    )
    monkeypatch.setattr(runner_android_client, "android_client_installed", lambda adb_serial=None: False)

    with pytest.raises(RuntimeError) as exc:
        runner_android_client.trigger_android_client_case(
            case_id="emmc_rw",
            trigger="testing/tests/android/common/system/test_emmc_rw.py::test_emmc_rw_via_android_client",
            adb_serial="ABC123",
        )

    assert "still not installed" in str(exc.value)


def test_ensure_test_apk_installed_reinstalls_when_user_apk_hash_changes(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/data/app/com.smarttest.mobile/base.apk")
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-new")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "user:hash-old"})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)

    calls: list[str] = []
    monkeypatch.setattr(android_client, "install_test_apk", lambda apk_path=None, adb_serial=None: calls.append("install"))

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123")

    assert installed is True
    assert calls == ["install"]
    assert saved == {"ABC123|com.smarttest.mobile|C:\\fake.apk": "user:hash-new"}


def test_ensure_test_apk_installed_privileged_case_reprovisions_stale_privapp(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-root")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-old"})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk")
    monkeypatch.setattr(android_client, "_device_file_hash", lambda **kwargs: "hash-old")
    monkeypatch.setattr(android_client, "_detect_adb_root_mode", lambda **kwargs: True)
    calls: list[str] = []
    monkeypatch.setattr(
        android_client,
        "_install_privileged_test_apk",
        lambda *, adb_executable, apk_path, adb_serial=None, package_name=android_client.PACKAGE_NAME: calls.append("provision"),
    )

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=True)

    assert installed is True
    assert calls == ["provision"]
    assert saved == {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-root"}


def test_ensure_test_apk_installed_privileged_case_skips_when_device_hash_matches_without_record(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-root")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk")
    monkeypatch.setattr(android_client, "_device_file_hash", lambda **kwargs: "hash-root")
    calls: list[str] = []
    monkeypatch.setattr(
        android_client,
        "_install_privileged_test_apk",
        lambda *, adb_executable, apk_path, adb_serial=None, package_name=android_client.PACKAGE_NAME: calls.append("provision"),
    )

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=True)

    assert installed is False
    assert calls == []
    assert saved == {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-root"}


def test_ensure_test_apk_installed_privileged_case_repairs_stale_record_when_device_hash_matches(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-root")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-old"})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk")
    monkeypatch.setattr(android_client, "_device_file_hash", lambda **kwargs: "hash-root")
    calls: list[str] = []
    monkeypatch.setattr(
        android_client,
        "_install_privileged_test_apk",
        lambda *, adb_executable, apk_path, adb_serial=None, package_name=android_client.PACKAGE_NAME: calls.append("provision"),
    )

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=True)

    assert installed is False
    assert calls == []
    assert saved == {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-root"}


def test_detect_adb_root_mode_accepts_empty_adb_root_output(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_adb(*, adb_executable: str, adb_serial: str | None = None, args: list[str]):  # noqa: ANN001
        calls.append(list(args))
        if args == ["root"]:
            return subprocess.CompletedProcess(["adb", *args], 0, stdout="", stderr="")
        if args == ["shell", "getprop", "sys.boot_completed"]:
            return subprocess.CompletedProcess(["adb", *args], 0, stdout="1\n", stderr="")
        if args == ["shell", "id"]:
            return subprocess.CompletedProcess(["adb", *args], 0, stdout="uid=0(root)\n", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(android_client, "_run_adb", fake_run_adb)

    assert android_client._detect_adb_root_mode(adb_executable="adb", adb_serial="ABC123") is True
    assert calls == [["root"], ["shell", "getprop", "sys.boot_completed"], ["shell", "id"]]


def test_ensure_test_apk_installed_user_case_does_not_attempt_privapp(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "")
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-user")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {})
    install_probe_results = iter([False, True])
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: next(install_probe_results))
    detect_calls: list[str] = []
    monkeypatch.setattr(android_client, "_detect_adb_root_mode", lambda **kwargs: detect_calls.append("root") or True)
    install_calls: list[str] = []
    monkeypatch.setattr(android_client, "install_test_apk", lambda apk_path=None, adb_serial=None: install_calls.append("install"))
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=False)

    assert installed is True
    assert detect_calls == []
    assert install_calls == ["install"]


def test_ensure_test_apk_installed_user_case_reuses_existing_privapp(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk")
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-user")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-user"})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "sign_privileged_apk", lambda input_apk_path=None: Path("C:/fake.apk"))
    monkeypatch.setattr(android_client, "_device_file_hash", lambda **kwargs: "hash-user")
    install_calls: list[str] = []
    monkeypatch.setattr(android_client, "install_test_apk", lambda apk_path=None, adb_serial=None: install_calls.append("install"))

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=False)

    assert installed is False
    assert install_calls == []
    assert saved == {}


def test_ensure_test_apk_installed_user_case_reprovisions_stale_privapp(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk")
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-new")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-old"})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "sign_privileged_apk", lambda input_apk_path=None: Path("C:/fake.apk"))
    monkeypatch.setattr(android_client, "_device_file_hash", lambda **kwargs: "hash-old")
    calls: list[str] = []
    monkeypatch.setattr(
        android_client,
        "_install_privileged_test_apk",
        lambda *, adb_executable, apk_path, adb_serial=None, package_name=android_client.PACKAGE_NAME: calls.append("provision"),
    )
    install_calls: list[Path] = []
    monkeypatch.setattr(android_client, "install_test_apk", lambda apk_path=None, adb_serial=None: install_calls.append(Path(apk_path)))

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=False)

    assert installed is True
    assert calls == ["provision"]
    assert install_calls == []
    assert saved == {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-new"}


def test_ensure_test_apk_installed_user_case_repairs_privapp_record_when_device_hash_matches(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk")
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-new")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-old"})
    saved: dict[str, str] = {}
    monkeypatch.setattr(android_client, "_save_install_state", lambda payload: saved.update(payload))
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "sign_privileged_apk", lambda input_apk_path=None: Path("C:/fake.apk"))
    monkeypatch.setattr(android_client, "_device_file_hash", lambda **kwargs: "hash-new")

    installed = android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=False)

    assert installed is False
    assert saved == {"ABC123|com.smarttest.mobile|C:\\fake.apk": "privapp:hash-new"}


def test_ensure_test_apk_installed_privileged_case_requires_adb_root_for_stale_user_install(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(android_client, "_apk_hash", lambda apk_path: "hash-root")
    monkeypatch.setattr(
        android_client,
        "_install_state_key",
        lambda adb_serial=None, apk_path=None, package_name=android_client.PACKAGE_NAME: "ABC123|com.smarttest.mobile|C:\\fake.apk",
    )
    monkeypatch.setattr(android_client, "_load_install_state", lambda: {})
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(android_client, "_package_code_path", lambda **kwargs: "/data/app/com.smarttest.mobile/base.apk")
    monkeypatch.setattr(android_client, "_detect_adb_root_mode", lambda **kwargs: False)
    monkeypatch.setattr(android_client, "_ensure_device_ready_before_install", lambda **kwargs: None)

    with pytest.raises(RuntimeError) as exc:
        android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=True)

    assert "adb root" in str(exc.value)


def test_ensure_test_apk_installed_reports_device_not_ready_before_provision(monkeypatch) -> None:
    monkeypatch.setattr(android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr(
        android_client,
        "_ensure_device_ready_before_install",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no devices/emulators found")),
    )

    with pytest.raises(RuntimeError) as exc:
        android_client.ensure_test_apk_installed(adb_serial="ABC123", require_privileged=True)

    assert "no devices/emulators found" in str(exc.value)


def test_trigger_android_client_case_marks_power_case_as_privileged(monkeypatch) -> None:
    monkeypatch.setattr(runner_android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123"])
    ensure_calls: list[str] = []
    stop_calls: list[str] = []
    launch_calls: list[str] = []
    monkeypatch.setattr(
        runner_android_client,
        "ensure_test_apk_installed",
        lambda adb_serial=None, require_privileged=False: ensure_calls.append(
            f"{adb_serial or '<default>'}|priv={require_privileged}"
        ) or False,
    )
    monkeypatch.setattr(runner_android_client, "android_client_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(
        runner_android_client,
        "stop_android_client_run",
        lambda adb_serial=None, reason="host stop": stop_calls.append(reason) or subprocess.CompletedProcess(["adb"], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        runner_android_client,
        "_launch_android_client_main",
        lambda *, adb_executable, adb_serial=None, package_name=runner_android_client.PACKAGE_NAME: launch_calls.append(
            adb_serial or "<default>"
        ) or subprocess.CompletedProcess(["adb"], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        runner_android_client,
        "_force_stop_android_client",
        lambda **kwargs: subprocess.CompletedProcess(["adb"], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        runner_android_client,
        "read_android_client_snapshot",
        lambda **kwargs: {"phase": "Idle", "logLines": [], "activeRequest": {}, "report": {}},
    )
    monkeypatch.setattr(
        runner_android_client,
        "wait_for_android_client_case_completion",
        lambda **kwargs: {"phase": "Completed", "report": {"statusText": "ok", "totalCount": 1, "successCount": 1, "failedCount": 0}},
    )
    monkeypatch.setattr(
        runner_android_client.subprocess,
        "run",
        lambda cmd, capture_output, text, check, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="Starting: Intent { ... }\n", stderr=""),
    )

    runner_android_client.trigger_android_client_case(
        case_id="auto_reboot",
        trigger="testing/tests/android/common/system/test_auto_reboot.py::test_auto_reboot_via_android_client",
        adb_serial="ABC123",
    )

    assert ensure_calls == ["ABC123|priv=True"]
    assert stop_calls == ["prepare privileged provisioning for auto_reboot"]
    assert launch_calls == ["ABC123"]


def test_trigger_android_client_case_skips_wait_in_no_poll_mode(monkeypatch) -> None:
    monkeypatch.setenv("SMARTTEST_ANDROID_NO_POLL_CASES", "auto_suspend")
    monkeypatch.setattr(runner_android_client.shutil, "which", lambda name: "adb" if name == "adb" else None)
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123"])
    monkeypatch.setattr(
        runner_android_client,
        "ensure_test_apk_installed",
        lambda adb_serial=None, require_privileged=False: False,
    )
    monkeypatch.setattr(runner_android_client, "android_client_installed", lambda adb_serial=None: True)
    monkeypatch.setattr(
        runner_android_client,
        "_force_stop_android_client",
        lambda **kwargs: subprocess.CompletedProcess(["adb"], 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        runner_android_client,
        "read_android_client_snapshot",
        lambda **kwargs: {"phase": "Idle", "logLines": [], "activeRequest": {}, "report": {}},
    )
    wait_called = {"value": False}

    def fail_wait(**kwargs):  # noqa: ANN001
        wait_called["value"] = True
        raise AssertionError("wait_for_android_client_case_completion should not be called")

    monkeypatch.setattr(runner_android_client, "wait_for_android_client_case_completion", fail_wait)
    monkeypatch.setattr(
        runner_android_client.subprocess,
        "run",
        lambda cmd, capture_output, text, check, **kwargs: subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Starting: Intent { ... }\n",
            stderr="",
        ),
    )

    result = runner_android_client.trigger_android_client_case(
        case_id="auto_suspend",
        trigger="testing/tests/android/common/system/test_auto_suspend.py::test_auto_suspend_via_android_client",
        adb_serial="ABC123",
    )

    assert result.returncode == 0
    assert wait_called["value"] is False


def test_extract_json_payload_accepts_raw_content_output() -> None:
    raw = "Random header\n{\"phase\":\"Completed\",\"logLines\":[]}\n"

    payload = runner_android_client._extract_json_payload(raw)

    assert payload == "{\"phase\":\"Completed\",\"logLines\":[]}"


def test_read_android_client_snapshot_parses_content_read_output(monkeypatch) -> None:
    monkeypatch.setattr("testing.params.adb_devices.list_adb_devices", lambda: ["ABC123"])
    monkeypatch.setattr(runner_android_client.subprocess, "run", lambda cmd, capture_output, text, check, encoding=None, errors=None, creationflags=0: subprocess.CompletedProcess(
        cmd,
        0,
        stdout="{\"phase\":\"Running\",\"logLines\":[\"a\",\"b\"]}",
        stderr="",
    ))

    snapshot = runner_android_client.read_android_client_snapshot(adb_executable="adb", adb_serial="ABC123")

    assert snapshot["phase"] == "Running"
    assert snapshot["logLines"] == ["a", "b"]


def test_dut_unavailable_wait_state_enters_and_exits_for_reboot_stage() -> None:
    waiting = runner_android_client._next_dut_unavailable_wait_state(
        phase="Running",
        current_stage="rebooting dut",
        matches_request=True,
        waiting_for_device_resume=False,
    )
    assert waiting is True

    waiting = runner_android_client._next_dut_unavailable_wait_state(
        phase="Running",
        current_stage="waiting after reboot",
        matches_request=True,
        waiting_for_device_resume=True,
    )
    assert waiting is True

    waiting = runner_android_client._next_dut_unavailable_wait_state(
        phase="Failed",
        current_stage="rebooting dut",
        matches_request=True,
        waiting_for_device_resume=True,
    )
    assert waiting is False


def test_dut_unavailable_wait_state_enters_and_exits_for_suspend_stage() -> None:
    waiting = runner_android_client._next_dut_unavailable_wait_state(
        phase="Running",
        current_stage="entering deep suspend",
        matches_request=True,
        waiting_for_device_resume=False,
    )
    assert waiting is True

    waiting = runner_android_client._next_dut_unavailable_wait_state(
        phase="Running",
        current_stage="resumed from deep suspend",
        matches_request=True,
        waiting_for_device_resume=True,
    )
    assert waiting is True


def test_snapshot_read_failure_key_collapses_repeated_adb_disconnects() -> None:
    error = (
        "content snapshot read failed.\n"
        "stdout:\n\n"
        "stderr:\nerror: no devices/emulators found\n"
        "returncode=1"
    )

    assert runner_android_client._snapshot_read_failure_key(error) == "no devices/emulators found"


def test_android_client_stage_tracker_emits_generic_step_updates(tmp_path: Path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    token = set_current_case_nodeid("testing/tests/example.py::test_external_case")
    try:
        tracker = runner_android_client._AndroidClientStageTracker(
            case_id="external_case",
            request_id="request-1",
            params={"external_case:target": "192.168.1.1"},
        )
        tracker.observe_snapshot(
            {
                "phase": "Running",
                "currentStage": "prepare target",
                "activeRequest": {"requestId": "request-1"},
            }
        )
        tracker.observe_snapshot(
            {
                "phase": "Running",
                "currentStage": "verify target",
                "activeRequest": {"requestId": "request-1"},
            }
        )
        tracker.finish("failed", error="target unreachable", actual="ping failed")
    finally:
        reset_current_case_nodeid(token)

    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    stage_events = [
        event
        for event in events
        if event.get("definition_id") == "android_client.stage" or event.get("type") == "step_finished"
    ]
    assert any(event.get("title") == "prepare target" for event in stage_events)
    assert any(event.get("title") == "verify target" for event in stage_events)
    assert events[-2]["status"] == "failed"
    assert events[-2]["error"] == "target unreachable"
    assert events[-1]["status"] == "failed"


def test_android_client_stage_tracker_plans_all_steps_before_status_updates(tmp_path: Path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    token = set_current_case_nodeid("testing/tests/example.py::test_external_case")
    try:
        tracker = runner_android_client._AndroidClientStageTracker(
            case_id="external_case",
            request_id="request-2",
            params={},
        )
        tracker.observe_snapshot(
            {
                "phase": "Running",
                "currentStage": "prepare target",
                "plannedSteps": [
                    {"id": "prepare", "title": "Prepare target", "kind": "setup", "definitionId": "case.prepare"},
                    {"id": "verify", "title": "Verify target", "kind": "check", "definitionId": "case.verify"},
                ],
                "stepStates": [
                    {"id": "prepare", "status": "running"},
                    {"id": "verify", "status": "planned"},
                ],
            }
        )
        tracker.observe_snapshot(
            {
                "phase": "Running",
                "currentStage": "verify target",
                "plannedSteps": [
                    {"id": "prepare", "title": "Prepare target", "kind": "setup", "definitionId": "case.prepare"},
                    {"id": "verify", "title": "Verify target", "kind": "check", "definitionId": "case.verify"},
                ],
                "stepStates": [
                    {"id": "prepare", "status": "passed"},
                    {"id": "verify", "status": "running"},
                ],
            }
        )
    finally:
        reset_current_case_nodeid(token)

    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    planned_titles = [event.get("title") for event in events if event["type"] == "step_planned"]
    started_titles = [event.get("title") for event in events if event["type"] == "step_started"]

    assert "Prepare target" in planned_titles
    assert "Verify target" in planned_titles
    verify_planned_index = next(
        index for index, event in enumerate(events)
        if event["type"] == "step_planned" and event.get("title") == "Verify target"
    )
    prepare_started_index = next(
        index for index, event in enumerate(events)
        if event["type"] == "step_started" and event.get("title") == "Prepare target"
    )
    assert verify_planned_index < prepare_started_index
    assert any(event["type"] == "step_finished" and event["status"] == "passed" for event in events)


def test_android_client_stage_tracker_emits_dynamic_cycle_step_states(tmp_path: Path, monkeypatch) -> None:
    event_file = tmp_path / "events.jsonl"
    monkeypatch.setenv("SMARTTEST_STEP_EVENTS_OUT", str(event_file))

    token = set_current_case_nodeid("testing/tests/example.py::test_external_case")
    try:
        tracker = runner_android_client._AndroidClientStageTracker(
            case_id="radio_case",
            request_id="request-3",
            params={},
        )
        tracker.observe_snapshot(
            {
                "phase": "Running",
                "currentLoop": 3,
                "totalLoops": 5,
                "currentStage": "cycle 3/5 disable radio",
                "currentStepId": "radio_case.cycle.3.disable",
                "plannedSteps": [
                    {"id": "radio_case.execute", "title": "Execute radio_case", "kind": "action", "definitionId": "radio_case.execute"},
                ],
                "stepStates": [
                    {"id": "radio_case.execute", "status": "passed"},
                    {"id": "radio_case.cycle.3.disable", "status": "running"},
                ],
            }
        )
        tracker.observe_snapshot(
            {
                "phase": "Running",
                "currentLoop": 3,
                "totalLoops": 5,
                "currentStage": "cycle 3/5 disable radio",
                "currentStepId": "radio_case.cycle.3.disable",
                "plannedSteps": [
                    {"id": "radio_case.execute", "title": "Execute radio_case", "kind": "action", "definitionId": "radio_case.execute"},
                ],
                "stepStates": [
                    {"id": "radio_case.execute", "status": "passed"},
                    {"id": "radio_case.cycle.3.disable", "status": "passed", "actual": "off"},
                ],
            }
        )
    finally:
        reset_current_case_nodeid(token)

    events = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    dynamic_events = [event for event in events if event.get("step_id") == "request-3:radio_case.cycle.3.disable"]

    assert [event["type"] for event in dynamic_events] == ["step_planned", "step_started", "step_finished"]
    assert dynamic_events[0]["definition_id"] == "radio_case.cycle.disable"
    assert dynamic_events[0]["title"] == "Cycle 3/5: disable"
    assert dynamic_events[-1]["status"] == "passed"
    assert dynamic_events[-1]["actual"] == "off"
