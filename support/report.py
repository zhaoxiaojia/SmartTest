from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from testing.reporting.store import ReportStore


REPORT_SCHEMA_VERSION = 1

_STATUS_COLORS = {
    "passed": "#107c10",
    "failed": "#c42b1c",
    "skipped": "#6b7280",
    "running": "#2563eb",
    "stopped": "#8a6a00",
    "planned": "#8764b8",
    "empty": "#6b7280",
}
_DOMAIN_COLORS = {
    "framework": "#0f6cbd",
    "ui": "#8f12a6",
    "runner": "#2546b8",
    "test": "#107c10",
    "dut": "#986f0b",
    "equipment": "#c43501",
    "android": "#16833a",
    "jira": "#6b3fa0",
    "python": "#616161",
}
_LEVEL_COLORS = {
    "debug": "#616161",
    "info": "#111827",
    "warning": "#986f0b",
    "error": "#c42b1c",
    "critical": "#a80000",
}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_filename(value: Any) -> str:
    text = _safe_text(value)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text or "report"


def _timestamp_for_filename(value: Any) -> str:
    raw = _safe_text(value)
    if not raw:
        return datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return _safe_filename(raw.replace("T", "_")[:19].replace(":", "-"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d_%H-%M-%S")


def report_file_stem(report: dict[str, Any]) -> str:
    timestamp = _timestamp_for_filename(report.get("finished_at") or report.get("started_at"))
    status = _safe_filename(report.get("status") or "unknown")
    run_id = _safe_filename(report.get("run_id"))
    suffix = f"_{run_id[:12]}" if run_id else ""
    return f"SmartTest_{timestamp}_{status}{suffix}"


def build_run_report(**model: Any) -> dict[str, Any]:
    report = dict(model)
    report["schema_version"] = int(report.get("schema_version") or REPORT_SCHEMA_VERSION)
    report["run_id"] = _safe_text(report.get("run_id")) or uuid4().hex
    report["finished_at"] = _safe_text(report.get("finished_at")) or _now_iso()
    report["started_at"] = _safe_text(report.get("started_at"))
    report["duration_ms"] = max(0, _safe_int(report.get("duration_ms")))
    report["returncode"] = int(report.get("returncode") or 0)
    report["stopped"] = bool(report.get("stopped"))
    report["status"] = _safe_text(report.get("status")) or _status_from_summary(report)
    report["title"] = _safe_text(report.get("title")) or f"{report['finished_at'].replace('T', ' ')[:19]}  {report['status']}"
    report["adb_serial"] = _safe_text(report.get("adb_serial"))
    report["kind"] = _safe_text(report.get("kind")) or "run"
    report["dut_results"] = _normalized_dut_results(report)
    report["selected_nodeids"] = list(report.get("selected_nodeids") or [])
    report["summary"] = _dict_value(report.get("summary") or report.get("counts"))
    report["counts"] = dict(report["summary"])
    report["cases"] = _list_value(report.get("cases"))
    report["steps"] = _list_value(report.get("steps"))
    report["logs"] = _list_value(report.get("logs"))
    report["failure_analysis"] = _dict_value(report.get("failure_analysis"))
    report["duration_ranking"] = _list_value(report.get("duration_ranking"))
    report["log_distribution"] = _dict_value(report.get("log_distribution"))
    return report


def save_run_report(report: dict[str, Any], *, reports_dir: Path) -> Path:
    normalized = build_run_report(**dict(report))
    store = ReportStore(reports_dir)
    json_path = store.save(normalized)
    generate_html_report(normalized, html_path=report_html_path(str(normalized.get("run_id", "")), reports_dir=reports_dir))
    return json_path


def list_reports(*, reports_dir: Path) -> list[dict[str, Any]]:
    return ReportStore(reports_dir).list_reports()


def load_report(run_id: str, *, reports_dir: Path) -> dict[str, Any] | None:
    return ReportStore(reports_dir).load(run_id)


def report_json_path(run_id: str, *, reports_dir: Path) -> Path:
    return ReportStore(reports_dir).path_for(run_id)


def _report_export_path(run_id: str, *, reports_dir: Path, suffix: str) -> Path:
    report = load_report(run_id, reports_dir=reports_dir)
    stem = report_file_stem(report) if report else _safe_filename(run_id)
    return reports_dir / f"{stem}.{suffix}"


def report_html_path(run_id: str, *, reports_dir: Path) -> Path:
    return _report_export_path(run_id, reports_dir=reports_dir, suffix="html")


def report_pdf_path(run_id: str, *, reports_dir: Path) -> Path:
    return _report_export_path(run_id, reports_dir=reports_dir, suffix="pdf")


def report_html_url(run_id: str, *, reports_dir: Path) -> str:
    path = report_html_path(run_id, reports_dir=reports_dir)
    report = load_report(run_id, reports_dir=reports_dir)
    if report:
        generate_html_report(report, html_path=path)
    return path.resolve().as_uri()


def export_pdf_report(run_id: str, *, reports_dir: Path, output_path: Path | None = None) -> Path:
    normalized_run_id = _safe_text(run_id)
    if not normalized_run_id:
        raise ValueError("run_id is required")
    html_path = report_html_path(normalized_run_id, reports_dir=reports_dir)
    if not html_path.exists():
        report = load_report(normalized_run_id, reports_dir=reports_dir)
        if not report:
            raise FileNotFoundError(f"Report not found: {report_json_path(normalized_run_id, reports_dir=reports_dir)}")
        generate_html_report(report, html_path=html_path)
    pdf_path = output_path or report_pdf_path(normalized_run_id, reports_dir=reports_dir)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    _render_html_to_pdf(html_path, pdf_path)
    return pdf_path


def _render_html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    try:
        _render_html_to_pdf_with_qt(html_path, pdf_path)
    except ImportError as exc:
        raise RuntimeError("PDF export requires PySide6 QtWebEngine in the SmartTest runtime.") from exc


def _render_html_to_pdf_with_qt(html_path: Path, pdf_path: Path) -> None:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineQuick import QtWebEngineQuick

    app = QGuiApplication.instance()
    owns_app = app is None
    if owns_app:
        QtWebEngineQuick.initialize()
        app = QGuiApplication([])

    page = QWebEnginePage()
    loop = QEventLoop()
    result: dict[str, Any] = {"ok": False, "error": ""}

    def finish(ok: bool, error: str = "") -> None:
        result["ok"] = ok
        result["error"] = error
        if loop.isRunning():
            loop.quit()

    def on_pdf_finished(path: str, success: bool) -> None:
        finish(bool(success), "" if success else f"Qt failed to write PDF: {path}")

    def on_load_finished(success: bool) -> None:
        if not success:
            finish(False, f"Failed to load report HTML: {html_path}")
            return
        page.pdfPrintingFinished.connect(on_pdf_finished)
        page.printToPdf(str(pdf_path))

    page.loadFinished.connect(on_load_finished)
    QTimer.singleShot(30000, lambda: finish(False, f"Timed out exporting PDF: {html_path}"))
    page.load(QUrl.fromLocalFile(str(html_path.resolve())))
    loop.exec()
    page.deleteLater()
    if owns_app:
        app.quit()
    if not result["ok"]:
        raise RuntimeError(str(result["error"] or "Failed to export PDF"))


def generate_html_report(report: dict[str, Any], *, html_path: Path) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html_report(report), encoding="utf-8")
    return html_path


def render_html_report(report: dict[str, Any]) -> str:
    model = build_run_report(**dict(report))
    status = _safe_text(model.get("status")) or "empty"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(model.get("title") or "SmartTest Report")}</title>
