from __future__ import annotations

from pathlib import Path

from support.report import (
    build_run_report,
    export_pdf_report,
    report_file_stem,
    report_html_path,
    report_html_url,
    report_pdf_path,
    render_html_report,
    save_run_report,
)


def _report_model() -> dict:
    return {
        "schema_version": 1,
        "run_id": "run-1",
        "title": "2026-06-24 10:00:03  failed",
        "started_at": "2026-06-24T10:00:00+08:00",
        "finished_at": "2026-06-24T10:00:03+08:00",
        "duration_ms": 3000,
        "returncode": 1,
        "stopped": False,
        "status": "failed",
        "adb_serial": "dut-1",
        "selected_nodeids": ["case::demo"],
        "summary": {"total": 1, "passed": 0, "failed": 1, "skipped": 0, "running": 0},
        "counts": {"total": 1, "passed": 0, "failed": 1, "skipped": 0, "running": 0},
        "duration_ranking": [{"title": "Demo case", "case_nodeid": "case::demo", "duration_ms": 3000}],
        "log_distribution": {"levels": {"error": 1}, "domains": {"test": 1}},
        "failure_analysis": {
            "status": "failed",
            "primary_failure": {
                "title": "Demo step",
                "case_nodeid": "case::demo",
                "error": "expected ok",
                "evidence_logs": [{"line": "failed detail", "level": "error", "domain": "test"}],
            },
            "failed_cases": [{"case_nodeid": "case::demo", "title": "Demo case"}],
        },
        "cases": [
            {
                "case": {
                    "id": "case:case::demo",
                    "kind": "case",
                    "title": "Demo case",
                    "status": "failed",
                    "duration_ms": 3000,
                    "case_nodeid": "case::demo",
                    "definition_id": "demo.case",
                    "error": {"message": "expected ok"},
                },
                "case_summary": {"headline": "Demo failed"},
                "loop_summary": {"observed": 3, "total": 3, "actions": {"demo.step": {"failed": 1}}},
                "steps": [
                    {
                        "id": "step-1",
                        "kind": "check",
                        "case_nodeid": "case::demo",
                        "title": "Demo step",
                        "status": "failed",
                        "definition_id": "demo.step",
                        "error": "expected ok",
                    }
                ],
                "logs": [{"line": "failed detail", "message": "failed detail", "level": "error", "domain": "test"}],
                "key_logs": [{"line": "failed detail", "message": "failed detail", "level": "error", "domain": "test"}],
                "artifacts": [{"title": "Raw result", "path": "result.json"}],
            }
        ],
        "steps": [],
        "logs": [],
    }


def test_build_run_report_accepts_complete_display_model():
    report = build_run_report(**_report_model())

    assert report["summary"]["failed"] == 1
    assert report["cases"][0]["loop_summary"]["observed"] == 3
    assert report["failure_analysis"]["primary_failure"]["title"] == "Demo step"


def test_save_run_report_writes_json_and_html(tmp_path):
    report = build_run_report(**_report_model())

    json_path = save_run_report(report, reports_dir=tmp_path)
    html_path = report_html_path("run-1", reports_dir=tmp_path)

    assert json_path == tmp_path / "run-1.json"
    assert report_file_stem(report) == "SmartTest_2026-06-24_10-00-03_failed_run-1"
    assert html_path == tmp_path / "SmartTest_2026-06-24_10-00-03_failed_run-1.html"
    assert json_path.exists()
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "SmartTest Report" in html
    assert "Demo case" in html
    assert "failed detail" in html
    assert "expected ok" in html
    assert "Demo failed" in html
    assert "Raw result" in html
    assert report_html_url("run-1", reports_dir=tmp_path).startswith("file:///")


def test_render_html_uses_model_without_rebuilding_business_meaning():
    html = render_html_report(_report_model())

    assert html.index("Cases In This Run") < html.index("Case Reports")
    assert "Failure Analysis" in html
    assert "Loop Summary" in html
    assert "demo.step</td><td>failed 1" in html
    assert "Case Logs (1)" in html
    assert "Log Distribution" in html
    assert "Case Duration" in html


def test_report_source_has_no_case_specific_or_log_inference_logic():
    source = Path("support/report.py").read_text(encoding="utf-8").lower()

    forbidden = [
        "emmc",
        "copy_err",
        "_infer_loop_summary",
        "_repeat_position",
        "case_logs(",
        "logs_for_step(",
        "classify_failure",
    ]
    assert [token for token in forbidden if token in source] == []


def test_export_pdf_report_regenerates_html_and_uses_default_pdf_path(tmp_path, monkeypatch):
    report = build_run_report(
        **{
            **_report_model(),
            "run_id": "run-pdf",
            "status": "failed",
            "finished_at": "2026-06-24T10:00:01+08:00",
        }
    )
    save_run_report(report, reports_dir=tmp_path)
    report_html_path("run-pdf", reports_dir=tmp_path).unlink()
    calls = []

    def fake_renderer(html_path, pdf_path):
        calls.append((html_path, pdf_path))
        pdf_path.write_bytes(b"%PDF-1.4\n% fake\n")

    monkeypatch.setattr("support.report._render_html_to_pdf", fake_renderer)

    pdf_path = export_pdf_report("run-pdf", reports_dir=tmp_path)

    expected_html_path = tmp_path / "SmartTest_2026-06-24_10-00-01_failed_run-pdf.html"
    expected_pdf_path = tmp_path / "SmartTest_2026-06-24_10-00-01_failed_run-pdf.pdf"

    assert pdf_path == expected_pdf_path
    assert pdf_path.exists()
    assert report_pdf_path("run-pdf", reports_dir=tmp_path) == expected_pdf_path
    assert report_html_path("run-pdf", reports_dir=tmp_path).exists()
    assert calls == [(expected_html_path, expected_pdf_path)]
