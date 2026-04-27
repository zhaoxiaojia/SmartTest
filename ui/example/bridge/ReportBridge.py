from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QStandardPaths, Signal, Slot
from PySide6.QtGui import QGuiApplication

from testing.reporting import ReportStore


class ReportBridge(QObject):
    reportsChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        self._store = ReportStore(self._default_reports_dir())
        self._reports: list[dict[str, Any]] = []
        self.refresh()

    def _default_reports_dir(self) -> Path:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        return Path(base) / "SmartTest" / "reports"

    def _format_duration(self, duration_ms: Any) -> str:
        total_seconds = max(0, int(duration_ms or 0) // 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _format_timestamp(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return raw.replace("T", " ")[:19]
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _counts(self, report: dict[str, Any]) -> dict[str, int]:
        raw = report.get("counts", {})
        if not isinstance(raw, dict):
            return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "running": 0}
        return {
            "total": int(raw.get("total", 0) or 0),
            "passed": int(raw.get("passed", 0) or 0),
            "failed": int(raw.get("failed", 0) or 0),
            "skipped": int(raw.get("skipped", 0) or 0),
            "running": int(raw.get("running", 0) or 0),
        }

    def _summary_row(self, report: dict[str, Any]) -> dict[str, Any]:
        counts = self._counts(report)
        return {
            "run_id": str(report.get("run_id", "") or ""),
            "title": str(report.get("title", "") or ""),
            "status": str(report.get("status", "") or ""),
            "started_at": self._format_timestamp(report.get("started_at", "")),
            "finished_at": self._format_timestamp(report.get("finished_at", "")),
            "started_at_raw": str(report.get("started_at", "") or ""),
            "finished_at_raw": str(report.get("finished_at", "") or ""),
            "duration": self._format_duration(report.get("duration_ms", 0)),
            "duration_ms": int(report.get("duration_ms", 0) or 0),
            "adb_serial": str(report.get("adb_serial", "") or ""),
            **counts,
        }

    def _detail_payload(self, report: dict[str, Any]) -> dict[str, Any]:
        counts = self._counts(report)
        steps = [dict(row) for row in report.get("steps", []) if isinstance(row, dict)]
        cases = [row for row in steps if row.get("kind") == "case"]
        logs = [dict(row) for row in report.get("logs", []) if isinstance(row, dict)]
        return {
            **self._summary_row(report),
            "returncode": int(report.get("returncode", 0) or 0),
            "stopped": bool(report.get("stopped", False)),
            "selected_nodeids": list(report.get("selected_nodeids", []) or []),
            "counts": counts,
            "cases": cases,
            "steps": steps,
            "logs": logs,
            "log_text": "\n".join(str(item.get("line", "")) for item in logs),
        }

    @Slot()
    def refresh(self) -> None:
        self._reports = self._store.list_reports()
        self.reportsChanged.emit()

    @Slot(result="QVariantList")
    def reportRows(self):
        return [self._summary_row(report) for report in self._reports]

    @Slot(str, result="QVariantMap")
    def reportDetail(self, run_id: str):
        report = self._store.load(run_id)
        if not report:
            return {}
        return self._detail_payload(report)
