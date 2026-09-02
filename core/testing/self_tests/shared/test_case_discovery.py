from __future__ import annotations

import sys
from pathlib import Path

from core.testing.cases.discovery import discover_pytest_cases


ROOT = Path(__file__).resolve().parents[4]


def test_discovery_does_not_shadow_python_stdlib_packages() -> None:
    cases = discover_pytest_cases(root_dir=ROOT, python_executable=sys.executable)

    assert cases
    assert all(case.nodeid.startswith("testing/tests/") for case in cases)
