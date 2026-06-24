from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from tools.report import duration_text, export_pdf_report, list_reports, report_html_url, report_json_path

try:
    from example.helper.AppPaths import app_data_dir
except ImportError:  # pragma: no cover - direct unit-test imports may use the ui.example package path
    from ui.example.helper.AppPaths import app_data_dir


class ReportBridge(QObject):
    reportsChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self):
        super().__init__(QGuiApplication.instance())
        self._reports: list[dict[str, Any]] = []
        self.refresh()

    def _default_reports_dir(self) -> Path:
        return app_data_dir() / "reports"

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
            raw = {}
        return {key: int(raw.get(key, 0) or 0) for key in ("total", "passed", "failed", "skipped", "running")}

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
            "duration": duration_text(report.get("duration_ms", 0)),
            "duration_ms": int(report.get("duration_ms", 0) or 0),
            "adb_serial": str(report.get("adb_serial", "") or ""),
            **counts,
        }

    @Slot()
    def refresh(self) -> None:
        self._reports = list_reports(reports_dir=self._default_reports_dir())
        self.reportsChanged.emit()

    @Slot(result="QVariantList")
    def reportRows(self):
        return [self._summary_row(report) for report in self._reports]

    @Slot(str, result=str)
    def reportHtmlUrl(self, run_id: str) -> str:
        return report_html_url(run_id, reports_dir=self._default_reports_dir())

    @Slot(str, result=bool)
    def openReportFolder(self, run_id: str) -> bool:
        path = report_json_path(run_id, reports_dir=self._default_reports_dir())
        if not path.exists():
            self.errorOccurred.emit(f"Report file not found: {path}")
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    @Slot(str, result=bool)
    def exportPdf(self, run_id: str) -> bool:
        try:
            pdf_path = export_pdf_report(run_id, reports_dir=self._default_reports_dir())
        except Exception as exc:  # noqa: BLE001
            self.errorOccurred.emit(f"Failed to export PDF: {exc}")
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf_path)))