<style>{_report_css()}</style>
</head>
<body>
<main>
  <header class="hero">
    <div>
      <p class="eyebrow">SmartTest DUT Report</p>
      <h1>{_esc(model.get("title") or model.get("run_id") or "Run Report")}</h1>
      <p class="meta">{_esc(model.get("started_at"))} - {_esc(model.get("finished_at"))}</p>
    </div>
    <span class="status" style="--status:{_status_color(status)}">{_esc(status)}</span>
  </header>
  {_summary_html(model)}
  {_section_html("DUT Overview", _dut_overview_html(model))}
  {_section_html("Failure Analysis", _failure_analysis_html(_dict_value(model.get("failure_analysis"))))}
  <section class="grid three">
    <article><h2>Result Chart</h2>{_chart_html(_dict_value(model.get("summary")))}</article>
    <article><h2>Case Duration</h2>{_duration_ranking_html(_list_value(model.get("duration_ranking")))}</article>
    <article><h2>Log Distribution</h2>{_log_distribution_html(_dict_value(model.get("log_distribution")))}</article>
  </section>
  {_section_html("DUT Details", _dut_details_html(model))}
</main>
</body>
</html>
"""


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _normalized_dut_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _list_value(report.get("dut_results"))
    if raw:
        return [_dict_value(item) for item in raw if isinstance(item, dict)]
    summary = _dict_value(report.get("summary") or report.get("counts"))
    return [{
        "dut_serial": _safe_text(report.get("adb_serial")) or "No DUT",
        "run_id": report.get("run_id"),
        "status": report.get("status"),
        "returncode": report.get("returncode"),
        "duration_ms": report.get("duration_ms"),
        "counts": summary,
    }]


def _status_from_summary(report: dict[str, Any]) -> str:
    summary = _dict_value(report.get("summary") or report.get("counts"))
    if report.get("stopped"):
        return "stopped"
    if _safe_int(summary.get("failed")) > 0 or int(report.get("returncode") or 0) != 0:
        return "failed"
    if _safe_int(summary.get("total")) == 0:
        return "empty"
    return "passed"


def _esc(value: Any) -> str:
    return html.escape(_safe_text(value), quote=True)


def _anchor_id(value: Any) -> str:
    text = _safe_text(value)
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    return normalized or "case"


def _status_color(status: str) -> str:
    return _STATUS_COLORS.get(status, "#6b7280")


def _section_html(title: str, body: str) -> str:
    return f"<section><h2>{_esc(title)}</h2>{body}</section>"


def duration_text(duration_ms: Any) -> str:
    total_seconds = max(0, _safe_int(duration_ms) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _summary_html(report: dict[str, Any]) -> str:
    summary = _dict_value(report.get("summary") or report.get("counts"))
    items = [
        ("DUTs", len(_list_value(report.get("dut_results")))),
        ("Total", summary.get("total", 0)),
        ("Passed", summary.get("passed", 0)),
        ("Failed", summary.get("failed", 0)),
        ("Duration", duration_text(report.get("duration_ms"))),
    ]
    cards = "".join(f"<article><span>{_esc(label)}</span><strong>{html.escape(str(value), quote=True)}</strong></article>" for label, value in items)
    return f'<section class="summary">{cards}</section>'


def _dut_overview_html(report: dict[str, Any]) -> str:
    rows = []
    for raw in _list_value(report.get("dut_results")):
        row = _dict_value(raw)
        counts = _dict_value(row.get("counts"))
        status = _safe_text(row.get("status")) or "-"
        rows.append(
            "<tr>"
            f"<td>{_esc(row.get('dut_serial') or 'No DUT')}</td>"
            f"<td><span class=\"status\" style=\"--status:{_status_color(status)}\">{_esc(status)}</span></td>"
            f"<td>{html.escape(str(counts.get('total', 0)), quote=True)}</td>"
            f"<td>{html.escape(str(counts.get('passed', 0)), quote=True)}</td>"
            f"<td>{html.escape(str(counts.get('failed', 0)), quote=True)}</td>"
            f"<td>{duration_text(row.get('duration_ms'))}</td>"
            f"<td>{_esc(row.get('run_id'))}</td>"
            "</tr>"
        )
    if not rows:
        return '<p class="empty">No DUT results.</p>'
    return (
        "<table><thead><tr><th>DUT</th><th>Status</th><th>Total</th><th>Passed</th>"
        "<th>Failed</th><th>Duration</th><th>Run ID</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _dut_details_html(report: dict[str, Any]) -> str:
    dut_results = _list_value(report.get("dut_results"))
    if not dut_results:
        return '<p class="empty">No DUT details.</p>'
    details = []
    all_cases = _list_value(report.get("cases"))
    all_logs = _list_value(report.get("logs"))
    for index, raw in enumerate(dut_results):
        row = _dict_value(raw)
        serial = _safe_text(row.get("dut_serial")) or "No DUT"
        counts = _dict_value(row.get("counts"))
        summary = (
            f"{serial} | {_safe_text(row.get('status')) or '-'} | "
            f"total {counts.get('total', 0)} passed {counts.get('passed', 0)} failed {counts.get('failed', 0)}"
        )
        body = _kv_html([
            ("DUT", serial),
            ("Run ID", row.get("run_id")),
            ("Status", row.get("status")),
            ("Return Code", row.get("returncode")),
            ("Duration", duration_text(row.get("duration_ms"))),
            ("Total", counts.get("total", 0)),
            ("Passed", counts.get("passed", 0)),
            ("Failed", counts.get("failed", 0)),
        ])
        if len(dut_results) == 1 and all_cases:
            body += _section_inline_html("Cases", _cases_overview_html(all_cases))
            body += _section_inline_html("Case Reports", _case_reports_html(all_cases))
        if len(dut_results) == 1 and all_logs:
            body += _details_html(f"Logs ({len(all_logs)})", _logs_html(all_logs))
        details.append(_details_html(summary, body, " open" if index == 0 else ""))
    return "".join(details)


def _section_inline_html(title: str, body: str) -> str:
    return f'<div class="inline-section"><h3>{_esc(title)}</h3>{body}</div>'


def _cases_overview_html(cases: list[Any]) -> str:
    if not cases:
        return '<p class="empty">No selected cases.</p>'
    items = []
    for item in cases:
        case = _dict_value(_dict_value(item).get("case"))
        status = _safe_text(case.get("status")) or "-"
        title = _safe_text(case.get("title") or case.get("case_nodeid"))
        nodeid = _safe_text(case.get("case_nodeid"))
        items.append(
            f'<a class="case-chip" href="#case-{_anchor_id(nodeid)}">'
            f'<span class="pill" style="--status:{_status_color(status)}">{_esc(status)}</span>'
            f'<strong>{_esc(title)}</strong><em>{_esc(nodeid)}</em>'
            '</a>'
        )
    return f'<div class="case-overview">{"".join(items)}</div>'


def _case_reports_html(cases: list[Any]) -> str:
    if not cases:
        return '<p class="empty">No case reports.</p>'
    return "".join(_case_report_html(_dict_value(item)) for item in cases)


def _case_report_html(item: dict[str, Any]) -> str:
    case = _dict_value(item.get("case"))
    steps = _list_value(item.get("steps"))
    logs = _list_value(item.get("logs"))
    key_logs = _list_value(item.get("key_logs"))
    artifacts = _list_value(item.get("artifacts"))
    status = _safe_text(case.get("status")) or "-"
    nodeid = _safe_text(case.get("case_nodeid"))
    title = _safe_text(case.get("title") or nodeid)
    detail_open = " open" if status != "passed" else ""
    detail_body = (
        _case_summary_html(_dict_value(item.get("case_summary")))
        + _loop_summary_html(_dict_value(item.get("loop_summary")))
        + _steps_html(steps)
        + _artifacts_html(artifacts)
    )
    return (
        f'<article class="case-report" id="case-{_anchor_id(nodeid)}">'
        '<header>'
        f'<div><h3>Case Report: {_esc(title)}</h3><p>{_esc(nodeid)}</p></div>'
        f'<span class="pill" style="--status:{_status_color(status)}">{_esc(status)}</span>'
        '</header>'
        '<div class="grid two">'
        f'<div><h4>Run Context</h4>{_case_context_html(case)}</div>'
        f'{_details_html("Detail", detail_body, detail_open)}'
        '</div>'
        f'{_details_html(f"Case Key Logs ({len(key_logs)})", _logs_html(key_logs, include_case=False), detail_open)}'
        f'{_details_html(f"Case Logs ({len(logs)})", _logs_html(logs, include_case=False))}'
        '</article>'
    )


def _case_context_html(case: dict[str, Any]) -> str:
    return _kv_html([
        ("Case Status", case.get("status")),
        ("Duration", duration_text(case.get("duration_ms"))),
    ], skip_empty=True)


def _case_summary_html(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    headline = _safe_text(summary.get("headline") or summary.get("title"))
    body = _safe_text(summary.get("body") or summary.get("message"))
    rows = [(key, value) for key, value in summary.items() if key not in {"headline", "title", "body", "message"}]
    content = (f"<p>{_esc(headline)}</p>" if headline else "") + (f"<p>{_esc(body)}</p>" if body else "")
    if rows:
        content += _kv_html(rows)
    return f'<div class="case-summary"><h4>Case Summary</h4>{content}</div>'


def _loop_summary_html(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    rows = _kv_html([("Observed Cycles", f"{summary.get('observed', 0)}/{summary.get('total', 0)}")])
    return f'<div class="loop-summary"><h4>Loop Summary</h4>{rows}{_loop_actions_html(summary.get("actions", {}))}</div>'


def _loop_actions_html(actions: Any) -> str:
    if not isinstance(actions, dict) or not actions:
        return ""
    action_rows = "".join(
        f"<tr><td>{_esc(name)}</td><td>{_esc(_status_counts_text(counts))}</td></tr>"
        for name, counts in actions.items()
        if isinstance(counts, dict)
    )
    return f'<table><thead><tr><th>Loop Action</th><th>Result</th></tr></thead><tbody>{action_rows}</tbody></table>' if action_rows else ""


def _status_counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))


def _artifacts_html(artifacts: list[Any]) -> str:
    if not artifacts:
        return ""
    rows = "".join(
        f"<tr><td>{_esc(_dict_value(item).get('title'))}</td><td>{_esc(_dict_value(item).get('path') or _dict_value(item).get('url'))}</td></tr>"
        for item in artifacts
    )
    return f'<div class="artifacts"><h4>Artifacts</h4><table><thead><tr><th>Title</th><th>Location</th></tr></thead><tbody>{rows}</tbody></table></div>'


def _kv_html(rows: list[tuple[str, Any]], *, skip_empty: bool = False) -> str:
    body = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>"
        for label, value in rows
        if not skip_empty or _safe_text(value)
    )
    return f'<table class="kv"><tbody>{body}</tbody></table>'


def _details_html(summary: str, body: str, attrs: str = "") -> str:
    return f'<details class="case-detail"{attrs}><summary>{_esc(summary)}</summary>{body}</details>'


def _chart_html(summary: dict[str, Any]) -> str:
    chart_items = [
        ("passed", _safe_int(summary.get("passed"))),
        ("failed", _safe_int(summary.get("failed"))),
        ("skipped", _safe_int(summary.get("skipped"))),
        ("running", _safe_int(summary.get("running"))),
    ]
    total = sum(value for _, value in chart_items)
    if total <= 0:
        return '<p class="empty">No case results.</p>'
    x = 0.0
    bars = []
    legend = []
    for status, value in chart_items:
        if value <= 0:
            continue
        width = value / total * 100
        color = _status_color(status)
        bars.append(f'<rect x="{x:.4f}" y="0" width="{width:.4f}" height="20" fill="{color}"><title>{status}: {value}</title></rect>')
        legend.append(f'<li><span style="background:{color}"></span>{_esc(status)} {_esc(value)}</li>')
        x += width
    return f'<svg class="bar" viewBox="0 0 100 20" preserveAspectRatio="none">{"".join(bars)}</svg><ul class="legend">{"".join(legend)}</ul>'


def _duration_ranking_html(rows: list[Any]) -> str:
    if not rows:
        return '<p class="empty">No case duration data.</p>'
    max_duration = max(_safe_int(_dict_value(row).get("duration_ms")) for row in rows) or 1
    items = []
    for raw in rows:
        row = _dict_value(raw)
        duration = _safe_int(row.get("duration_ms"))
        width = max(2, duration / max_duration * 100)
        items.append(
            '<li>'
            f'<div><strong>{_esc(row.get("title"))}</strong><span>{_esc(row.get("case_nodeid"))}</span></div>'
            f'<em>{_esc(duration)} ms</em><i style="width:{width:.2f}%"></i>'
            '</li>'
        )
    return f'<ul class="metric-bars">{"".join(items)}</ul>'


def _log_distribution_html(distribution: dict[str, Any]) -> str:
    level_items = _count_bar_items(_dict_value(distribution.get("levels")), color_by_level=True)
    domain_items = _count_bar_items(_dict_value(distribution.get("domains")), color_by_level=False)
    if not level_items and not domain_items:
        return '<p class="empty">No log data.</p>'
    return (
        '<div class="distribution">'
        f'<h3>By Level</h3><ul class="metric-bars compact">{level_items or "<li>No level data</li>"}</ul>'
        f'<h3>By Domain</h3><ul class="metric-bars compact">{domain_items or "<li>No domain data</li>"}</ul>'
        '</div>'
    )


def _count_bar_items(counts: dict[str, Any], *, color_by_level: bool) -> str:
    if not counts:
        return ""
    max_count = max(_safe_int(value) for value in counts.values()) or 1
    items = []
    for key, value in sorted(counts.items(), key=lambda item: _safe_int(item[1]), reverse=True):
        width = max(2, _safe_int(value) / max_count * 100)
        color = _LEVEL_COLORS.get(key, _DOMAIN_COLORS.get(key, "#616161")) if color_by_level else _DOMAIN_COLORS.get(key, "#616161")
        items.append(
            '<li>'
            f'<div><strong>{_esc(key)}</strong></div><em>{_esc(value)}</em>'
            f'<i style="width:{width:.2f}%;background:{color}"></i>'
            '</li>'
        )
    return "".join(items)


def _failure_analysis_html(analysis: dict[str, Any]) -> str:
    primary = _dict_value(analysis.get("primary_failure"))
    if not primary:
        status = _safe_text(analysis.get("status")) or "passed"
        return f'<p class="empty">No failed step detected. Analysis status: {_esc(status)}.</p>'

    failed_cases = _list_value(analysis.get("failed_cases"))
    evidence_logs = _list_value(primary.get("evidence_logs"))
    case_items = "".join(
        f"<li>{_esc(_dict_value(row).get('title') or _dict_value(row).get('case_nodeid'))}<span>{_esc(_dict_value(row).get('case_nodeid'))}</span></li>"
        for row in failed_cases
    )
    log_items = "".join(
        f"<li><strong>{_esc(_dict_value(row).get('level') or 'info')}</strong><pre>{_esc(_dict_value(row).get('line'))}</pre></li>"
        for row in evidence_logs[:8]
    )
    facts = [
        ("Case", primary.get("case_nodeid")),
        ("Step", primary.get("title")),
        ("Kind", primary.get("kind")),
        ("Error", primary.get("error")),
        ("Expected", primary.get("expected")),
        ("Actual", primary.get("actual")),
    ]
    facts_html = _kv_html(facts, skip_empty=True)
    cases_html = f'<div><h3>Affected Cases</h3><ul class="failure-list">{case_items}</ul></div>' if case_items else ""
    logs_html = f'<div><h3>Evidence Logs</h3><ul class="failure-logs">{log_items}</ul></div>' if log_items else '<p class="empty">No related warning/error logs provided for the primary failure.</p>'
    return f'<div class="failure-grid">{facts_html}{cases_html}{logs_html}</div>'


def _steps_html(steps: list[Any]) -> str:
    if not steps:
        return '<p class="empty">No steps recorded.</p>'
    rows = []
    for raw in steps:
        row = _dict_value(raw)
        status = _safe_text(row.get("status")) or "-"
        error = row.get("error")
        rows.append(
            "<tr>"
            f'<td><span class="pill" style="--status:{_status_color(status)}">{_esc(status)}</span></td>'
            f"<td>{_esc(row.get('kind') or 'step')}</td>"
            f"<td>{_esc(row.get('title') or row.get('id'))}</td>"
            f"<td>{_esc(row.get('definition_id') or row.get('id'))}</td>"
            f"<td>{_esc(row.get('duration_ms') or 0)} ms</td>"
            f"<td>{_esc(error)}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>Status</th><th>Kind</th><th>Title</th><th>Definition</th><th>Duration</th><th>Error</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def _logs_html(logs: list[Any], *, include_case: bool = True) -> str:
    if not logs:
        return '<p class="empty">No logs recorded.</p>'
    rows = []
    for raw in logs:
        row = _dict_value(raw)
        level = _safe_text(row.get("level")) or "info"
        domain = _safe_text(row.get("domain")) or "framework"
        source = _safe_text(row.get("source"))
        color = _LEVEL_COLORS.get(level, _DOMAIN_COLORS.get(domain, "#616161"))
        case_cell = f"<td>{_esc(row.get('case_nodeid'))}</td>" if include_case else ""
        rows.append(
            f'<tr style="--accent:{_DOMAIN_COLORS.get(domain, "#616161")};--text:{color}">'
            f"<td>{_esc(level)}</td>"
            f"<td>{_esc(domain)}</td>"
            f"<td>{_esc(source)}</td>"
            f"{case_cell}"
            f"<td><pre>{_esc(row.get('line'))}</pre></td>"
            "</tr>"
        )
    case_header = "<th>Case</th>" if include_case else ""
    return f'<table class="logs"><thead><tr><th>Level</th><th>Domain</th><th>Source</th>{case_header}<th>Message</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def _report_css() -> str:
    return """
