from pathlib import Path

from .core import _safe_filename, report_file_stem
from .json import load_report


def _report_export_path(run_id: str, *, reports_dir: Path, suffix: str) -> Path:
    report = load_report(run_id, reports_dir=reports_dir)
    stem = report_file_stem(report) if report else _safe_filename(run_id)
    return reports_dir / f"{stem}.{suffix}"


def report_html_path(run_id: str, *, reports_dir: Path) -> Path:
    return _report_export_path(run_id, reports_dir=reports_dir, suffix="html")


def report_pdf_path(run_id: str, *, reports_dir: Path) -> Path:
    return _report_export_path(run_id, reports_dir=reports_dir, suffix="pdf")
