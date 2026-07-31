from pathlib import Path
from typing import Any

from .core import build_run_report
from .html import generate_html_report
from .json import ReportStore
from .paths import report_html_path


def save_run_report(report: dict[str, Any], *, reports_dir: Path) -> Path:
    normalized = build_run_report(**dict(report))
    json_path = ReportStore(reports_dir).save(normalized)
    generate_html_report(
        normalized,
        html_path=report_html_path(
            str(normalized.get("run_id", "")), reports_dir=reports_dir
        ),
    )
    return json_path