:root{color-scheme:light dark;font-family:"Segoe UI",Arial,sans-serif;background:#f5f7fb;color:#111827}body{margin:0;background:#f5f7fb;color:#111827}main{max-width:1280px;margin:0 auto;padding:28px}
.hero{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:18px}.eyebrow{margin:0 0 8px;color:#526071;font-size:13px;font-weight:600;text-transform:uppercase}h1{margin:0;font-size:28px;font-weight:650;letter-spacing:0}h2{margin:0 0 14px;font-size:18px;font-weight:650}.meta{margin:8px 0 0;color:#526071}
.status,.pill{background:color-mix(in srgb,var(--status) 12%,white);border:1px solid color-mix(in srgb,var(--status) 42%,white);color:var(--status);border-radius:999px;padding:5px 10px;font-weight:650}section,article{background:#fff;border:1px solid #e5e7eb;border-radius:8px}section{margin-top:14px;padding:16px}article{padding:16px}
.summary{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:10px;background:transparent;border:0;padding:0}.summary article span{display:block;color:#526071;font-size:12px}.summary article strong{display:block;margin-top:6px;font-size:22px}
.grid{display:grid;gap:14px}.two{grid-template-columns:1fr 1fr}.three{grid-template-columns:1fr 1fr 1fr}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #edf0f5;padding:9px;text-align:left;vertical-align:top}th{color:#526071;font-weight:650;background:#fafbfc}.kv th{width:160px}.bar{width:100%;height:38px;border-radius:6px;overflow:hidden;background:#eef2f7}.legend{display:flex;gap:14px;list-style:none;padding:0;margin:12px 0 0;flex-wrap:wrap}.legend span{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.metric-bars{list-style:none;margin:0;padding:0}.metric-bars li{position:relative;padding:8px 0 10px;border-bottom:1px solid #edf0f5}.metric-bars li:last-child{border-bottom:0}.metric-bars div{display:flex;flex-direction:column;gap:2px;max-width:72%}.metric-bars strong{font-size:13px}.metric-bars span{font-size:12px;color:#526071;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.metric-bars em{position:absolute;right:0;top:8px;font-style:normal;color:#526071;font-size:12px}.metric-bars i{display:block;height:4px;margin-top:8px;border-radius:999px;background:#2563eb}.metric-bars.compact h3{margin-top:0}.distribution h3{margin:0 0 6px;font-size:13px}.distribution h3:not(:first-child){margin-top:12px}
.case-overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.case-chip{display:grid;grid-template-columns:auto 1fr;gap:6px 10px;align-items:center;text-decoration:none;color:inherit;border:1px solid #edf0f5;border-radius:8px;padding:10px}.case-chip strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.case-chip em{grid-column:2;color:#526071;font-size:12px;font-style:normal;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.case-report{margin-top:14px}.case-report header{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:12px}.case-report h3{margin:0;font-size:18px}.case-report h4{margin:0 0 10px;font-size:14px}.case-report p{margin:4px 0 0;color:#526071;word-break:break-all}.case-detail{border:1px solid #edf0f5;border-radius:8px;padding:10px;background:#fff}.case-detail summary{cursor:pointer;font-weight:650}.case-detail table,.case-detail .empty{margin-top:10px}
.case-summary,.loop-summary,.artifacts{margin:10px 0 12px}.failure-grid{display:grid;grid-template-columns:minmax(280px,1fr) minmax(220px,.7fr);gap:14px}.failure-grid table{grid-column:1/-1}.failure-grid h3{margin:0 0 8px;font-size:14px}.failure-list,.failure-logs{list-style:none;margin:0;padding:0}.failure-list li,.failure-logs li{border:1px solid #edf0f5;border-radius:6px;padding:8px;margin-bottom:8px}.failure-list span{display:block;color:#526071;font-size:12px;margin-top:4px}.failure-logs pre{margin:4px 0 0;white-space:pre-wrap;word-break:break-word;font-family:"Cascadia Mono",Consolas,monospace}
.logs tr{border-left:3px solid var(--accent)}.logs td:first-child{color:var(--text);font-weight:650}.logs pre{margin:0;white-space:pre-wrap;word-break:break-word;font-family:"Cascadia Mono",Consolas,monospace}.empty{color:#526071;margin:0}
@media (max-width:1100px){.three{grid-template-columns:1fr 1fr}}@media (max-width:900px){main{padding:16px}.summary{grid-template-columns:repeat(2,1fr)}.two,.three,.failure-grid{grid-template-columns:1fr}.hero{display:block}.status{display:inline-block;margin-top:12px}}
@media (prefers-color-scheme:dark){:root,body{background:#111827;color:#f3f4f6}section,article,.case-detail{background:#1f2937;border-color:#374151}th,td{border-color:#374151}th{background:#243041;color:#cbd5e1}.meta,.eyebrow,.empty,.failure-list span,.metric-bars span,.metric-bars em,.case-chip em,.case-report p{color:#cbd5e1}.summary{background:transparent}.status,.pill{background:color-mix(in srgb,var(--status) 24%,#111827);border-color:color-mix(in srgb,var(--status) 56%,#111827)}.bar{background:#374151}.failure-list li,.failure-logs li,.metric-bars li,.case-chip{border-color:#374151}}
"""
