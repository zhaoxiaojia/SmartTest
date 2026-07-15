from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
VERSION_PATH = ROOT / "support" / "packaging" / "version.json"
INSTALLER_VERSION_INCLUDE = ROOT / "build" / "generated" / "installer_version.iss"
_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _load_version() -> str:
    if not VERSION_PATH.exists():
        return "1.0.0"
    try:
        payload = json.loads(VERSION_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid version file: {VERSION_PATH}") from exc
    version = str(payload.get("version", "") if isinstance(payload, dict) else "").strip()
    if not _VERSION_RE.match(version):
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH format in {VERSION_PATH}: {version!r}")
    return version


def _bump_patch(version: str) -> str:
    match = _VERSION_RE.match(version)
    if not match:
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH format: {version!r}")
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch")) + 1
    return f"{major}.{minor}.{patch}"


def _write_version(version: str) -> None:
    VERSION_PATH.write_text(
        json.dumps({"version": version}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_installer_version_include(version: str) -> None:
    INSTALLER_VERSION_INCLUDE.parent.mkdir(parents=True, exist_ok=True)
    INSTALLER_VERSION_INCLUDE.write_text(
        f'#define SmartTestAppVersion "{version}"\n',
        encoding="utf-8",
    )


def main() -> None:
    catalog = ROOT / "build" / "generated" / "testing" / "cases" / "test_catalog.json"
    android_catalog = ROOT / "android_client" / "app" / "src" / "main" / "java" / "com" / "smarttest" / "mobile" / "runner" / "SmartTestCatalog.kt"
    manifest_path = ROOT / "build" / "generated" / "build_manifest.json"
    version = _bump_patch(_load_version())
    built_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {
        "version": version,
        "built_at": built_at,
        "git_commit": _git_commit(),
        "files": {
            "test_catalog": {
                "path": str(catalog.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(catalog) if catalog.exists() else "",
            },
            "android_catalog": {
                "path": str(android_catalog.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(android_catalog) if android_catalog.exists() else "",
            },
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_version(version)
    _write_installer_version_include(version)
    print(f"Build manifest: {manifest_path}")
    print(f"Build version: {version}")
    print(f"Build time: {built_at}")


if __name__ == "__main__":
    main()
