from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from testing.runner import execution


def test_packaged_runtime_uses_bundled_python_pytest_runner(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    runtime_root = tmp_path / "_internal"
    bundled_python = runtime_root / "python" / "python.exe"
    bundled_python.parent.mkdir(parents=True)
    bundled_python.write_text("", encoding="utf-8")

    class _TempDir:
        name = "C:/tmp/smarttest-run"

        def cleanup(self) -> None:
            pass

    class _Process:
        stdout = None

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Process()

    monkeypatch.setattr(execution, "is_packaged_runtime", lambda: True)
    monkeypatch.setattr(execution.tempfile, "TemporaryDirectory", lambda prefix: _TempDir())
    monkeypatch.setattr(execution.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sys, "_MEIPASS", str(runtime_root), raising=False)

    session = execution.start_pytest_run(
        root_dir=Path("D:/SmartTest"),
        nodeids=["testing/tests/example.py::test_case"],
    )

    assert session.process is not None
    assert captured["cmd"] == [
        str(bundled_python),
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-s",
        "-q",
        "--disable-warnings",
        "testing/tests/example.py::test_case",
    ]
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["cwd"] == str(runtime_root.resolve())
    env = kwargs["env"]
    assert "SMARTTEST_STEP_EVENTS_OUT" in env
    assert "SMARTTEST_RUN_CONFIG_JSON" in env
