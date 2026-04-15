"""Shared helpers for running host-side shell commands."""

from __future__ import annotations

import logging
import subprocess as _subprocess
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass
class CommandResult:
    """Container describing a completed shell command."""

    command: str
    stdout: str
    stderr: str
    returncode: int


PIPE = _subprocess.PIPE
DEVNULL = _subprocess.DEVNULL
STDOUT = _subprocess.STDOUT
CalledProcessError = _subprocess.CalledProcessError
TimeoutExpired = _subprocess.TimeoutExpired
CompletedProcess = _subprocess.CompletedProcess


class CommandExecutionError(RuntimeError):
    """Raised when a host command exits with a non-zero code."""


class CommandTimeoutError(RuntimeError):
    """Raised when a host command exceeds the allotted timeout."""


class _NullProcess:
    def __init__(self, exc: BaseException, args=None) -> None:
        self.args = args
        self.returncode = 1
        self.pid = None
        self.stdout = None
        self.stderr = None
        self._exc = exc

    def poll(self) -> int:
        return self.returncode

    def communicate(self, input=None, timeout: float | None = None):
        return "", str(self._exc)

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode

    def kill(self) -> None:
        return None

    def terminate(self) -> None:
        return None


class CommandRunner:
    """Lightweight wrapper around :mod:`subprocess` with consistent logging."""

    def __init__(self, encoding: str = "utf-8") -> None:
        self.default_encoding = encoding

    def popen(
        self,
        cmd: Sequence[str] | str,
        *,
        shell: bool = False,
        encoding: str | None = None,
        stdout=_subprocess.PIPE,
        stderr=_subprocess.PIPE,
        **kwargs,
    ) -> _subprocess.Popen[str]:
        """Launch a subprocess and return the raw ``Popen`` handle."""
        try:
            kwargs.setdefault("stdin", _subprocess.DEVNULL)
            process = _subprocess.Popen(
                cmd,
                shell=shell,
                stdout=stdout,
                stderr=stderr,
                encoding=encoding or self.default_encoding,
                errors=kwargs.pop("errors", "ignore"),
                **kwargs,
            )
            return process
        except Exception as exc:  # noqa: BLE001 - intentional swallow
            logging.exception("Command popen failed: %s", cmd)
            return _NullProcess(exc, cmd)

    def run(
        self,
        cmd: Sequence[str] | str,
        *,
        shell: bool = False,
        timeout: float | None = None,
        **kwargs,
    ) -> CommandResult:
        """Execute a command and capture its stdout/stderr."""
        logging.info("Executing host command: %s", cmd)
        capture_output = kwargs.pop("capture_output", False)
        kwargs.pop("check", None)
        input_data = kwargs.pop("input", None)
        if capture_output:
            kwargs.setdefault("stdout", _subprocess.PIPE)
            kwargs.setdefault("stderr", _subprocess.PIPE)
        process = self.popen(cmd, shell=shell, **kwargs)
        try:
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
        except _subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            logging.error("Command timed out after %ss: %s", timeout, cmd)
        return CommandResult(
            command=" ".join(cmd) if isinstance(cmd, Iterable) and not isinstance(cmd, str) else str(cmd),
            stdout=stdout or "",
            stderr=stderr or "",
            returncode=process.returncode,
        )


class CommandBatch:
    """Accumulates commands to be executed sequentially with shared error handling."""

    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner
        self._entries: list[tuple[str, float | None, bool, bool]] = []

    def add(
        self,
        command: str,
        *,
        timeout: float | None = None,
        shell: bool = True,
        ignore_error: bool = True,
    ) -> None:
        """Enqueue a new command for execution."""
        if not command:
            return
        self._entries.append((command, timeout, shell, ignore_error))

    def run(self) -> List[CommandResult]:
        """Run all queued commands in order."""
        results: List[CommandResult] = []
        while self._entries:
            command, timeout, shell, ignore_error = self._entries.pop(0)
            result = self._runner.run(command, shell=shell, timeout=timeout)
            if result.returncode != 0:
                logging.warning(
                    "Command exited with %s: %s\nstderr: %s",
                    result.returncode,
                    result.command,
                    result.stderr.strip(),
                )
            results.append(result)
        return results


_DEFAULT_RUNNER = CommandRunner()


def run(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    result = _DEFAULT_RUNNER.run(cmd, **kwargs)
    return _subprocess.CompletedProcess(cmd, result.returncode, result.stdout, result.stderr)


def Popen(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    return _DEFAULT_RUNNER.popen(cmd, **kwargs)


def check_output(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    result = _DEFAULT_RUNNER.run(cmd, **kwargs)
    if result.returncode != 0:
        logging.warning("Command exited with %s: %s", result.returncode, result.command)
    return result.stdout
