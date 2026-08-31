from __future__ import annotations

import json
import logging as py_logging
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from .formatter import readable_line
from .record import SmartLogRecord, build_log_record, infer_source_and_domain, normalize_platform, safe_text

SMARTTEST_LOG_DIR_ENV = "SMARTTEST_LOG_DIR"
SMARTTEST_STEP_EVENTS_OUT_ENV = "SMARTTEST_STEP_EVENTS_OUT"
SMARTTEST_LOG_COLOR_ENV = "SMARTTEST_LOG_COLOR"
SMARTTEST_LOG_FILE_NAME = "smarttest.log"
SMARTTEST_READABLE_LOG_FILE_NAME = "smarttest_readable.log"

_FILE_LOCK = threading.Lock()
_EVENT_LOCK = threading.Lock()
_CONSOLE_LOCK = threading.Lock()
_PLATFORM_LOCK = threading.Lock()
_default_platform = "client"


def configure_platform(platform: str) -> str:
    """Set this process's product platform and return its previous value."""
    normalized = normalize_platform(platform)
    global _default_platform
    with _PLATFORM_LOCK:
        previous = _default_platform
        _default_platform = normalized
    return previous


def current_platform() -> str:
    with _PLATFORM_LOCK:
        return _default_platform


def default_log_dir() -> Path:
    configured = safe_text(os.environ.get(SMARTTEST_LOG_DIR_ENV))
    if configured:
        return Path(configured)
    local_app_data = safe_text(os.environ.get("LOCALAPPDATA"))
    if local_app_data:
        return Path(local_app_data) / "Amlogic" / "SmartTest" / "logs"
    if sys.platform.startswith("darwin"):
        return Path.home() / "Library" / "Logs" / "Amlogic" / "SmartTest"
    return Path.cwd() / "logs"


def default_log_path() -> Path:
    return default_log_dir() / SMARTTEST_LOG_FILE_NAME


def default_readable_log_path() -> Path:
    return default_log_dir() / SMARTTEST_READABLE_LOG_FILE_NAME


def set_external_logger_level(name: str, level: str = "warning") -> None:
    py_level = getattr(py_logging, level.upper(), py_logging.WARNING)
    py_logging.getLogger(name).setLevel(py_level)


class SmartLoggingHandler(py_logging.Handler):
    def __init__(self, *, platform: str, domain: str = "framework") -> None:
        super().__init__()
        self.platform = platform
        self.domain = domain

    def emit(self, record: py_logging.LogRecord) -> None:
        smart_log(
            record.getMessage(),
            platform=self.platform,
            domain=self.domain,
            level=record.levelname,
            source=record.name,
            exc_info=record.exc_info,
            emit_runtime_event=False,
        )


def configure_external_logging(
    *names: str, platform: str, domain: str = "framework"
) -> None:
    handler = SmartLoggingHandler(platform=platform, domain=domain)
    for name in names:
        logger = py_logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False


def _format_message(message: Any, args: tuple[Any, ...]) -> str:
    text = str(message)
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return f"{text} {' '.join(map(str, args))}".rstrip()


def write_static_log(record: SmartLogRecord, *, path: Path | None = None) -> Path:
    target = path or default_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record.to_static_payload(), ensure_ascii=False, sort_keys=True)
    with _FILE_LOCK:
        with target.open("a", encoding="utf-8") as stream:
            stream.write(encoded + "\n")
        readable = (
            target.with_name(SMARTTEST_READABLE_LOG_FILE_NAME)
            if path
            else default_readable_log_path()
        )
        with readable.open("a", encoding="utf-8") as stream:
            stream.write(readable_line(record) + "\n")
    return target


def _write_event(record: SmartLogRecord) -> None:
    raw_path = safe_text(os.environ.get(SMARTTEST_STEP_EVENTS_OUT_ENV))
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record.to_event_payload(), ensure_ascii=False)
    with _EVENT_LOCK:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(encoded + "\n")


def _console_color_enabled(stdout: Any) -> bool:
    mode = safe_text(os.environ.get(SMARTTEST_LOG_COLOR_ENV)).lower()
    if mode in {"0", "false", "no", "off", "never"}:
        return False
    if mode in {"1", "true", "yes", "on", "always"}:
        return True
    return bool(getattr(stdout, "isatty", lambda: False)())


def _write_console(record: SmartLogRecord) -> None:
    if safe_text(os.environ.get(SMARTTEST_STEP_EVENTS_OUT_ENV)):
        return
    stdout = getattr(sys, "stdout", None)
    if stdout is None or not hasattr(stdout, "write"):
        return
    line = readable_line(record, color_enabled=_console_color_enabled(stdout))
    with _CONSOLE_LOCK:
        stdout.write(line + "\n")
        stdout.flush()


def smart_log(
    message: Any,
    *args: Any,
    platform: str | None = None,
    domain: str | None = None,
    level: str = "info",
    source: str | None = None,
    request_id: str | None = None,
    case_nodeid: str | None = None,
    step_id: str | None = None,
    extra: dict[str, Any] | None = None,
    emit_runtime_event: bool = True,
    static_path: Path | None = None,
    exc_info: Any = False,
) -> SmartLogRecord:
    inferred_source, inferred_domain = infer_source_and_domain()
    merged_extra = dict(extra or {})
    if exc_info and sys.exc_info()[0] is not None:
        merged_extra["traceback"] = "".join(traceback.format_exception(*sys.exc_info()))
    record = build_log_record(
        _format_message(message, args),
        platform=platform or current_platform(),
        domain=domain or inferred_domain,
        level=level,
        source=source or inferred_source,
        request_id=request_id,
        case_nodeid=case_nodeid,
        step_id=step_id,
        extra=merged_extra,
    )
    write_static_log(record, path=static_path)
    if emit_runtime_event:
        _write_event(record)
    _write_console(record)
    return record
