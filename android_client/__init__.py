from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import sys

from testing.params.adb_devices import resolve_adb_serial_for_command
from tools.logging import smart_log


PACKAGE_NAME = "com.smarttest.mobile"
RAW_DEBUG_APK_RELATIVE_PATH = Path("android_client", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
SIGNED_APK_RELATIVE_PATH = Path(
    "android_client",
    "app",
    "build",
    "outputs",
    "apk",
    "debug",
    "app-debug-platform.apk",
)


def _resource_path(relative_path: Path) -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        packaged_path = Path(packaged_root) / relative_path
        if packaged_path.exists():
            return packaged_path
    return Path(__file__).resolve().parent.parent / relative_path


RAW_DEBUG_APK_PATH = _resource_path(RAW_DEBUG_APK_RELATIVE_PATH)
DEFAULT_APK_PATH = _resource_path(SIGNED_APK_RELATIVE_PATH)
INSTALL_STATE_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SmartTest" / "android_client_install_state.json"
DEFAULT_PRIVAPP_DIR = "/system/priv-app/SmartTestMobile"


DEFAULT_PRIVAPP_APK = f"{DEFAULT_PRIVAPP_DIR}/SmartTestMobile.apk"
DEFAULT_PRIVAPP_PERMISSIONS = "/system/etc/permissions/privapp-permissions-com.smarttest.mobile.xml"
LOCAL_PRIVAPP_PERMISSIONS = Path(__file__).resolve().parent / "system_app" / "privapp-permissions-com.smarttest.mobile.xml"
DEFAULT_SIGNAPK_DIR = Path(__file__).resolve().parent / "signapk" / "mnt" / "fileroot" / "fae.autobuild" / "workdir" / "workspace" / "FAE" / "AutoBuild" / "IPTV" / "daxiong.cao" / "s6" / "u-1"
SIGNAPK_DIR = Path(os.environ.get("SMARTTEST_SIGNAPK_DIR", DEFAULT_SIGNAPK_DIR)).expanduser()
SIGNAPK_JAR = Path(
    os.environ.get("SMARTTEST_SIGNAPK_JAR", SIGNAPK_DIR / "prebuilts" / "sdk" / "tools" / "lib" / "signapk.jar"),
).expanduser()
PLATFORM_CERT_PEM = Path(
    os.environ.get("SMARTTEST_PLATFORM_CERT_PEM", SIGNAPK_DIR / "build" / "target" / "product" / "security" / "platform.x509.pem"),
).expanduser()
PLATFORM_CERT_PK8 = Path(
    os.environ.get("SMARTTEST_PLATFORM_CERT_PK8", SIGNAPK_DIR / "build" / "target" / "product" / "security" / "platform.pk8"),
).expanduser()
DEFAULT_ADB_WAIT_TIMEOUT_SEC = 180.0
PRIVILEGED_CASE_IDS = frozenset({"auto_reboot", "auto_suspend", "wifi_onoff_scan", "bt_onoff_scan"})
PRIVILEGED_PARTITIONS = ("/system", "/product", "/system_ext")


def _subprocess_creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _build_env() -> dict[str, str]:
    build_env = os.environ.copy()
    if build_env.get("JAVA_HOME"):
        return build_env
    homebrew_jdk17 = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
    if homebrew_jdk17.exists():
        build_env["JAVA_HOME"] = str(homebrew_jdk17)
        build_env["PATH"] = f"{homebrew_jdk17 / 'bin'}{os.pathsep}{build_env.get('PATH', '')}"
    return build_env


def _adb_base_cmd(*, adb_executable: str, adb_serial: str | None = None) -> list[str]:
    command = [adb_executable]
    serial = resolve_adb_serial_for_command(adb_serial)
    if serial:
        command.extend(["-s", serial])
    return command


def _serial_for_log(serial: str | None) -> str:
    text = str(serial or "").strip()
    if not text:
        return "<default>"
    return text.encode("unicode_escape").decode("ascii")


def _apk_hash(apk_path: Path) -> str:
    digest = hashlib.sha256()
    with apk_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_debug_apk_built(apk_path: Path) -> None:
    project_dir = Path(__file__).resolve().parent
    gradlew = project_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not gradlew.exists():
        smart_log(f"build check skipped: gradlew missing at {gradlew}", level="warning", domain="android", source="android_client.install")
        return
    source_roots = [
        project_dir / "app" / "src" / "main" / "java",
        project_dir / "app" / "src" / "main" / "res",
    ]
    source_files: list[Path] = []
    for root in source_roots:
        if root.exists():
            source_files.extend(path for path in root.rglob("*") if path.is_file())
    manifest = project_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    if manifest.exists():
        source_files.append(manifest)
    newest_source_mtime = max((path.stat().st_mtime for path in source_files), default=0.0)
    apk_mtime = apk_path.stat().st_mtime if apk_path.exists() else 0.0
    smart_log(
        "build check "
        f"apk={apk_path} exists={apk_path.exists()} apk_mtime={apk_mtime:.3f} "
        f"newest_source_mtime={newest_source_mtime:.3f} source_files={len(source_files)}",
        domain="android", source="android_client.install")
    if apk_path.exists() and apk_path.stat().st_mtime >= newest_source_mtime:
        smart_log("build check result: existing debug APK is up to date", domain="android", source="android_client.install")
        return
    smart_log("local APK is missing or stale; build :app:assembleDebug", domain="android", source="android_client.install")
    gradle_cmd = [str(gradlew)] if os.name == "nt" or os.access(gradlew, os.X_OK) else ["sh", str(gradlew)]
    result = subprocess.run(
        [*gradle_cmd, ":app:assembleDebug"],
        cwd=str(project_dir),
        env=_build_env(),
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    smart_log(f"build stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
    smart_log(f"build stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
    if result.returncode != 0 or not apk_path.exists():
        raise RuntimeError(
            "Failed to build android_client debug APK.\n"
            f"Command: {gradlew} :app:assembleDebug\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _platform_signing_available() -> bool:
    return PLATFORM_CERT_PEM.exists() and PLATFORM_CERT_PK8.exists()


def _find_apksigner() -> str | None:
    direct = shutil.which("apksigner")
    if direct:
        return direct
    sdk_roots: list[Path] = []
    for raw in [os.environ.get("ANDROID_HOME", ""), os.environ.get("ANDROID_SDK_ROOT", "")]:
        text = raw.strip()
        if text:
            sdk_roots.append(Path(text))
    local_properties = Path(__file__).resolve().parent / "local.properties"
    if local_properties.exists():
        for line in local_properties.read_text(encoding="utf-8").splitlines():
            if line.startswith("sdk.dir="):
                sdk_roots.append(Path(line.split("=", 1)[1].strip()))
                break
    sdk_roots.extend(
        [
            Path("/opt/homebrew/share/android-commandlinetools"),
            Path.home() / "Library" / "Android" / "sdk",
        ],
    )
    candidates = sorted(
        [
            path
            for sdk_root in sdk_roots
            for path in ((sdk_root / "build-tools").iterdir() if (sdk_root / "build-tools").exists() else [])
            if path.is_dir()
        ],
        key=lambda item: item.name,
        reverse=True,
    )
    for candidate in candidates:
        apksigner = candidate / ("apksigner.bat" if os.name == "nt" else "apksigner")
        if apksigner.exists():
            return str(apksigner)
    return None


def sign_privileged_apk(
    *,
    input_apk_path: str | Path | None = None,
    output_apk_path: str | Path | None = None,
) -> Path:
    source_apk = Path(input_apk_path or RAW_DEBUG_APK_PATH).resolve()
    target_apk = Path(output_apk_path or DEFAULT_APK_PATH).resolve()

    needs_resign = True
    if target_apk.exists():
        try:
            needs_resign = target_apk.stat().st_mtime < source_apk.stat().st_mtime
        except FileNotFoundError:
            needs_resign = False
        if not needs_resign:
            return target_apk
        if not _platform_signing_available():
            smart_log("use existing platform-signed APK; signing files are unavailable", level="warning", domain="android", source="android_client.install")
            return target_apk

    if not source_apk.exists():
        raise RuntimeError(f"android_client APK was not found for signing: {source_apk}")
    if not _platform_signing_available():
        raise RuntimeError(
            "android_client platform signing files are missing and no pre-signed APK is available.\n"
            f"target={target_apk}\n"
            f"jar={SIGNAPK_JAR}\n"
            f"pem={PLATFORM_CERT_PEM}\n"
            f"pk8={PLATFORM_CERT_PK8}"
        )

    target_apk.parent.mkdir(parents=True, exist_ok=True)
    if target_apk.exists():
        try:
            target_apk.unlink()
        except FileNotFoundError:
            pass

    apksigner = _find_apksigner()
    if apksigner:
        cmd = [
            apksigner,
            "sign",
            "--key",
            str(PLATFORM_CERT_PK8),
            "--cert",
            str(PLATFORM_CERT_PEM),
            "--out",
            str(target_apk),
            str(source_apk),
        ]
        smart_log(f"platform sign command: {' '.join(cmd)}", domain="android", source="android_client.install")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            creationflags=_subprocess_creationflags(),
        )
        smart_log(f"platform sign stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
        smart_log(f"platform sign stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
        if result.returncode == 0 and target_apk.exists():
            return target_apk
        sign_errors = [
            "Failed to platform-sign android_client APK with apksigner.",
            f"command: {' '.join(cmd)}",
            f"stdout:\n{result.stdout}",
            f"stderr:\n{result.stderr}",
        ]
    else:
        sign_errors = ["Failed to platform-sign android_client APK: apksigner was not found."]

    if SIGNAPK_JAR.exists():
        fallback_cmd = [
            "java",
            "-jar",
            str(SIGNAPK_JAR),
            str(PLATFORM_CERT_PEM),
            str(PLATFORM_CERT_PK8),
            str(source_apk),
            str(target_apk),
        ]
        smart_log(f"fallback sign command: {' '.join(fallback_cmd)}", domain="android", source="android_client.install")
        fallback_result = subprocess.run(
            fallback_cmd,
            capture_output=True,
            text=True,
            check=False,
            creationflags=_subprocess_creationflags(),
        )
        smart_log(f"fallback sign stdout: {fallback_result.stdout.strip()}", domain="android", source="android_client.install")
        smart_log(f"fallback sign stderr: {fallback_result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
        if fallback_result.returncode == 0 and target_apk.exists():
            return target_apk
        sign_errors.extend(
            [
                "Fallback signapk.jar signing also failed.",
                f"command: {' '.join(fallback_cmd)}",
                f"stdout:\n{fallback_result.stdout}",
                f"stderr:\n{fallback_result.stderr}",
            ],
        )

    if not target_apk.exists():
        raise RuntimeError("\n".join(sign_errors))
    return target_apk


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
        creationflags=_subprocess_creationflags(),
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
    smart_log(f"root probe mode=adb_root stdout: {root_stdout}", domain="android", source="android_client.install")
    smart_log(f"root probe mode=adb_root stderr: {root_stderr}", level="warning", domain="android", source="android_client.install")
    if root_result.returncode == 0:
        _wait_for_device_ready(adb_executable=adb_executable, adb_serial=adb_serial)
        verify = _shell(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            command="id",
        )
        smart_log(f"root verify stdout: {str(verify.stdout or '').strip().lower()}", domain="android", source="android_client.install")
        smart_log(f"root verify stderr: {str(verify.stderr or '').strip().lower()}", level="warning", domain="android", source="android_client.install")
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


def _package_version_info(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    package_name: str = PACKAGE_NAME,
) -> dict[str, str]:
    result = _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "dumpsys", "package", package_name],
    )
    if result.returncode != 0:
        return {
            "version_code": "",
            "version_name": "",
            "error": str(result.stderr or "").strip(),
        }
    version_code = ""
    version_name = ""
    for raw_line in str(result.stdout or "").splitlines():
        line = raw_line.strip()
        if line.startswith("versionCode="):
            version_code = line.split(maxsplit=1)[0].split("=", 1)[-1].strip()
        elif line.startswith("versionName="):
            version_name = line.split("=", 1)[-1].strip()
    return {
        "version_code": version_code,
        "version_name": version_name,
        "error": "",
    }


def _device_file_hash(
    *,
    adb_executable: str,
    adb_serial: str | None = None,
    path: str,
) -> str:
    result = _run_adb(
        adb_executable=adb_executable,
        adb_serial=adb_serial,
        args=["shell", "sha256sum", path],
    )
    stdout = str(result.stdout or "").strip()
    if result.returncode != 0 or not stdout:
        return ""
    return stdout.split(maxsplit=1)[0].strip()


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
        creationflags=_subprocess_creationflags(),
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
    smart_log(f"{label} stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
    smart_log(f"{label} stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
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
        smart_log(f"push {local_path.name} stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
        smart_log(f"push {local_path.name} stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
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
        smart_log(f"provision command: {command}", domain="android", source="android_client.install")
        smart_log(f"provision stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
        smart_log(f"provision stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
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
        smart_log(f"try privileged partition: {partition_root}", domain="android", source="android_client.install")
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
    smart_log(f"priv-app reboot stdout: {reboot_result.stdout.strip()}", domain="android", source="android_client.install")
    smart_log(f"priv-app reboot stderr: {reboot_result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
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
    smart_log(
        "priv-app decision input "
        f"installed={installed} privileged={privileged} code_path={code_path or '<missing>'} "
        f"recorded_mode={recorded_mode or '<none>'} "
        f"recorded_hash={recorded_hash or '<none>'} current_hash={current_hash}",
        domain="android", source="android_client.install")
    if installed and privileged:
        device_hash = _device_file_hash(
            adb_executable=adb_executable,
            adb_serial=adb_serial,
            path=code_path,
        )
        smart_log(f"device priv-app hash: {device_hash or '<unavailable>'}", domain="android", source="android_client.install")
        if device_hash == current_hash:
            if recorded_mode != "privapp" or recorded_hash != current_hash:
                install_state[state_key] = _install_state_value(mode="privapp", apk_hash=current_hash)
                _save_install_state(install_state)
                smart_log("repaired priv-app install state from device hash", domain="android", source="android_client.install")
            smart_log("priv-app already installed with matching device hash, skip install", domain="android", source="android_client.install")
            return False
        if not device_hash and recorded_mode == "privapp" and recorded_hash == current_hash:
            smart_log("priv-app already installed with matching recorded hash, skip install", domain="android", source="android_client.install")
            return False

    smart_log("privileged provisioning required; start official adb root/remount flow", domain="android", source="android_client.install")
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
    smart_log("priv-app install finished", domain="android", source="android_client.install")
    return True


def is_test_apk_installed(*, adb_serial: str | None = None, package_name: str = PACKAGE_NAME) -> bool:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        raise RuntimeError("adb is not available in PATH.")

    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["shell", "pm", "path", package_name])
    smart_log(f"probe install status: {' '.join(cmd)}", domain="android", source="android_client.install")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    smart_log(f"probe stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
    smart_log(f"probe stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
    return result.returncode == 0 and "package:" in str(result.stdout or "")


def install_test_apk(*, apk_path: str | Path | None = None, adb_serial: str | None = None) -> subprocess.CompletedProcess[str]:
    adb_executable = shutil.which("adb")
    if not adb_executable:
        smart_log("adb is not available in PATH during install", level="error", domain="android", source="android_client.install")
        raise RuntimeError("adb is not available in PATH.")

    resolved_apk_path = Path(apk_path or DEFAULT_APK_PATH).resolve()
    if not resolved_apk_path.exists():
        smart_log(f"test APK not found: {resolved_apk_path}", level="error", domain="android", source="android_client.install")
        raise RuntimeError(f"android_client test APK was not found: {resolved_apk_path}")

    cmd = _adb_base_cmd(adb_executable=adb_executable, adb_serial=adb_serial)
    cmd.extend(["install", "-r", "-g", "-t", str(resolved_apk_path)])
    smart_log(f"install APK: {' '.join(cmd)}", domain="android", source="android_client.install")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        creationflags=_subprocess_creationflags(),
    )
    smart_log(f"install stdout: {result.stdout.strip()}", domain="android", source="android_client.install")
    smart_log(f"install stderr: {result.stderr.strip()}", level="warning", domain="android", source="android_client.install")
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
    requested_serial = str(adb_serial or "").strip()
    effective_serial = resolve_adb_serial_for_command(requested_serial)
    smart_log(
        "ensure install start "
        f"adb={adb_executable} requested_serial={_serial_for_log(requested_serial)} "
        f"effective_serial={_serial_for_log(effective_serial)} "
        f"require_privileged={require_privileged} explicit_apk={apk_path is not None} frozen={getattr(sys, 'frozen', False)}",
        domain="android", source="android_client.install")
    _ensure_device_ready_before_install(adb_executable=adb_executable, adb_serial=requested_serial)

    resolved_apk_path = Path(apk_path or DEFAULT_APK_PATH).resolve()
    smart_log(f"resolved APK path before build/sign: {resolved_apk_path}", domain="android", source="android_client.install")
    if apk_path is None and not getattr(sys, "frozen", False):
        _ensure_debug_apk_built(RAW_DEBUG_APK_PATH)
        resolved_apk_path = sign_privileged_apk(input_apk_path=RAW_DEBUG_APK_PATH, output_apk_path=DEFAULT_APK_PATH)
    if not resolved_apk_path.exists():
        smart_log(f"ensure install failed, APK missing: {resolved_apk_path}", level="error", domain="android", source="android_client.install")
        raise RuntimeError(f"android_client test APK was not found: {resolved_apk_path}")

    installed = is_test_apk_installed(adb_serial=requested_serial)

    current_hash = _apk_hash(resolved_apk_path)
    state_key = _install_state_key(adb_serial=effective_serial, apk_path=resolved_apk_path)
    install_state = _load_install_state()
    recorded_mode, recorded_hash = _parse_install_state_value(install_state.get(state_key, ""))
    code_path = _package_code_path(adb_executable=adb_executable, adb_serial=requested_serial)
    version_info = _package_version_info(adb_executable=adb_executable, adb_serial=requested_serial)
    smart_log(f"final APK path for install decision: {resolved_apk_path}", domain="android", source="android_client.install")
    smart_log(f"current apk hash: {current_hash}", domain="android", source="android_client.install")
    smart_log(f"installed on device: {installed}", domain="android", source="android_client.install")
    smart_log(f"device package code_path: {code_path or '<missing>'}", domain="android", source="android_client.install")
    smart_log(
        "device package version "
        f"versionCode={version_info.get('version_code') or '<missing>'} "
        f"versionName={version_info.get('version_name') or '<missing>'} "
        f"error={version_info.get('error') or '<none>'}",
        domain="android", source="android_client.install")
    smart_log(f"install state path: {INSTALL_STATE_PATH}", domain="android", source="android_client.install")
    smart_log(f"install state key: {state_key}", domain="android", source="android_client.install")
    smart_log(
        "install state recorded "
        f"mode={recorded_mode or '<none>'} hash={recorded_hash or '<none>'} "
        f"state_entries={len(install_state)}",
        domain="android", source="android_client.install")

    if require_privileged:
        return _ensure_privileged_install(
            adb_executable=adb_executable,
            resolved_apk_path=resolved_apk_path,
            adb_serial=requested_serial,
            current_hash=current_hash,
            state_key=state_key,
            install_state=install_state,
            installed=installed,
            code_path=code_path,
            recorded_mode=recorded_mode,
            recorded_hash=recorded_hash,
        )

    if installed and "/system/priv-app/" in code_path:
        smart_log("existing package is priv-app; verify/reinstall signed APK", domain="android", source="android_client.install")
        return _ensure_privileged_install(
            adb_executable=adb_executable,
            resolved_apk_path=resolved_apk_path,
            adb_serial=requested_serial,
            current_hash=current_hash,
            state_key=state_key,
            install_state=install_state,
            installed=installed,
            code_path=code_path,
            recorded_mode=recorded_mode,
            recorded_hash=recorded_hash,
        )

    if installed and recorded_mode == "user" and recorded_hash == current_hash:
        smart_log("decision: signed APK already installed with matching recorded hash, skip install", domain="android", source="android_client.install")
        return False

    if not installed:
        smart_log("decision: package missing on DUT, start install", domain="android", source="android_client.install")
    else:
        smart_log("decision: installed package is stale or unrecorded, start install", domain="android", source="android_client.install")
    install_test_apk(apk_path=resolved_apk_path, adb_serial=requested_serial)
    if not is_test_apk_installed(adb_serial=requested_serial):
        raise RuntimeError("android_client test APK install completed but package is still missing on DUT.")
    install_state[state_key] = _install_state_value(mode="user", apk_hash=current_hash)
    _save_install_state(install_state)
    smart_log("signed APK install finished", domain="android", source="android_client.install")
    return True


__all__ = [
    "DEFAULT_APK_PATH",
    "INSTALL_STATE_PATH",
    "PACKAGE_NAME",
    "PRIVILEGED_CASE_IDS",
    "ensure_test_apk_installed",
    "install_test_apk",
    "is_test_apk_installed",
    "sign_privileged_apk",
]
