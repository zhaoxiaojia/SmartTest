from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ui import jsonTool


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


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
        reports: list[dict[str, Any]] = []
        for path in self._reports_dir.glob("*.json"):
            report = self.load_by_path(path)
            if report:
                reports.append(report)
        reports.sort(key=lambda item: _safe_text(item.get("finished_at")), reverse=True)
        return reports

    def load(self, run_id: str) -> dict[str, Any] | None:
        normalized = _safe_text(run_id)
        if not normalized:
            return None
        return self.load_by_path(self.path_for(normalized))

    def path_for(self, run_id: str) -> Path:
        return self._reports_dir / f"{_safe_text(run_id)}.json"

    def load_by_path(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            data = jsonTool.read_json(path, {})
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        return data
