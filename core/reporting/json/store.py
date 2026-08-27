from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from core.config import jsonTool

from ..core import _safe_text


class ReportStore:
    def __init__(self, reports_dir: Path):
        self._reports_dir = reports_dir

    @property
    def reports_dir(self) -> Path:
        return self._reports_dir

    def save(self, report: dict[str, Any]) -> Path:
        run_id = _safe_text(report.get("run_id")) or uuid4().hex
        report = dict(report)
        report["run_id"] = run_id
        path = self._reports_dir / f"{run_id}.json"
        jsonTool.write_json(path, report)
        return path

    def list_reports(self) -> list[dict[str, Any]]:
        if not self._reports_dir.exists():
            return []
        reports = [
            report
            for path in self._reports_dir.glob("*.json")
            if (report := self.load_by_path(path))
        ]
        reports.sort(key=lambda item: _safe_text(item.get("finished_at")), reverse=True)
        return reports

    def load(self, run_id: str) -> dict[str, Any] | None:
        normalized = _safe_text(run_id)
        return self.load_by_path(self.path_for(normalized)) if normalized else None

    def path_for(self, run_id: str) -> Path:
        return self._reports_dir / f"{_safe_text(run_id)}.json"

    def load_by_path(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            data = jsonTool.read_json(path, {})
        except ValueError:
            return None
        return data if isinstance(data, dict) else None


def list_reports(*, reports_dir: Path) -> list[dict[str, Any]]:
    return ReportStore(reports_dir).list_reports()


def load_report(run_id: str, *, reports_dir: Path) -> dict[str, Any] | None:
    return ReportStore(reports_dir).load(run_id)


def report_json_path(run_id: str, *, reports_dir: Path) -> Path:
    return ReportStore(reports_dir).path_for(run_id)
