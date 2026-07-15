from __future__ import annotations

import importlib.util
from pathlib import Path


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
