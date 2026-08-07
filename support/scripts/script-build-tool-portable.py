from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import zipfile


ROOT = Path(__file__).resolve().parents[2]
DIST_ROOT = ROOT / "dist_tool"
APP_NAME = "SmartTestTool"
FORBIDDEN_TOKENS = ("cv2", "testing", "android_client")
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
    "android_client",
)


def validate_distribution(app_dir: Path) -> dict[str, int]:
    executable = app_dir / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise RuntimeError(f"Missing portable executable: {executable}")
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


def main() -> None:
    import env

    started_at = time.monotonic()
    scripts = ROOT / "support" / "scripts"
    subprocess.run([env.python(), str(scripts / "script-update-translations.py")], check=True)
    subprocess.run([
        env.pyside6_rcc(), str(ROOT / "ui/example/imports/tool_resource.qrc"),
        "-o", str(ROOT / "ui/example/imports/tool_resource_rc.py"),
    ], check=True)
    subprocess.run([env.python(), str(scripts / "script-build-manifest.py")], check=True)
    build_environment = env.environment()
    build_environment["SMARTTEST_REPO_ROOT"] = str(ROOT)
    work_dir = ROOT / "build" / "pyinstaller_tool"
    subprocess.run([
        env.pyinstaller(), "--clean", "-y", "--distpath", str(DIST_ROOT),
        "--workpath", str(work_dir),
        str(ROOT / "support/packaging/pyinstaller/tool.spec"),
    ], cwd=ROOT, env=build_environment, check=True)
    app_dir = DIST_ROOT / APP_NAME
    metrics = validate_distribution(app_dir)
    manifest = json.loads(
        (ROOT / "build/generated/build_manifest.json").read_text(encoding="utf-8")
    )
    executable = app_dir / f"{APP_NAME}.exe"
    validate_python_archive(
        executable, Path(env.pyinstaller()).with_name("pyi-archive_viewer.exe")
    )
    validate_smoke_imports(executable)
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
