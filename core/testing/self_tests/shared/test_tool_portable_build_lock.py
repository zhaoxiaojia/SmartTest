from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "client/scripts/build_tool_portable.py"


def _module():
    spec = importlib.util.spec_from_file_location("tool_portable_build", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_portable_build_lock_rejects_concurrent_owner_and_releases(tmp_path):
    module = _module()
    lock_path = tmp_path / "portable-tool-build.lock"

    with module.portable_build_lock(lock_path):
        with pytest.raises(RuntimeError, match="already running"):
            with module.portable_build_lock(lock_path):
                pass

    with module.portable_build_lock(lock_path):
        assert lock_path.is_file()
