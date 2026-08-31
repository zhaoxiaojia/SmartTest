from pathlib import Path

from ..core import _safe_text
from ..html import generate_html_report
from ..json import load_report, report_json_path
from ..paths import report_html_path, report_pdf_path
from .renderer import render_html_to_pdf


def export_pdf_report(
    run_id: str,
    *,
    reports_dir: Path,
    output_path: Path | None = None,
) -> Path:
    from PySide6.QtCore import QUrl

    normalized_run_id = _safe_text(run_id)
    if not normalized_run_id:
        raise ValueError("run_id is required")
    html_path = report_html_path(normalized_run_id, reports_dir=reports_dir)
    if not html_path.exists():
        report = load_report(normalized_run_id, reports_dir=reports_dir)
        if not report:
            raise FileNotFoundError(
                f"Report not found: {report_json_path(normalized_run_id, reports_dir=reports_dir)}"
            )
        generate_html_report(report, html_path=html_path)
    pdf_path = output_path or report_pdf_path(
        normalized_run_id, reports_dir=reports_dir
    )
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    render_html_to_pdf(
        html_path.read_text(encoding="utf-8"),
        pdf_path,
        base_url=QUrl.fromLocalFile(str(html_path.resolve())),
    )
    return pdf_path
