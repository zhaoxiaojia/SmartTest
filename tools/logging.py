from __future__ import annotations

import json
import logging as py_logging
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SMARTTEST_LOG_DIR_ENV = "SMARTTEST_LOG_DIR"
SMARTTEST_STEP_EVENTS_OUT_ENV = "SMARTTEST_STEP_EVENTS_OUT"
SMARTTEST_LOG_COLOR_ENV = "SMARTTEST_LOG_COLOR"
SMARTTEST_LOG_FILE_NAME = "smarttest.log"
SMARTTEST_READABLE_LOG_FILE_NAME = "smarttest_readable.log"

_FILE_LOCK = threading.Lock()
_EVENT_LOCK = threading.Lock()
_CONSOLE_LOCK = threading.Lock()

_RESET = "\033[0m"
_DOMAIN_COLORS = {
    "framework": "\033[36m",
    "ui": "\033[35m",
    "runner": "\033[34m",
    "test": "\033[32m",
    "dut": "\033[33m",
    "equipment": "\033[38;5;208m",
    "android": "\033[92m",
    "jira": "\033[95m",
    "python": "\033[37m",
}
_LEVEL_COLORS = {
    "debug": "\033[90m",
    "info": "",
    "warning": "\033[93m",
    "error": "\033[91m",
    "critical": "\033[97;41m",
}
_UI_DOMAIN_COLORS = {
    "framework": {"light": "#0F6CBD", "dark": "#62CDFF", "background_light": "#EAF6FF", "background_dark": "#102A3A"},
    "ui": {"light": "#8F12A6", "dark": "#E879F9", "background_light": "#FCEBFF", "background_dark": "#35113D"},
    "runner": {"light": "#2546B8", "dark": "#93B4FF", "background_light": "#EEF3FF", "background_dark": "#16234A"},
    "test": {"light": "#107C10", "dark": "#7EE787", "background_light": "#EAF7EA", "background_dark": "#13351B"},
    "dut": {"light": "#986F0B", "dark": "#FACC15", "background_light": "#FFF7D6", "background_dark": "#3A2B08"},
    "equipment": {"light": "#C43501", "dark": "#FDBA74", "background_light": "#FFF1E8", "background_dark": "#44200E"},
    "android": {"light": "#16833A", "dark": "#86EFAC", "background_light": "#E9F8EE", "background_dark": "#12351F"},
    "jira": {"light": "#6B3FA0", "dark": "#C4B5FD", "background_light": "#F3EEFF", "background_dark": "#2B1C45"},
    "python": {"light": "#616161", "dark": "#BDBDBD", "background_light": "#F3F3F3", "background_dark": "#252525"},
}
_UI_LEVEL_COLORS = {
    "warning": {"light": "#986F0B", "dark": "#FACC15", "background_light": "#FFF7D6", "background_dark": "#3A2B08"},
    "error": {"light": "#C42B1C", "dark": "#FF8A80", "background_light": "#FDECEA", "background_dark": "#4A1712"},
    "critical": {"light": "#A80000", "dark": "#FFFFFF", "background_light": "#F9D8D6", "background_dark": "#7A0000"},
}


@dataclass(frozen=True)
class SmartLogRecord:
    timestamp: str
    level: str
    domain: str
    message: str
    source: str
    case_nodeid: str
    step_id: str
    extra: dict[str, Any]

    @property
    def line(self) -> str:
        prefix = f"[{self.domain}]"
        if self.source:
            prefix += f"[{self.source}]"
        return f"{prefix} {self.message}"

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["line"] = self.line
        row.update(log_display_fields(domain=self.domain, level=self.level))
        return row

    def to_static_payload(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "domain": self.domain,
            "source": self.source,
            "case_nodeid": self.case_nodeid,
            "step_id": self.step_id,
            "message": self.message,
            "extra": self.extra,
        }

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "type": "log",
            "timestamp": time.time(),
            "level": self.level,
            "domain": self.domain,
            "source": self.source,
            "case_nodeid": self.case_nodeid,
            "step_id": self.step_id,
            "message": self.message,
            "line": self.line,
            "extra": self.extra,
            **log_display_fields(domain=self.domain, level=self.level),
        }


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_level(level: str | None) -> str:
    normalized = _safe_text(level).lower()
    if normalized in {"debug", "info", "warning", "error", "critical"}:
        return normalized
    if normalized == "warn":
        return "warning"
    return "info"


def _normalize_domain(domain: str | None) -> str:
    normalized = _safe_text(domain).lower()
    return normalized or "framework"


def _infer_source_and_domain() -> tuple[str, str]:
    frame = sys._getframe(2)
    module_name = str(frame.f_globals.get("__name__", "") or "")
    if module_name.startswith("ui."):
        return module_name, "ui"
    if module_name.startswith("testing.runner"):
        return module_name, "runner"
    if module_name.startswith("testing.runtime") or module_name.startswith("testing.tests"):
        return module_name, "test"
    if module_name.startswith("android_client"):
        return module_name, "android"
    if module_name.startswith("testing.tool.relay") or module_name.startswith("testing.tool.wifi_lab"):
        return module_name, "equipment"
    if module_name.startswith("testing.tool"):
        return module_name, "dut"
    return module_name, "framework"


