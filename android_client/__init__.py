from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from testing.params.adb_devices import resolve_adb_serial_for_command


PACKAGE_NAME = "com.smarttest.mobile"
DEFAULT_APK_PATH = Path(__file__).resolve().parent / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
INSTALL_STATE_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SmartTest" / "android_client_install_state.json"
DEFAULT_PRIVAPP_DIR = "/system/priv-app/SmartTestMobile"
DEFAULT_PRIVAPP_APK = f"{DEFAULT_PRIVAPP_DIR}/SmartTestMobile.apk"
DEFAULT_PRIVAPP_PERMISSIONS = "/system/etc/permissions/privapp-permissions-com.smarttest.mobile.xml"
LOCAL_PRIVAPP_PERMISSIONS = Path(__file__).resolve().parent / "system_app" / "privapp-permissions-com.smarttest.mobile.xml"
DEFAULT_ADB_WAIT_TIMEOUT_SEC = 180.0
PRIVILEGED_CASE_IDS = frozenset({"auto_reboot", "auto_suspend"})
PRIVILEGED_PARTITIONS = ("/system", "/product", "/system_ext")


def _adb_base_cmd(*, adb_executable: str, adb_serial: str | None = None) -> list[str]:
    cmd = [adb_executable]
    serial = resolve_adb_serial_for_command(adb_serial)
    if serial:
        cmd.extend(["-s", serial])
    return cmd


def _apk_hash(apk_path: Path) -> str:
    digest = hashlib.sha256()
    with apk_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_install_state() -> dict[str, str]:
    if not INSTALL_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(INSTALL_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def _save_install_state(payload: dict[str, str]) -> None:
    INSTALL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSTALL_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _install_state_key(*, adb_serial: str | None, apk_path: Path, package_name: str = PACKAGE_NAME) -> str:
    serial = str(adb_serial or "").strip() or "<default>"
    return f"{serial}|{package_name}|{apk_path.resolve()}"


def _install_state_value(*, mode: str, apk_hash: str) -> str:
    return f"{mode}:{apk_hash}"


def _parse_install_state_value(raw: str) -> tuple[str, str]:
    text = str(raw or "")
    if ":" not in text:
        return "", text
    mode, apk_hash = text.split(":", 1)
    return mode, apk_hash


def _run_adb(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def _shell(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    command: str,
) -> subprocess.CompletedProcess[str]:
    return _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", command],
    )


def _detect_adb_root_mode(*, adb_executable: str, adb_serial: str | None = None) -> bool:
    root_result = _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["root"],
    )
    root_stdout = str(root_result.stdout or "").strip().lower()
    root_stderr = str(root_result.stderr or "").strip().lower()
    print(f"[android_client] root probe mode=adb_root stdout: {root_stdout}")
    print(f"[android_client] root probe mode=adb_root stderr: {root_stderr}")
    if root_result.returncode == 0:
        _wait_for_device_ready(adb_executable=adb_executable, adb_serial=adb_serial)
        verify = _shell(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            command="id",
        )
        print(f"[android_client] root verify stdout: {str(verify.stdout or '').strip().lower()}")
        print(f"[android_client] root verify stderr: {str(verify.stderr or '').strip().lower()}")
        if verify.returncode == 0 and "uid=0" in str(verify.stdout or "").strip().lower():
            return True
    return False


def _package_code_path(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> str:
    result = _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "pm", "path", package_name],
    )
    stdout = str(result.stdout or "").strip()
    if result.returncode != 0 or "package:" not in stdout:
        return ""
    return stdout.split("package:", 1)[-1].strip()


def _is_privileged_code_path(code_path: str) -> bool:
    normalized = str(code_path or "").strip()
    return normalized.startswith("/system/priv-app/") or normalized.startswith("/system/app/")


def _wait_for_device_ready(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    timeout_sec: float = DEFAULT_ADB_WAIT_TIMEOUT_SEC,
) -> None:
    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.append("wait-for-device")
    subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_sec,
    )
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = _run_adb(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            args=["shell", "getprop", "sys.boot_completed"],
        )
        if str(result.stdout or "").strip() == "1":
            return
        time.sleep(2.0)
    raise RuntimeError("Timed out while waiting for DUT to finish booting after priv-app install.")


def _ensure_device_ready_before_install(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    timeout_sec: float = 60.0,
) -> None:
    try:
        _wait_for_device_ready(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            timeout_sec=timeout_sec,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "android_client cannot start because no ready DUT is visible to adb.\n"
            "Run 'adb devices' and confirm the target shows as 'device', then retry.\n"
            f"details: {exc}"
        ) from exc


