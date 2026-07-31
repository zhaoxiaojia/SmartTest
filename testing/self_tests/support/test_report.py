from pathlib import Path

from openpyxl import load_workbook

from support.report import (
    build_run_report,
    duration_text,
    export_pdf_report,
    generate_html_report,
    list_reports,
    load_report,
    render_html_report,
    report_file_stem,
    report_html_path,
    report_html_url,
    report_json_path,
    report_pdf_path,
    save_run_report,
    write_xlsx_table,
)


def test_report_package_preserves_public_run_report_api():
    assert build_run_report(run_id="r1")["run_id"] == "r1"
    assert duration_text(61_000) == "1m 1s"
    assert all(callable(value) for value in (
        export_pdf_report, generate_html_report, list_reports, load_report,
        render_html_report, report_file_stem, report_html_path, report_html_url,
        report_json_path, report_pdf_path, save_run_report,
    ))
    assert Path(__import__("support.report", fromlist=["x"]).__path__[0]).name == "report"


def test_global_xlsx_owner_writes_filtered_frozen_wrapped_table(tmp_path):
    output = write_xlsx_table(
        tmp_path / "matrix.xlsx",
        sheet_name="Matrix",
        headers=("Name", "State", "URL"),
        rows=(("Project", "已更新", "https://c/project"),),
        hyperlinks={(2, 3): "https://c/project"},
    )
    sheet = load_workbook(output).active
    assert sheet.title == "Matrix"
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:C2"
    assert sheet["A1"].alignment.wrap_text is True
    assert sheet["C2"].hyperlink.target == "https://c/project"