def _format_message(message: Any, args: tuple[Any, ...]) -> str:
    text = str(message)
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        rendered_args = " ".join(str(arg) for arg in args)
        return f"{text} {rendered_args}".rstrip()


def default_log_dir() -> Path:
    configured = _safe_text(os.environ.get(SMARTTEST_LOG_DIR_ENV))
    if configured:
        return Path(configured)
    local_app_data = _safe_text(os.environ.get("LOCALAPPDATA"))
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


def log_display_fields(*, domain: str | None, level: str | None) -> dict[str, str]:
    normalized_domain = _normalize_domain(domain)
    normalized_level = _normalize_level(level)
    domain_colors = _UI_DOMAIN_COLORS.get(normalized_domain, _UI_DOMAIN_COLORS["framework"])
    level_colors = _UI_LEVEL_COLORS.get(normalized_level, {})
    return {
        "accent_color_light": domain_colors["light"],
        "accent_color_dark": domain_colors["dark"],
        "text_color_light": level_colors.get("light", domain_colors["light"]),
        "text_color_dark": level_colors.get("dark", domain_colors["dark"]),
        "background_color_light": level_colors.get("background_light", domain_colors["background_light"]),
        "background_color_dark": level_colors.get("background_dark", domain_colors["background_dark"]),
    }


def ensure_log_display_fields(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized.update(log_display_fields(domain=normalized.get("domain"), level=normalized.get("level")))
    return normalized


def build_log_record(
    message: Any,
    *,
    domain: str = "framework",
    level: str = "info",
    source: str | None = None,
    case_nodeid: str | None = None,
    step_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> SmartLogRecord:
    return SmartLogRecord(
        timestamp=_now_iso(),
        level=_normalize_level(level),
        domain=_normalize_domain(domain),
        message=str(message),
        source=_safe_text(source),
        case_nodeid=_safe_text(case_nodeid),
        step_id=_safe_text(step_id),
        extra=dict(extra or {}),
    )


def write_static_log(record: SmartLogRecord, *, path: Path | None = None) -> Path:
    target = path or default_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record.to_static_payload(), ensure_ascii=False, sort_keys=True)
    with _FILE_LOCK:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(encoded)
            fh.write("\n")
        readable_path = target.with_name(SMARTTEST_READABLE_LOG_FILE_NAME) if path else default_readable_log_path()
        with readable_path.open("a", encoding="utf-8") as fh:
            fh.write(_console_line(record, color_enabled=False))
            fh.write("\n")
    return target


def _write_event(record: SmartLogRecord) -> None:
    raw_path = _safe_text(os.environ.get(SMARTTEST_STEP_EVENTS_OUT_ENV))
    if not raw_path:
        return
    event_path = Path(raw_path)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record.to_event_payload(), ensure_ascii=False) + "\n"
    with _EVENT_LOCK:
        with event_path.open("a", encoding="utf-8") as fh:
            fh.write(encoded)


def _console_color_enabled() -> bool:
    mode = _safe_text(os.environ.get(SMARTTEST_LOG_COLOR_ENV)).lower()
    if mode in {"0", "false", "no", "off", "never"}:
        return False
    if mode in {"1", "true", "yes", "on", "always"}:
        return True
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def _color(text: str, color: str) -> str:
    if not color:
        return text
    return f"{color}{text}{_RESET}"


def _console_line(record: SmartLogRecord, *, color_enabled: bool) -> str:
    timestamp = record.timestamp
    level = record.level.upper()
    domain = record.domain
    source = record.source
    if color_enabled:
        domain = _color(domain, _DOMAIN_COLORS.get(record.domain, ""))
        level = _color(level, _LEVEL_COLORS.get(record.level, ""))
    return f"{timestamp} [{domain}] [{level}] [{source}] {record.message}"


def _write_console(record: SmartLogRecord) -> None:
    if _safe_text(os.environ.get(SMARTTEST_STEP_EVENTS_OUT_ENV)):
        return
    stdout = getattr(sys, "stdout", None)
    if stdout is None or not hasattr(stdout, "write"):
        return
    line = _console_line(record, color_enabled=_console_color_enabled())
    with _CONSOLE_LOCK:
        stdout.write(line)
        stdout.write("\n")
        stdout.flush()


def smart_log(
    message: Any,
    *args: Any,
    domain: str | None = None,
    level: str = "info",
    source: str | None = None,
    case_nodeid: str | None = None,
    step_id: str | None = None,
    extra: dict[str, Any] | None = None,
    emit_runtime_event: bool = True,
    static_path: Path | None = None,
    exc_info: Any = False,
) -> SmartLogRecord:
    inferred_source, inferred_domain = _infer_source_and_domain()
    merged_extra = dict(extra or {})
    if exc_info:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type is not None:
            import traceback

            merged_extra["traceback"] = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    record = build_log_record(
        _format_message(message, args),
        domain=domain or inferred_domain,
        level=level,
        source=source or inferred_source,
        case_nodeid=case_nodeid,
        step_id=step_id,
        extra=merged_extra,
    )
    write_static_log(record, path=static_path)
    if emit_runtime_event:
        _write_event(record)
    _write_console(record)
    return record
