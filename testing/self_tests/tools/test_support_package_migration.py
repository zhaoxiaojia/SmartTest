from __future__ import annotations

import importlib.util
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]


def test_shared_modules_are_owned_by_support_package():
    import support.logging
    import support.param_conversion
    import support.report

    assert support.logging.__file__
    assert support.param_conversion.__file__
    assert support.report.__file__
    assert importlib.util.find_spec("tools") is None


def test_packaging_owns_support_paths_only():
    package_spec = ROOT / "support/packaging/pyinstaller/main.spec"
    source = package_spec.read_text(encoding="utf-8")

    assert 'os.path.join(repo_root, "support")' in source
    assert 'support_root,\n            "support"' in source
    assert 'os.path.join(repo_root, "tools")' not in source
    assert 'support_root,\n            "tools"' not in source
    assert (ROOT / "support/scripts/script-build-manifest.py").is_file()
    assert (ROOT / "support/packaging/version.json").is_file()


def test_support_build_owners_have_no_removed_repository_paths():
    owners = [
        path
        for owner in (ROOT / "support/scripts", ROOT / "support/packaging")
        for path in owner.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".ps1", ".spec", ".iss", ".md"}
    ]
    stale_pattern = re.compile(r"tools[\\/]?(?:scripts|packaging)|[\"']tools[\"']\s*/\s*[\"'](?:scripts|packaging)[\"']")
    stale = {
        str(path.relative_to(ROOT)): [
            (line_number, line.strip())
            for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1)
            if stale_pattern.search(line)
        ]
        for path in owners
    }

    assert {path: rows for path, rows in stale.items() if rows} == {}
