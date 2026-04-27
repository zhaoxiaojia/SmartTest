from __future__ import annotations

import json
from json import JSONDecodeError
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


REPORT_SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _status_counts(steps: list[dict[str, Any]]) -> dict[str, int]:
    cases = [row for row in steps if row.get("kind") == "case"]
    return {
        "total": len(cases),
        "passed": sum(1 for row in cases if row.get("status") == "passed"),
        "failed": sum(1 for row in cases if row.get("status") == "failed"),
        "skipped": sum(1 for row in cases if row.get("status") == "skipped"),
        "running": sum(1 for row in cases if row.get("status") == "running"),
    }


def _overall_status(*, returncode: int, stopped: bool, counts: dict[str, int]) -> str:
    if stopped:
        return "stopped"
    if counts.get("failed", 0) > 0 or returncode != 0:
        return "failed"
    if counts.get("total", 0) == 0:
        return "empty"
    return "passed"


def build_run_report(
    *,
    run_id: str | None,
    started_at: str,
    finished_at: str | None,
    duration_ms: int,
    returncode: int,
    stopped: bool,
    adb_serial: str | None,
    selected_nodeids: list[str],
    steps: list[dict[str, Any]],
    logs: list[dict[str, Any]],
) -> dict[str, Any]:
    report_id = _safe_text(run_id) or uuid4().hex
    finished = _safe_text(finished_at) or _now_iso()
    normalized_steps = [dict(row) for row in steps]
    normalized_logs = [dict(row) for row in logs]
    counts = _status_counts(normalized_steps)
    status = _overall_status(returncode=returncode, stopped=stopped, counts=counts)
    title = f"{finished.replace('T', ' ')[:19]}  {status}"

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": report_id,
        "title": title,
        "started_at": started_at,
        "finished_at": finished,
        "duration_ms": max(0, int(duration_ms)),
        "returncode": int(returncode),
        "stopped": bool(stopped),
        "status": status,
        "adb_serial": _safe_text(adb_serial),
        "selected_nodeids": list(selected_nodeids),
        "counts": counts,
        "steps": normalized_steps,
        "logs": normalized_logs,
    }


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
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        path = self._reports_dir / f"{run_id}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
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
        return self.load_by_path(self._reports_dir / f"{normalized}.json")

    def load_by_path(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data
