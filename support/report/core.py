from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import uuid4


REPORT_SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_filename(value: Any) -> str:
    text = _safe_text(value)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text or "report"


def _timestamp_for_filename(value: Any) -> str:
    raw = _safe_text(value)
    if not raw:
        return datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return _safe_filename(raw.replace("T", "_")[:19].replace(":", "-"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d_%H-%M-%S")


def report_file_stem(report: dict[str, Any]) -> str:
    timestamp = _timestamp_for_filename(
        report.get("finished_at") or report.get("started_at")
    )
    status = _safe_filename(report.get("status") or "unknown")
    run_id = _safe_filename(report.get("run_id"))
    suffix = f"_{run_id[:12]}" if run_id else ""
    return f"SmartTest_{timestamp}_{status}{suffix}"


def build_run_report(**model: Any) -> dict[str, Any]:
    report = dict(model)
    report["schema_version"] = int(
        report.get("schema_version") or REPORT_SCHEMA_VERSION
    )
    report["run_id"] = _safe_text(report.get("run_id")) or uuid4().hex
    report["finished_at"] = _safe_text(report.get("finished_at")) or _now_iso()
    report["started_at"] = _safe_text(report.get("started_at"))
    report["duration_ms"] = max(0, _safe_int(report.get("duration_ms")))
    report["returncode"] = int(report.get("returncode") or 0)
    report["stopped"] = bool(report.get("stopped"))
    report["status"] = _safe_text(report.get("status")) or _status_from_summary(report)
    report["title"] = _safe_text(report.get("title")) or (
        f"{report['finished_at'].replace('T', ' ')[:19]}  {report['status']}"
    )
    report["adb_serial"] = _safe_text(report.get("adb_serial"))
    report["kind"] = _safe_text(report.get("kind")) or "run"
    report["dut_results"] = _normalized_dut_results(report)
    report["selected_nodeids"] = list(report.get("selected_nodeids") or [])
    report["summary"] = _dict_value(report.get("summary") or report.get("counts"))
    report["counts"] = dict(report["summary"])
    report["cases"] = _list_value(report.get("cases"))
    report["steps"] = _list_value(report.get("steps"))
    report["logs"] = _list_value(report.get("logs"))
    report["failure_analysis"] = _dict_value(report.get("failure_analysis"))
    report["duration_ranking"] = _list_value(report.get("duration_ranking"))
    report["log_distribution"] = _dict_value(report.get("log_distribution"))
    return report


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _normalized_dut_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _list_value(report.get("dut_results"))
    if raw:
        return [_dict_value(item) for item in raw if isinstance(item, dict)]
    summary = _dict_value(report.get("summary") or report.get("counts"))
    return [{
        "dut_serial": _safe_text(report.get("adb_serial")) or "No DUT",
        "run_id": report.get("run_id"),
        "status": report.get("status"),
        "returncode": report.get("returncode"),
        "duration_ms": report.get("duration_ms"),
        "counts": summary,
    }]


def _status_from_summary(report: dict[str, Any]) -> str:
    summary = _dict_value(report.get("summary") or report.get("counts"))
    if report.get("stopped"):
        return "stopped"
    if _safe_int(summary.get("failed")) > 0 or int(report.get("returncode") or 0) != 0:
        return "failed"
    if _safe_int(summary.get("total")) == 0:
        return "empty"
    return "passed"


def duration_text(duration_ms: Any) -> str:
    total_seconds = max(0, _safe_int(duration_ms) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
