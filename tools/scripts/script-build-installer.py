import os
import shutil
import subprocess
import sys
import typing as _t


def _repo_root():
    return os.path.abspath(".")


def _run(cmd, **kwargs):
    subprocess.run(cmd, check=True, **kwargs)


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


if __name__ == "__main__":
    repo_root = _repo_root()
    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    if sys.platform.startswith("win"):
        # 1) Build app (PyInstaller) -> dist/
        _run([os.path.join(repo_root, ".venv", "Scripts", "python.exe"), os.path.join(scripts_dir, "script-build-pyinstaller.py")])

        # 2) Wrap dist/ into an installer (Inno Setup) -> dist_installer/
        iscc = _find_iscc()
        if not iscc:
            raise SystemExit(
                "Inno Setup not found (iscc.exe). Install it first, then re-run this script."
            )
        iss = os.path.join(repo_root, "tools", "packaging", "innosetup", "SmartTest.iss")
        _run([iscc, iss], cwd=os.path.dirname(iss))
        raise SystemExit(0)

    if sys.platform.startswith("darwin"):
        raise SystemExit("macOS installer packaging is not wired yet in this repo. Build on macOS with a DMG step.")

    if sys.platform.startswith("linux"):
        raise SystemExit("Linux installer packaging is not wired yet in this repo. Build on Linux with AppImage/deb/rpm step.")

    raise SystemExit(f"Unsupported platform: {sys.platform}")
