from __future__ import annotations

import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

PLATFORMS = frozenset({"client", "tool", "web", "runner", "mobile"})

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


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_level(level: str | None) -> str:
    normalized = safe_text(level).lower()
    if normalized == "warn":
        return "warning"
    if normalized in {"debug", "info", "warning", "error", "critical"}:
        return normalized
    return "info"


def normalize_domain(domain: str | None) -> str:
    return safe_text(domain).lower() or "framework"


def normalize_platform(platform: str | None) -> str:
    value = safe_text(platform).lower()
    if value not in PLATFORMS:
        raise ValueError(f"Unsupported SmartTest logging platform: {platform!r}")
    return value


def log_display_fields(*, domain: str | None, level: str | None) -> dict[str, str]:
    domain_colors = _UI_DOMAIN_COLORS.get(
        normalize_domain(domain), _UI_DOMAIN_COLORS["framework"]
    )
    level_colors = _UI_LEVEL_COLORS.get(normalize_level(level), {})
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
    normalized.update(
        log_display_fields(domain=normalized.get("domain"), level=normalized.get("level"))
    )
    return normalized


@dataclass(frozen=True)
class SmartLogRecord:
    timestamp: str
    platform: str
    level: str
    domain: str
    message: str
    source: str
    request_id: str
    case_nodeid: str
    step_id: str
    extra: dict[str, Any]

    @property
    def line(self) -> str:
        return f"[{self.platform}][{self.domain}][{self.source}] {self.message}"

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["line"] = self.line
        row.update(log_display_fields(domain=self.domain, level=self.level))
        return row

    def to_static_payload(self) -> dict[str, Any]:
        return asdict(self)

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "type": "log",
            **asdict(self),
            "timestamp": time.time(),
            "line": self.line,
            **log_display_fields(domain=self.domain, level=self.level),
        }


def infer_source_and_domain() -> tuple[str, str]:
    module = str(sys._getframe(2).f_globals.get("__name__", "") or "")
    if module.startswith("client.app.ui."):
        return module, "ui"
    if module.startswith("web.backend") or module.startswith("smarttest_web"):
        return module, "web"
    if module.startswith("core.testing.runner"):
        return module, "runner"
    if module.startswith(("core.testing.runtime", "core.testing.tests")):
        return module, "test"
    if module.startswith("mobile.android"):
        return module, "android"
    if module.startswith(("core.testing.tool.relay", "core.testing.tool.wifi_lab")):
        return module, "equipment"
    if module.startswith("core.testing.tool"):
        return module, "dut"
    return module, "framework"


def build_log_record(
    message: Any,
    *,
    platform: str,
    domain: str = "framework",
    level: str = "info",
    source: str | None = None,
    request_id: str | None = None,
    case_nodeid: str | None = None,
    step_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> SmartLogRecord:
    return SmartLogRecord(
        timestamp=datetime.now().astimezone().isoformat(timespec="milliseconds"),
        platform=normalize_platform(platform),
        level=normalize_level(level),
        domain=normalize_domain(domain),
        message=str(message),
        source=safe_text(source),
        request_id=safe_text(request_id),
        case_nodeid=safe_text(case_nodeid),
        step_id=safe_text(step_id),
        extra=dict(extra or {}),
    )
