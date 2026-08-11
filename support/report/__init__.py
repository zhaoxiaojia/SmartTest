from .core import REPORT_SCHEMA_VERSION, build_run_report, duration_text, report_file_stem
from .excel import write_xlsx_table
from .html import generate_html_report, render_html_report, report_html_url
from .json import list_reports, load_report, report_json_path
from .paths import report_html_path, report_pdf_path
from .pdf import export_pdf_report
from .pipeline import save_run_report

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "DEFAULT_LINE_CHART_STYLE",
    "LineChartStyle",
    "LineSeries",
    "build_run_report",
    "duration_text",
    "export_pdf_report",
    "generate_html_report",
    "list_reports",
    "load_report",
    "render_html_report",
    "report_file_stem",
    "report_html_path",
    "report_html_url",
    "report_json_path",
    "report_pdf_path",
    "render_line_chart",
    "render_html_page_image",
    "save_run_report",
    "write_xlsx_table",
]

_IMAGE_EXPORTS = {
    "DEFAULT_LINE_CHART_STYLE",
    "LineChartStyle",
    "LineSeries",
    "render_line_chart",
    "render_html_page_image",
}


def __getattr__(name: str):
    if name not in _IMAGE_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import image

    value = getattr(image, name)
    globals()[name] = value
    return value
