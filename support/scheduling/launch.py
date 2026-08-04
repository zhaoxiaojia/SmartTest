"""Resolve and serialize source or packaged launch commands."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Iterable

from .models import LaunchCommand


def resolve_launch_command(
    *,
    executable: Path | None = None,
    packaged: bool | None = None,
    main_script: Path | None = None,
) -> LaunchCommand:
    provided = executable is not None
    resolved_executable = Path(executable or sys.executable).resolve()
    if packaged is None:
        packaged = bool(
            getattr(sys, "frozen", False)
            or provided and resolved_executable.suffix.casefold() == ".exe"
        )
    if packaged:
        return LaunchCommand(resolved_executable)
    script = Path(
        main_script or Path(__file__).resolve().parents[2] / "main.py"
    ).resolve()
    return LaunchCommand(resolved_executable, (str(script),))


def serialize_arguments(arguments: Iterable[str]) -> str:
    return subprocess.list2cmdline([str(value) for value in arguments])
