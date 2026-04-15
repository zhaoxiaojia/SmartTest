from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .models import TestCaseInfo


class PytestDiscoveryError(RuntimeError):
    pass


def discover_pytest_cases(
    *,
    root_dir: Path,
    test_paths: list[Path] | None = None,
    python_executable: str | None = None,
) -> list[TestCaseInfo]:
    """
    Collect pytest items and return nodeids with marker metadata.

    This runs a subprocess to keep pytest collection isolated from the UI process.
    """
    root_dir = root_dir.resolve()
    if test_paths is None:
        test_paths = [root_dir / "testing" / "tests"]

    python_executable = python_executable or "python"

    with tempfile.TemporaryDirectory(prefix="smarttest_pytest_collect_") as tmpdir:
        out_file = Path(tmpdir) / "collected.json"
        env = os.environ.copy()
        env["SMARTTEST_PYTEST_COLLECT_OUT"] = str(out_file)
        # Ensure the repo root is importable so the plugin module can be found.
        env["PYTHONPATH"] = str(root_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

        cmd = [
            python_executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--disable-warnings",
        ] + [str(p) for p in test_paths]

        proc = subprocess.run(
            cmd,
            cwd=str(root_dir),
            env=env,
            capture_output=True,
            text=True,
        )
        # pytest uses exit code 5 when no tests were collected.
        if proc.returncode not in (0, 5):
            raise PytestDiscoveryError(
                "Pytest collection failed.\n\n"
                f"Command: {' '.join(cmd)}\n\n"
                f"stdout:\n{proc.stdout}\n\n"
                f"stderr:\n{proc.stderr}"
            )

        if not out_file.exists():
            raise PytestDiscoveryError("Pytest collection produced no output file.")

        raw = json.loads(out_file.read_text(encoding="utf-8"))
        cases: list[TestCaseInfo] = []
        for item in raw:
            cases.append(
                TestCaseInfo(
                    nodeid=str(item["nodeid"]),
                    file=str(item.get("file", "")),
                    name=str(item.get("name", "")),
                    markers=[str(m) for m in item.get("markers", [])],
                    case_type=str(item.get("case_type", "default")),
                    required_params=[str(p) for p in item.get("required_params", [])],
                    required_param_groups=[str(g) for g in item.get("required_param_groups", [])],
                )
            )
        return cases
