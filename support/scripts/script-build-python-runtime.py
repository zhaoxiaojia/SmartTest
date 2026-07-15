from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _ignore_common(dirname: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__"}
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


def _copytree(src: Path, dst: Path, *, ignore=None) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore or _ignore_common)


def _copy_file_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _venv_root() -> Path:
    return Path(sys.prefix).resolve()


def _base_root() -> Path:
    return Path(sys.base_prefix).resolve()


def build_python_runtime(*, dist_dir: Path) -> Path:
    if os.name != "nt":
        raise SystemExit("Bundled Python runtime packaging is currently wired for Windows only.")

    runtime_dir = dist_dir / "python"
    shutil.rmtree(runtime_dir, ignore_errors=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    base_root = _base_root()
    venv_root = _venv_root()
    print(f"[python-runtime] base_root={base_root}")
    print(f"[python-runtime] venv_root={venv_root}")
    print(f"[python-runtime] output={runtime_dir}")

    _copy_file_if_exists(base_root / "python.exe", runtime_dir / "python.exe")
    _copy_file_if_exists(base_root / "pythonw.exe", runtime_dir / "pythonw.exe")
    for pattern in ("python*.dll", "vcruntime*.dll", "sqlite3.dll", "libcrypto*.dll", "libssl*.dll"):
        for item in base_root.glob(pattern):
            _copy_file_if_exists(item, runtime_dir / item.name)

    base_dlls = base_root / "DLLs"
    if base_dlls.exists():
        _copytree(base_dlls, runtime_dir / "DLLs")

    base_lib = base_root / "Lib"
    runtime_lib = runtime_dir / "Lib"
    ignore_lib = lambda dirname, names: _ignore_common(dirname, names) | {"site-packages"}
    _copytree(base_lib, runtime_lib, ignore=ignore_lib)

    venv_site_packages = venv_root / "Lib" / "site-packages"
    _copytree(venv_site_packages, runtime_lib / "site-packages")

    python_exe = runtime_dir / "python.exe"
    if not python_exe.exists():
        raise FileNotFoundError(f"Bundled python.exe was not created: {python_exe}")
    print(f"[python-runtime] bundled python: {python_exe}")
    return python_exe


if __name__ == "__main__":
    scripts_dir = Path(__file__).resolve().parent
    repo_root = scripts_dir.parents[1]
    build_python_runtime(dist_dir=repo_root / "dist")
