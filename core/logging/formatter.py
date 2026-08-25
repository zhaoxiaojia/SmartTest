from __future__ import annotations

from .record import SmartLogRecord

RESET = "\033[0m"
DOMAIN_COLORS = {
    "framework": "\033[36m",
    "ui": "\033[35m",
    "runner": "\033[34m",
    "test": "\033[32m",
    "dut": "\033[33m",
    "equipment": "\033[38;5;208m",
    "android": "\033[92m",
    "jira": "\033[95m",
    "python": "\033[37m",
    "web": "\033[36m",
}
LEVEL_COLORS = {
    "debug": "\033[90m",
    "info": "",
    "warning": "\033[93m",
    "error": "\033[91m",
    "critical": "\033[97;41m",
}


def _color(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if color else text


def readable_line(record: SmartLogRecord, *, color_enabled: bool = False) -> str:
    domain = record.domain
    level = record.level.upper()
    if color_enabled:
        domain = _color(domain, DOMAIN_COLORS.get(record.domain, ""))
        level = _color(level, LEVEL_COLORS.get(record.level, ""))
    return (
        f"{record.timestamp} [{record.platform}] [{domain}] "
        f"[{level}] [{record.source}] {record.message}"
    )
