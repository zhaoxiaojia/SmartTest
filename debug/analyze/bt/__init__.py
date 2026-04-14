"""BT firmware log capture and analysis helpers.

This module centralises all BT FW log business logic so that UI layers
only need to call into this package.  The implementation currently
wraps the legacy ``fw_log_tools`` parser but hides its location behind
stable functions:

* ``capture_serial_log`` – capture raw BT FW logs from a serial port.
* ``analyze_bt_fw_log`` – parse a raw FW log file and return decoded text.

Once the legacy parser has been fully ported, the dependency on the
``fw_log_tools`` folder can be removed without touching the UI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .parse_digit_log import start_parse_fw_log


def _looks_like_bt_fw_log(path: Path, sample_size: int = 32_000) -> bool:
    """Heuristic: does this file look like a raw BT FW hex log?"""

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:sample_size]
    except Exception:
        return False

    if not text.strip():
        return False

    import re

    tokens = re.split(r"\s+", text.strip())
    if not tokens:
        return False

    hex_tokens = [t for t in tokens if re.fullmatch(r"[0-9a-fA-F]{2}", t)]
    if len(hex_tokens) < 64:
        return False
    if len(hex_tokens) / len(tokens) < 0.7:
        return False
    return True


def analyze_bt_fw_log(
    log_path: str | Path,
    *,
    is_normal_mode: bool = True,
    add_timestamp: bool = True,
    on_chunk: Optional[Callable[[str], None]] = None,
    output_path: str | Path | None = None,
) -> str:
    """Parse a BT firmware log file and return the decoded text."""

    log_path = Path(log_path).resolve()
    import sys as _sys

    debug_out = getattr(_sys, "__stdout__", None) or _sys.stdout
    print(f"[bt-fw-debug] analyze_bt_fw_log: start path={log_path}", file=debug_out, flush=True)

    if not log_path.is_file():
        raise FileNotFoundError(f"BT FW log file not found: {log_path}")

    try:
        looks_like_fw = _looks_like_bt_fw_log(log_path)
    except Exception:
        looks_like_fw = True
    if not looks_like_fw and on_chunk is not None:
        on_chunk(
            "[bt-fw] Warning: file does not look like a pure BT FW hex log; "
            "parsing anyway, this may be slow.\n"
        )

    if output_path is None:
        output_path = log_path.with_name(log_path.stem + "_parsed.txt")
    output_path = Path(output_path)

    import os
    import sys

    class _StreamBuffer:
        """File-like object that forwards parser output."""

        def __init__(self, chunk_callback: Optional[Callable[[str], None]] = None) -> None:
            self._chunks: list[str] = []
            self._callback = chunk_callback

        def write(self, data: str) -> int:  # type: ignore[override]
            if not isinstance(data, str):
                data = str(data)
            if not data:
                return 0
            self._chunks.append(data)
            if self._callback is not None:
                self._callback(data)
            return len(data)

        def flush(self) -> None:  # type: ignore[override]
            return None

        def getvalue(self) -> str:
            return "".join(self._chunks)

    original_cwd = os.getcwd()
    original_stdout = sys.stdout
    buffer = _StreamBuffer(on_chunk)
    try:
        # Redirect parser stdout into the buffer so that callers can
        # stream output while preserving the original implementation.
        sys.stdout = buffer
        dummy_output = str(log_path.with_suffix(".parsed.txt"))
        start_parse_fw_log(str(log_path), is_normal_mode, add_timestamp, dummy_output)
    finally:
        os.chdir(original_cwd)
        sys.stdout = original_stdout

    result_text = buffer.getvalue()
    print(
        f"[bt-fw-debug] analyze_bt_fw_log: done, result_len={len(result_text)}",
        file=debug_out,
        flush=True,
    )

    try:
        if result_text:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result_text, encoding="utf-8", errors="ignore")
    except Exception:
        pass

    return result_text


def capture_serial_log(
    port: str,
    baudrate: int,
    *,
    add_timestamp: bool = True,
    on_raw_text: Optional[Callable[[str], None]] = None,
    stop_flag: Optional[Callable[[], bool]] = None,
    rotate_threshold_mb: int = 300,
) -> list[Path]:
    """Capture raw BT FW log data from a serial port.

    When the current log file exceeds ``rotate_threshold_mb`` it is
    closed and a new file is opened automatically.  All created paths
    are returned so that callers can run analysis on each chunk.
    """

    import datetime
    import time

    import serial  # type: ignore

    root = Path(__file__).resolve().parents[3]
    log_dir = root / "report" / "bt_fw_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    def _new_log_path() -> Path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return log_dir / f"bt_fw_log_{ts}.txt"

    paths: list[Path] = []
    current_path = _new_log_path()
    ser = serial.Serial(port, baudrate, timeout=0.2)
    try:
        fh = current_path.open("w", encoding="utf-8", errors="ignore")
        paths.append(current_path)
        if on_raw_text is not None:
            on_raw_text(f"start capture on {port} @ {baudrate}\n")
        rotate_threshold_bytes = max(1, int(rotate_threshold_mb)) * 1024 * 1024
        while not (stop_flag and stop_flag()):
            data = ser.read(4096)
            if not data:
                time.sleep(0.05)
                continue
            if on_raw_text is not None:
                on_raw_text(f"count = {len(data)}\n")
            if add_timestamp:
                now = datetime.datetime.now()
                ts = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " "
                fh.write(ts)
            fh.write(" ".join(f"{b:02x}" for b in data))
            fh.write("\n")
            fh.flush()
            # Rotate when file grows too large (approx. 300 MB by default).
            try:
                if fh.tell() >= rotate_threshold_bytes:
                    fh.close()
                    current_path = _new_log_path()
                    paths.append(current_path)
                    fh = current_path.open("w", encoding="utf-8", errors="ignore")
            except Exception:
                pass
    finally:
        try:
            fh.close()
        except Exception:
            pass
        try:
            ser.close()
        except Exception:
            pass

    if on_raw_text is not None:
        on_raw_text("stop capture\n")

    return paths


__all__ = ["analyze_bt_fw_log", "capture_serial_log"]
