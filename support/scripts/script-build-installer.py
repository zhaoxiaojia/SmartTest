import os
from pathlib import Path
import shutil
import subprocess
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run(cmd, **kwargs):
    subprocess.run(cmd, check=True, **kwargs)


def _python(repo_root: Path) -> str:
    if sys.platform.startswith("win"):
        venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _run_packaging_preflight(repo_root: Path) -> None:
    python = _python(repo_root)
    pytest_dirs = [
        repo_root / "testing" / "self_tests" / "packaging",
        repo_root / "testing" / "self_tests" / "params",
    ]
    for test_dir in pytest_dirs:
        if test_dir.exists():
            _run([python, "-m", "pytest", str(test_dir.relative_to(repo_root)), "-q"], cwd=str(repo_root))
    _run([python, "-m", "compileall", "testing", "support", str(Path("ui") / "example" / "bridge")], cwd=str(repo_root))


def _verify_dist_runtime(repo_root: Path) -> None:
    if sys.platform.startswith("darwin"):
        app_path = repo_root / "dist" / "SmartTest.app"
        if not app_path.exists():
            raise SystemExit(f"Packaged macOS app is missing: {app_path}")
        return

    required_paths = [
        repo_root / "dist" / "SmartTest.exe",
        repo_root / "dist" / "python" / "python.exe",
        repo_root / "dist" / "testing",
        repo_root / "dist" / "support",
        repo_root / "dist" / "support" / "param_conversion.py",
        repo_root / "dist" / "ui",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise SystemExit("Packaged runtime is missing required files:\n" + "\n".join(missing))

    runtime_python = repo_root / "dist" / "python" / "python.exe"
    _run(
        [
            str(runtime_python),
            "-c",
            "import sys; sys.path.insert(0, r'dist'); import support.param_conversion; import testing.params.options; import cv2; import testing.tool.boot_video.service; import ui.example.bridge.BootVideoBridge",
        ],
        cwd=str(repo_root),
    )


def _create_macos_zip(repo_root: Path) -> Path:
    app_path = repo_root / "dist" / "SmartTest.app"
    if not app_path.exists():
        raise SystemExit(f"Packaged macOS app is missing: {app_path}")
    output_dir = repo_root / "dist_installer"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_base = output_dir / "SmartTest-macos"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=app_path.parent, base_dir=app_path.name))
    return archive_path


def _verify_signed_apk_artifact(repo_root: Path) -> None:
    apk_path = repo_root / "dist_installer" / "app-debug-platform.apk"
    if not apk_path.exists():
        raise SystemExit(
            "Signed Android APK is missing:\n"
            f"{apk_path}\n"
            "Build it first with:\n"
            f"{_python(repo_root)} {repo_root / 'support' / 'scripts' / 'script-build-apk.py'}"
        )
    if apk_path.stat().st_size <= 0:
        raise SystemExit(f"Signed Android APK is empty: {apk_path}")


def _find_iscc():
    iscc = shutil.which("iscc") or shutil.which("iscc.exe") or shutil.which("ISCC.exe")
    if iscc:
        return iscc
    # Typical install locations.
    candidates = []
    pf = os.environ.get("ProgramFiles")
    pfx86 = os.environ.get("ProgramFiles(x86)")
    for base in [pfx86, pf]:
        if not base or not os.path.isdir(base):
            continue
        # Common exact paths.
        candidates.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
        candidates.append(os.path.join(base, "Inno Setup 5", "ISCC.exe"))
        # More tolerant scan: any folder starting with "Inno Setup"
        try:
            for name in os.listdir(base):
                if not name.lower().startswith("inno setup"):
                    continue
                candidates.append(os.path.join(base, name, "ISCC.exe"))
        except OSError:
            pass
    # Per-user install location (winget often installs here without admin).
    localappdata = os.environ.get("LocalAppData")
    if localappdata:
        candidates.append(os.path.join(localappdata, "Programs", "Inno Setup 6", "ISCC.exe"))
        candidates.append(os.path.join(localappdata, "Programs", "Inno Setup 5", "ISCC.exe"))

    # Registry-based lookup for custom locations.
    if sys.platform.startswith("win"):
        try:
            import winreg  # type: ignore
        except Exception:
            winreg = None
        if winreg:
            for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                for base_key in [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                ]:
                    try:
                        with winreg.OpenKey(hive, base_key) as k:
                            i = 0
                            while True:
                                try:
                                    sub = winreg.EnumKey(k, i)
                                except OSError:
                                    break
                                i += 1
                                try:
                                    with winreg.OpenKey(k, sub) as sk:
                                        try:
                                            dn = winreg.QueryValueEx(sk, "DisplayName")[0]
                                        except OSError:
                                            continue
                                        if not isinstance(dn, str) or "inno setup" not in dn.lower():
                                            continue
                                        try:
                                            il = winreg.QueryValueEx(sk, "InstallLocation")[0]
                                        except OSError:
                                            il = ""
                                        if isinstance(il, str) and il:
                                            candidates.append(os.path.join(il, "ISCC.exe"))
                                except OSError:
                                    continue
                    except OSError:
                        continue
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _build_windows_installer(repo_root: Path, scripts_dir: str) -> None:
    # 0) Fail fast on checks that protect the installed runtime from import/resource drift.
    _run_packaging_preflight(repo_root)
    _verify_signed_apk_artifact(repo_root)

    # 1) Build app (PyInstaller) -> dist/
    _run([_python(repo_root), os.path.join(scripts_dir, "script-build-pyinstaller.py")])

    # 2) Verify the packaged runtime contains the Python subprocess dependencies.
    _verify_dist_runtime(repo_root)

    # 3) Wrap dist/ into an installer (Inno Setup) -> dist_installer/
    iscc = _find_iscc()
    if not iscc:
        raise SystemExit(
            "Inno Setup not found (iscc.exe). Install it first, then re-run this script."
        )
    iss = os.path.join(str(repo_root), "support", "packaging", "innosetup", "SmartTest.iss")
    _run([iscc, iss], cwd=os.path.dirname(iss))


def _build_macos_package(repo_root: Path, scripts_dir: str) -> None:
    _run_packaging_preflight(repo_root)
    _verify_signed_apk_artifact(repo_root)
    _run([_python(repo_root), os.path.join(scripts_dir, "script-build-pyinstaller.py")])
    _verify_dist_runtime(repo_root)
    archive_path = _create_macos_zip(repo_root)
    print(f"macOS package output: {archive_path}")


if __name__ == "__main__":
    repo_root = _repo_root()
    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    if sys.platform.startswith("win"):
        _build_windows_installer(repo_root, scripts_dir)
        raise SystemExit(0)

    if sys.platform.startswith("darwin"):
        _build_macos_package(repo_root, scripts_dir)
        raise SystemExit(0)

    if sys.platform.startswith("linux"):
        raise SystemExit("Linux installer packaging is not wired yet in this repo. Build on Linux with AppImage/deb/rpm step.")

    raise SystemExit(f"Unsupported platform: {sys.platform}")
