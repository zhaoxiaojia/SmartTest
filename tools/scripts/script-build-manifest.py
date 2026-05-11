from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


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


def main() -> None:
    catalog = ROOT / "build" / "generated" / "testing" / "cases" / "test_catalog.json"
    android_catalog = ROOT / "android_client" / "app" / "src" / "main" / "java" / "com" / "smarttest" / "mobile" / "runner" / "SmartTestCatalog.kt"
    manifest_path = ROOT / "build" / "generated" / "build_manifest.json"
    payload = {
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
    print(f"Build manifest: {manifest_path}")


if __name__ == "__main__":
    main()
