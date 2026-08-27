from __future__ import annotations

from contextlib import contextmanager
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from client.packaging.tool_runtime_resources import missing_required

DIST_ROOT = ROOT / "dist" / "tool"
STAGING_ROOT = ROOT / "build" / "tool_runtime"
APP_NAME = "SmartTestTool"
BUILD_LOCK = ROOT / "build" / "portable-tool-build.lock"
FORBIDDEN_TOKENS = ("cv2", "testing", "mobile.android")
FORBIDDEN_ARCHIVE_MODULES = (
    "example.main",
    "example.bridge.HomeBridge",
    "example.bridge.RunBridge",
    "example.bridge.ReportBridge",
    "example.bridge.TestPageBridge",
    "example.bridge.DebugBridge",
    "example.bridge.BootVideoBridge",
    "cv2",
    "testing",
    "mobile.android",
)


@contextmanager
def portable_build_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        raise RuntimeError(
            "SmartTest Tool portable build is already running."
        ) from exc
    try:
        yield
    finally:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()


def validate_distribution(app_dir: Path) -> dict[str, int]:
    executable = app_dir / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise RuntimeError(f"Missing portable executable: {executable}")
    missing = missing_required(app_dir)
    if missing:
        raise RuntimeError("Missing portable runtime resources: " + ", ".join(missing))
    files = sorted(path for path in app_dir.rglob("*") if path.is_file())
    offending = [
        str(path.relative_to(app_dir)) for path in files
        if any(token in str(path.relative_to(app_dir)).lower()
               for token in FORBIDDEN_TOKENS)
    ]
    if offending:
        raise RuntimeError("Forbidden portable payload: " + ", ".join(offending))
    return {"files": len(files), "bytes": sum(path.stat().st_size for path in files)}


def create_portable_zip(app_dir: Path, version: str, output_dir: Path) -> Path:
    archive = output_dir / f"{APP_NAME}-{version}-windows-x64.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
        for path in sorted(item for item in app_dir.rglob("*") if item.is_file()):
            package.write(path, Path(APP_NAME) / path.relative_to(app_dir))
    return archive


def build_metrics(
    distribution: dict[str, int],
    archive: Path,
    *,
    elapsed_seconds: float,
) -> dict[str, int | float]:
    return {
        "files": distribution["files"],
        "bytes": distribution["bytes"],
        "zip_bytes": archive.stat().st_size,
        "build_seconds": round(elapsed_seconds, 2),
    }


def find_forbidden_archive_modules(archive_listing: str) -> list[str]:
    archived_modules = {line.strip() for line in archive_listing.splitlines()}
    return sorted(
        module for module in FORBIDDEN_ARCHIVE_MODULES
        if any(
            archived == module or archived.startswith(module + ".")
            for archived in archived_modules
        )
    )


def validate_python_archive(executable: Path, archive_viewer: Path) -> None:
    result = subprocess.run(
        [str(archive_viewer), "-r", "-b", str(executable)],
        check=True, capture_output=True, text=True,
    )
    offending = find_forbidden_archive_modules(result.stdout)
    if offending:
        raise RuntimeError("Forbidden Python archive modules: " + ", ".join(offending))


def validate_startup(executable: Path, seconds: float = 8.0) -> None:
    environment = dict(os.environ, QT_QUICK_BACKEND="software")
    process = subprocess.Popen([str(executable)], cwd=executable.parent, env=environment)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = process.poll()
        if result is not None:
            raise RuntimeError(f"Portable executable exited during startup: {result}")
        time.sleep(0.25)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def validate_smoke_imports(executable: Path) -> None:
    result = subprocess.run(
        [str(executable), "--portable-smoke-imports"],
        cwd=executable.parent, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Portable smoke imports failed: " + result.stderr + result.stdout
        )
    if "SmartTestTool portable smoke imports: PASS" not in result.stdout:
        raise RuntimeError("Portable smoke imports did not report PASS")


def validate_credential_smoke(executable: Path) -> None:
    result = subprocess.run(
        [str(executable), "--portable-smoke-credentials"],
        cwd=executable.parent, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        output = result.stderr + result.stdout
        failure_type = "UnknownError"
        if "FAIL (" in output:
            failure_type = output.split("FAIL (", 1)[1].split(")", 1)[0]
        raise RuntimeError(
            f"Portable credential capability failed ({failure_type})"
        )
    if "SmartTestTool portable credentials: PASS" not in result.stdout:
        raise RuntimeError("Portable credential capability did not report PASS")


def validate_context_smoke(executable: Path) -> None:
    result = subprocess.run(
        [str(executable), "--portable-smoke-context"],
        cwd=executable.parent, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Portable context smoke failed: " + result.stderr + result.stdout
        )
    if "SmartTestTool portable context: PASS" not in result.stdout:
        raise RuntimeError("Portable context smoke did not report PASS")


def main() -> None:
    with portable_build_lock(BUILD_LOCK):
        build_portable()


def build_portable() -> None:
    import env

    started_at = time.monotonic()
    scripts = ROOT / "client" / "scripts"
    subprocess.run([env.python(), str(scripts / "update_translations.py")], check=True)
    subprocess.run([
        env.pyside6_rcc(), str(ROOT / "client/app/ui/example/imports/tool_resource.qrc"),
        "-o", str(ROOT / "client/app/ui/example/imports/tool_resource_rc.py"),
    ], check=True)
    subprocess.run([env.python(), str(ROOT / "core/devtools/scripts/build_manifest.py")], check=True)
    build_environment = env.environment()
    build_environment["SMARTTEST_REPO_ROOT"] = str(ROOT)
    work_dir = ROOT / "build" / "pyinstaller_tool"
    subprocess.run([
        env.pyinstaller(), "--clean", "-y", "--distpath", str(STAGING_ROOT),
        "--workpath", str(work_dir),
        str(ROOT / "client/packaging/pyinstaller/tool.spec"),
    ], cwd=ROOT, env=build_environment, check=True)
    app_dir = STAGING_ROOT / APP_NAME
    metrics = validate_distribution(app_dir)
    manifest = json.loads(
        (ROOT / "build/generated/build_manifest.json").read_text(encoding="utf-8")
    )
    executable = app_dir / f"{APP_NAME}.exe"
    validate_python_archive(
        executable, Path(env.pyinstaller()).with_name("pyi-archive_viewer.exe")
    )
    validate_smoke_imports(executable)
    validate_credential_smoke(executable)
    validate_context_smoke(executable)
    validate_startup(executable)
    archive = create_portable_zip(app_dir, manifest["version"], DIST_ROOT)
    metrics = build_metrics(
        metrics, archive, elapsed_seconds=time.monotonic() - started_at,
    )
    print(f"Portable folder: {app_dir}")
    print(f"Portable archive: {archive}")
    print(
        "Portable metrics: "
        f"{metrics['files']} files, {metrics['bytes']} bytes, "
        f"{metrics['zip_bytes']} zip bytes, {metrics['build_seconds']} seconds"
    )


if __name__ == "__main__":
    main()