def _run_checked_adb(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    args: list[str],
    label: str,
) -> subprocess.CompletedProcess[str]:
    result = _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=args,
    )
    print(f"[android_client] {label} stdout: {result.stdout.strip()}")
    print(f"[android_client] {label} stderr: {result.stderr.strip()}")
    if result.returncode != 0:
        raise RuntimeError(
            f"android_client provisioning failed during {label}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _partition_targets(partition_root: str) -> tuple[str, str]:
    normalized = partition_root.rstrip("/")
    priv_dir = f"{normalized}/priv-app/SmartTestMobile"
    apk_path = f"{priv_dir}/SmartTestMobile.apk"
    xml_path = f"{normalized}/etc/permissions/privapp-permissions-com.smarttest.mobile.xml"
    return apk_path, xml_path


def _provision_to_partition(
    *,
    adb_executable: str,
    adb_serial: str | None,
    apk_path: Path,
    partition_root: str,
    package_name: str = PACKAGE_NAME,
) -> bool:
    remote_apk_tmp = "/data/local/tmp/SmartTestMobile.apk"
    remote_xml_tmp = "/data/local/tmp/privapp-permissions-com.smarttest.mobile.xml"
    target_apk, target_xml = _partition_targets(partition_root)
    target_dir = target_apk.rsplit("/", 1)[0]

    for local_path, remote_path in ((apk_path, remote_apk_tmp), (LOCAL_PRIVAPP_PERMISSIONS, remote_xml_tmp)):
        result = _run_adb(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            args=["push", str(local_path), remote_path],
        )
        print(f"[android_client] push {local_path.name} stdout: {result.stdout.strip()}")
        print(f"[android_client] push {local_path.name} stderr: {result.stderr.strip()}")
        if result.returncode != 0:
            raise RuntimeError(
                "Failed to push android_client provisioning artifact.\n"
                f"local={local_path}\nremote={remote_path}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

    commands = [
        f"mkdir -p '{target_dir}'",
        f"cp '{remote_apk_tmp}' '{target_apk}'",
        f"cp '{remote_xml_tmp}' '{target_xml}'",
        f"chown root:root '{target_apk}' '{target_xml}'",
        f"chmod 0644 '{target_apk}' '{target_xml}'",
        f"restorecon '{target_apk}' '{target_xml}' || true",
        f"pm uninstall '{package_name}' || true",
    ]
    for command in commands:
        result = _shell(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            command=command,
        )
        print(f"[android_client] provision command: {command}")
        print(f"[android_client] provision stdout: {result.stdout.strip()}")
        print(f"[android_client] provision stderr: {result.stderr.strip()}")
        if result.returncode != 0 and "|| true" not in command:
            error_text = str(result.stderr or result.stdout or "").lower()
            if "read-only file system" in error_text or "not in /proc/mounts" in error_text:
                return False
            raise RuntimeError(
                "Failed to provision android_client as privileged app.\n"
                f"command={command}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
    return True


def _install_privileged_test_apk(
    *,
    adb_executable: str,
    apk_path: Path,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> None:
    if not LOCAL_PRIVAPP_PERMISSIONS.exists():
        raise RuntimeError(f"privapp permissions file is missing: {LOCAL_PRIVAPP_PERMISSIONS}")
    if not _detect_adb_root_mode(adb_executable=adb_executable, adb_serial=adb_serial):
        raise RuntimeError(
            "android_client privileged provisioning requires a build that supports 'adb root'."
        )
    _run_checked_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["remount"],
        label="adb remount",
    )

    provisioned_partition = ""
    for partition_root in PRIVILEGED_PARTITIONS:
        print(f"[android_client] try privileged partition: {partition_root}")
        if _provision_to_partition(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            apk_path=apk_path,
            partition_root=partition_root,
            package_name=package_name,
        ):
            provisioned_partition = partition_root
            break

    if not provisioned_partition:
        raise RuntimeError(
            "android_client privileged provisioning failed on all official system partitions.\n"
            f"tried={', '.join(PRIVILEGED_PARTITIONS)}\n"
            "This DUT doesn't currently expose a writable remounted system partition for privileged app deployment."
        )

    reboot_result = _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["reboot"],
    )
    print(f"[android_client] priv-app reboot stdout: {reboot_result.stdout.strip()}")
    print(f"[android_client] priv-app reboot stderr: {reboot_result.stderr.strip()}")
    if reboot_result.returncode != 0:
        raise RuntimeError(
            "Failed to reboot DUT after priv-app install.\n"
            f"stdout:\n{reboot_result.stdout}\nstderr:\n{reboot_result.stderr}"
        )
    _wait_for_device_ready(adb_executable=adb_executable, adb_serial=adb_serial)


def _ensure_privileged_install(
    *,
    adb_executable: str,
    resolved_apk_path: Path,
    adb_serial: str | None,
    current_hash: str,
    state_key: str,
    install_state: dict[str, str],
    installed: bool,
    code_path: str,
    recorded_mode: str,
    recorded_hash: str,
) -> bool:
    privileged = _is_privileged_code_path(code_path)
    if installed and privileged and recorded_mode == "privapp" and recorded_hash == current_hash:
        print("[android_client] priv-app already installed with matching hash, skip install")
        return False

    print("[android_client] privileged provisioning required; start official adb root/remount flow")
    _install_privileged_test_apk(
        adb_executable=adb_executable,
        apk_path=resolved_apk_path,
        adb_serial=adb_serial,
    )
    if not is_test_apk_installed(adb_serial=adb_serial):
        raise RuntimeError("android_client priv-app install completed but package is still missing on DUT.")
    verified_code_path = _package_code_path(adb_executable=adb_executable, adb_serial=adb_serial)
    if not _is_privileged_code_path(verified_code_path):
        raise RuntimeError(
            "android_client priv-app install completed but package is not loaded from /system.\n"
            f"code_path={verified_code_path or '<missing>'}"
        )
    install_state[state_key] = _install_state_value(mode="privapp", apk_hash=current_hash)
    _save_install_state(install_state)
    print("[android_client] priv-app install finished")
    return True


def is_test_apk_installed(*, adb_serial: str | None = None, package_name: str = PACKAGE_NAME) -> bool:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", "pm", "path", package_name])
    print(f"[android_client] probe install status: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"[android_client] probe stdout: {result.stdout.strip()}")
    print(f"[android_client] probe stderr: {result.stderr.strip()}")
    return result.returncode == 0 and "package:" in str(result.stdout or "")


def install_test_apk(*, apk_path: str | Path | None = None, adb_serial: str | None = None) -> subprocess.CompletedProcess[str]:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        print("[android_client] adb is not available in PATH during install")
        raise RuntimeError("adb is not available in PATH.")

    resolved_apk_path = Path(apk_path or DEFAULT_APK_PATH).resolve()
    if not resolved_apk_path.exists():
        print(f"[android_client] test APK not found: {resolved_apk_path}")
        raise RuntimeError(f"android_client test APK was not found: {resolved_apk_path}")

    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["install", "-r", "-g", "-t", str(resolved_apk_path)])
    print(f"[android_client] install APK: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"[android_client] install stdout: {result.stdout.strip()}")
    print(f"[android_client] install stderr: {result.stderr.strip()}")
    combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0 or "Failure" in combined_output:
        raise RuntimeError(
            "Failed to install android_client test APK.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def ensure_test_apk_installed(
    *,
    apk_path: str | Path | None = None,
    adb_serial: str | None = None,
    require_privileged: bool = False,
) -> bool:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")
    _ensure_device_ready_before_install(adb_executable=adb_executable, adb_serial=adb_serial)

    resolved_apk_path = Path(apk_path or DEFAULT_APK_PATH).resolve()
    if not resolved_apk_path.exists():
        print(f"[android_client] ensure install failed, APK missing: {resolved_apk_path}")
        raise RuntimeError(f"android_client test APK was not found: {resolved_apk_path}")

    current_hash = _apk_hash(resolved_apk_path)
    state_key = _install_state_key(adb_serial=adb_serial, apk_path=resolved_apk_path)
    install_state = _load_install_state()
    recorded_mode, recorded_hash = _parse_install_state_value(install_state.get(state_key, ""))
    installed = is_test_apk_installed(adb_serial=adb_serial)
    code_path = _package_code_path(adb_executable=adb_executable, adb_serial=adb_serial) if installed else ""
    privileged = _is_privileged_code_path(code_path)
    print(f"[android_client] current apk hash: {current_hash}")
    print(f"[android_client] current code path: {code_path or '<missing>'}")
    print(f"[android_client] privileged install: {privileged}")
    print(f"[android_client] recorded mode: {recorded_mode or '<none>'}")
    print(f"[android_client] recorded apk hash: {recorded_hash or '<none>'}")
    print(f"[android_client] installed on device: {installed}")

    if require_privileged:
        return _ensure_privileged_install(
            adb_executable=adb_executable,
            resolved_apk_path=resolved_apk_path,
            adb_serial=adb_serial,
            current_hash=current_hash,
            state_key=state_key,
            install_state=install_state,
            installed=installed,
            code_path=code_path,
            recorded_mode=recorded_mode,
            recorded_hash=recorded_hash,
        )

    if installed and not privileged and recorded_mode == "user" and recorded_hash == current_hash:
        print("[android_client] user app already installed with matching hash, skip install")
        return False

    if installed and recorded_hash != current_hash:
        print("[android_client] installed APK hash changed, reinstall required")
    elif not installed:
        print("[android_client] test APK not installed, start install")
    else:
        print("[android_client] install state missing, reinstall to align DUT with current APK")
    install_test_apk(apk_path=resolved_apk_path, adb_serial=adb_serial)
    if not is_test_apk_installed(adb_serial=adb_serial):
        raise RuntimeError("android_client test APK install completed but package is still missing on DUT.")
    install_state[state_key] = _install_state_value(mode="user", apk_hash=current_hash)
    _save_install_state(install_state)
    print("[android_client] test APK install finished")
    return True


__all__ = [
    "DEFAULT_APK_PATH",
    "INSTALL_STATE_PATH",
    "PACKAGE_NAME",
    "PRIVILEGED_CASE_IDS",
    "ensure_test_apk_installed",
    "install_test_apk",
    "is_test_apk_installed",
]
