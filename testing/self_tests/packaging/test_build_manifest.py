from __future__ import annotations

import json
import runpy
from pathlib import Path


def _load_script() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[3]
    return runpy.run_path(str(repo_root / "tools" / "scripts" / "script-build-manifest.py"))


def test_build_manifest_bumps_patch_version_and_writes_installer_include(tmp_path, monkeypatch) -> None:
    namespace = _load_script()
    version_path = tmp_path / "version.json"
    manifest_path = tmp_path / "build" / "generated" / "build_manifest.json"
    include_path = tmp_path / "build" / "generated" / "installer_version.iss"
    version_path.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")

    script_globals = namespace["main"].__globals__
    monkeypatch.setitem(script_globals, "ROOT", tmp_path)
    monkeypatch.setitem(script_globals, "VERSION_PATH", version_path)
    monkeypatch.setitem(script_globals, "INSTALLER_VERSION_INCLUDE", include_path)
    monkeypatch.setitem(script_globals, "_git_commit", lambda: "abc123")

    namespace["main"]()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version_state = json.loads(version_path.read_text(encoding="utf-8"))

    assert manifest["version"] == "1.0.1"
    assert manifest["built_at"]
    assert manifest["git_commit"] == "abc123"
    assert version_state == {"version": "1.0.1"}
    assert include_path.read_text(encoding="utf-8") == '#define SmartTestAppVersion "1.0.1"\n'
