from __future__ import annotations

import subprocess

from testing.params.adb_devices import _decode_adb_output, _hidden_process_kwargs, resolve_adb_serial_for_command


def effective_adb_serial(selected_serial: str | None) -> str | None:
    return resolve_adb_serial_for_command(selected_serial)


def build_adb_command(
    *,
    selected_serial: str | None,
    args: list[str],
    adb_executable: str = "adb",
) -> list[str]:
    command = [adb_executable]
    serial = effective_adb_serial(selected_serial)
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    return command


def run_adb(
    *,
    selected_serial: str | None,
    args: list[str],
    timeout: float,
    check: bool,
    adb_executable: str = "adb",
) -> subprocess.CompletedProcess[str]:
    command = build_adb_command(
        selected_serial=selected_serial,
        args=args,
        adb_executable=adb_executable,
    )
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=False,
            check=False,
            timeout=timeout,
            **_hidden_process_kwargs(),
        )
    except FileNotFoundError as exc:
        raise RuntimeError("adb was not found in PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ADB command timed out after {timeout}s: {' '.join(command)}") from exc

    completed = subprocess.CompletedProcess(
        command,
        result.returncode,
        _decode_adb_output(result.stdout),
        _decode_adb_output(result.stderr),
    )
    if check and completed.returncode != 0:
        detail = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        raise RuntimeError(f"ADB command failed ({completed.returncode}): {' '.join(command)}\n{detail}")
    return completed
