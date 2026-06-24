from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from testing.reporting.store import ReportStore


REPORT_SCHEMA_VERSION = 1
_NOISY_REPORT_LOG_PREFIXES = (
    "[step-debug.",
    "[android_client.status]",
    "[android_client.power] waiting_for_resume=",
    "[android_client.power] snapshot channel ready",
    "[android_client.power] host quiet mode:",
    "[testing.runner.android_client] baseline phase=",
)
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


def _is_noisy_report_log(line: str) -> bool:
    return any(line.startswith(prefix) for prefix in _NOISY_REPORT_LOG_PREFIXES)


def filter_report_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in logs:
        if not isinstance(row, dict):
            continue
        line = _safe_text(row.get("line"))
        if not line or _is_noisy_report_log(line):
            continue
        normalized = dict(row)
        normalized["line"] = line
        filtered.append(normalized)
    return filtered


def logs_for_step(report: dict[str, Any], step: dict[str, Any]) -> list[dict[str, Any]]:
    logs = filter_report_logs([row for row in report.get("logs", []) if isinstance(row, dict)])
    case_nodeid = _safe_text(step.get("case_nodeid"))
    step_id = _safe_text(step.get("id") or step.get("step_id"))
    related: list[dict[str, Any]] = []
    for row in logs:
        row_case = _safe_text(row.get("case_nodeid"))
        row_step = _safe_text(row.get("step_id"))
        if step_id and row_step == step_id:
            related.append(row)
            continue
        if case_nodeid and row_case == case_nodeid and _safe_text(row.get("level")).lower() in {"warning", "error", "critical"}:
            related.append(row)
    return related


def case_logs(report: dict[str, Any], case_nodeid: str) -> list[dict[str, Any]]:
    nodeid = _safe_text(case_nodeid)
    if not nodeid:
        return []
    logs = filter_report_logs([row for row in report.get("logs", []) if isinstance(row, dict)])
    start_index = _case_log_start_index(logs, nodeid)
    if start_index is None:
        return []
    next_start = _next_case_log_start_index(report, logs, nodeid, start_index)
    if next_start is not None:
        return logs[start_index:next_start]
    end_index = _last_related_case_log_index(logs, nodeid, start_index)
    return logs[start_index : end_index + 1]


def _case_log_start_index(logs: list[dict[str, Any]], case_nodeid: str) -> int | None:
    for index, row in enumerate(logs):
        if _log_starts_case_execution(row, case_nodeid):
            return index
    for index, row in enumerate(logs):
        if _log_references_case(row, case_nodeid):
            return index
    return None


def _next_case_log_start_index(
    report: dict[str, Any],
    logs: list[dict[str, Any]],
    case_nodeid: str,
    start_index: int,
) -> int | None:
    case_nodeids = [
        _safe_text(row.get("case_nodeid"))
        for row in report.get("steps", [])
        if isinstance(row, dict) and _safe_text(row.get("kind")) == "case"
    ]
    for index in range(start_index + 1, len(logs)):
        for other_nodeid in case_nodeids:
            if other_nodeid and other_nodeid != case_nodeid and _log_starts_case_execution(logs[index], other_nodeid):
                return index
    return None


def _last_related_case_log_index(logs: list[dict[str, Any]], case_nodeid: str, start_index: int) -> int:
    last_index = start_index
    for index in range(start_index, len(logs)):
        if _log_references_case(logs[index], case_nodeid):
            last_index = index
    return last_index


def _log_references_case(row: dict[str, Any], case_nodeid: str) -> bool:
    nodeid = _safe_text(case_nodeid)
    line = _safe_text(row.get("line"))
    return (
        _safe_text(row.get("case_nodeid")) == nodeid
        or f"case={nodeid}" in line
        or f"trigger={nodeid}" in line
    )


def _log_starts_case_execution(row: dict[str, Any], case_nodeid: str) -> bool:
    nodeid = _safe_text(case_nodeid)
    line = _safe_text(row.get("line"))
    return _safe_text(row.get("case_nodeid")) == nodeid or f"trigger={nodeid}" in line


def classify_failure(error_text: Any, logs: list[dict[str, Any]]) -> str:
    text = " ".join([_safe_text(error_text)] + [_safe_text(row.get("line")) for row in logs]).lower()
    if any(token in text for token in ("timeout", "timed out", "waiting for", "wait ")):
        return "timeout"
    if any(token in text for token in ("adb", "device", "serial", "offline", "unauthorized")):
        return "dut"
    if any(token in text for token in ("android_client", "apk", "package", "snapshot")):
        return "android"
    if any(token in text for token in ("equipment", "relay", "attenuator", "serial port")):
        return "equipment"
    if any(token in text for token in ("assert", "expected", "actual", "mismatch", "validation")):
        return "assertion"
    if any(token in text for token in ("traceback", "exception", "typeerror", "attributeerror", "runtimeerror")):
        return "framework"
    return "unknown"


def failure_analysis(report: dict[str, Any]) -> dict[str, Any]:
    steps = [row for row in report.get("steps", []) if isinstance(row, dict)]
    failed_steps = [row for row in steps if _safe_text(row.get("status")) == "failed" and _safe_text(row.get("kind")) != "case"]
    failed_cases = [
        {"case_nodeid": _safe_text(row.get("case_nodeid")), "title": _safe_text(row.get("title") or row.get("case_nodeid"))}
        for row in steps
        if _safe_text(row.get("status")) == "failed" and _safe_text(row.get("kind")) == "case"
    ]
    primary = failed_steps[0] if failed_steps else next((row for row in steps if _safe_text(row.get("status")) == "failed"), None)
    if primary is None:
        return {
            "status": "stopped" if report.get("stopped") else "passed",
            "failed_cases": failed_cases,
            "failed_steps": [],
            "primary_failure": {},
        }

    evidence_logs = logs_for_step(report, primary)
    error_text = primary.get("error") or primary.get("actual") or primary.get("title")
    primary_failure = {
        "id": _safe_text(primary.get("id")),
        "title": _safe_text(primary.get("title") or primary.get("id")),
        "case_nodeid": _safe_text(primary.get("case_nodeid")),
        "kind": _safe_text(primary.get("kind")),
        "category": classify_failure(error_text, evidence_logs),
        "error": _safe_text(error_text),
        "expected": primary.get("expected", ""),
        "actual": primary.get("actual", ""),
        "evidence_logs": evidence_logs,
    }
    return {
        "status": "failed",
        "failed_cases": failed_cases,
        "failed_steps": failed_steps,
        "primary_failure": primary_failure,
    }


def case_duration_ranking(report: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    steps = [row for row in report.get("steps", []) if isinstance(row, dict)]
    cases = [
        {
            "title": _safe_text(row.get("title") or row.get("case_nodeid")),
            "case_nodeid": _safe_text(row.get("case_nodeid")),
            "duration_ms": _safe_int(row.get("duration_ms")),
        }
        for row in steps
        if _safe_text(row.get("kind")) == "case"
    ]
    cases.sort(key=lambda row: int(row.get("duration_ms", 0) or 0), reverse=True)
    return cases[: max(0, int(limit))]


def log_distribution(report: dict[str, Any]) -> dict[str, dict[str, int]]:
    logs = filter_report_logs([row for row in report.get("logs", []) if isinstance(row, dict)])
    levels: dict[str, int] = {}
    domains: dict[str, int] = {}
    for row in logs:
        level = _safe_text(row.get("level")).lower() or "info"
        domain = _safe_text(row.get("domain")).lower() or "framework"
        levels[level] = levels.get(level, 0) + 1
        domains[domain] = domains.get(domain, 0) + 1
    return {"levels": levels, "domains": domains}


def case_reports(report: dict[str, Any]) -> list[dict[str, Any]]:
    steps = [row for row in report.get("steps", []) if isinstance(row, dict)]
    cases = [row for row in steps if _safe_text(row.get("kind")) == "case"]
    if not cases:
        selected = report.get("selected_nodeids") if isinstance(report.get("selected_nodeids"), list) else []
        cases = [
            {
                "id": f"case:{_safe_text(nodeid)}",
                "kind": "case",
                "case_nodeid": _safe_text(nodeid),
                "title": _safe_text(nodeid),
                "status": "planned",
                "duration_ms": 0,
            }
            for nodeid in selected
            if _safe_text(nodeid)
        ]
    reports: list[dict[str, Any]] = []
    for case in cases:
        nodeid = _safe_text(case.get("case_nodeid"))
        case_steps = [
            row
            for row in steps
            if _safe_text(row.get("case_nodeid")) == nodeid and _safe_text(row.get("kind")) != "case"
        ]
        logs = case_logs(report, nodeid)
        reports.append(
            {
                "case": case,
                "steps": _failure_first_steps(case_steps),
                "logs": logs,
                "key_logs": _key_logs(logs),
            }
        )
    reports.sort(key=lambda item: (0 if _safe_text(item["case"].get("status")) == "failed" else 1, _safe_text(item["case"].get("title"))))
    return reports


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
    normalized_steps = [dict(row) for row in steps if isinstance(row, dict)]
    normalized_logs = filter_report_logs(logs)
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


def save_run_report(report: dict[str, Any], *, reports_dir: Path) -> Path:
    normalized = dict(report)
    normalized["run_id"] = _safe_text(normalized.get("run_id")) or uuid4().hex
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


def report_html_path(run_id: str, *, reports_dir: Path) -> Path:
    report = load_report(run_id, reports_dir=reports_dir)
    stem = report_file_stem(report) if report else _safe_filename(run_id)
    return reports_dir / f"{stem}.html"


def report_pdf_path(run_id: str, *, reports_dir: Path) -> Path:
    report = load_report(run_id, reports_dir=reports_dir)
    stem = report_file_stem(report) if report else _safe_filename(run_id)
    return reports_dir / f"{stem}.pdf"


def report_html_url(run_id: str, *, reports_dir: Path) -> str:
    path = report_html_path(run_id, reports_dir=reports_dir)
    if not path.exists():
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
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    analysis = failure_analysis(report)
    durations = case_duration_ranking(report)
    distribution = log_distribution(report)
    cases = case_reports(report)
    status = _safe_text(report.get("status")) or "empty"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(report.get("title") or "SmartTest Report")}</title>
<style>{_report_css()}</style>
</head>
<body>
<main>
  <header class="hero">
    <div>
      <p class="eyebrow">SmartTest Report</p>
      <h1>{_esc(report.get("title") or report.get("run_id") or "Run Report")}</h1>
      <p class="meta">{_esc(report.get("started_at"))} - {_esc(report.get("finished_at"))}</p>
    </div>
    <span class="status" style="--status:{_status_color(status)}">{_esc(status)}</span>
  </header>
  {_summary_html(report, counts)}
  <section>
    <h2>Failure Analysis</h2>
    {_failure_analysis_html(analysis)}
  </section>
  <section>
    <h2>Cases In This Run</h2>
    {_cases_overview_html(cases)}
  </section>
  <section class="grid three">
    <article>
      <h2>Result Chart</h2>
      {_chart_html(counts)}
    </article>
    <article>
      <h2>Case Duration</h2>
      {_duration_ranking_html(durations)}
    </article>
    <article>
      <h2>Log Distribution</h2>
      {_log_distribution_html(distribution)}
    </article>
  </section>
  <section>
    <h2>Run Summary</h2>
    {_context_html(report)}
  </section>
  <section>
    <h2>Case Reports</h2>
    {_case_reports_html(report, cases)}
  </section>
</main>
</body>
</html>
"""


def _esc(value: Any) -> str:
    return html.escape(_safe_text(value), quote=True)


def _anchor_id(value: Any) -> str:
    text = _safe_text(value)
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    return normalized or "case"


def _status_color(status: str) -> str:
    return _STATUS_COLORS.get(status, "#6b7280")


def _duration_text(duration_ms: Any) -> str:
    total_seconds = max(0, _safe_int(duration_ms) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _summary_html(report: dict[str, Any], counts: dict[str, Any]) -> str:
    items = [
        ("Total", counts.get("total", 0)),
        ("Passed", counts.get("passed", 0)),
        ("Failed", counts.get("failed", 0)),
        ("Skipped", counts.get("skipped", 0)),
        ("Duration", _duration_text(report.get("duration_ms"))),
    ]
    cards = "".join(f"<article><span>{_esc(label)}</span><strong>{_esc(value)}</strong></article>" for label, value in items)
    return f'<section class="summary">{cards}</section>'


def _context_html(report: dict[str, Any]) -> str:
    nodeids = report.get("selected_nodeids") if isinstance(report.get("selected_nodeids"), list) else []
    rows = [
        ("Run ID", report.get("run_id")),
        ("DUT", report.get("adb_serial") or "No DUT"),
        ("Return Code", report.get("returncode")),
        ("Stopped", "Yes" if report.get("stopped") else "No"),
        ("Selected Cases", len(nodeids)),
    ]
    body = "".join(f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows)
    return f'<table class="kv"><tbody>{body}</tbody></table>'


def _cases_overview_html(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return '<p class="empty">No selected cases.</p>'
    items = []
    for item in cases:
        case = item.get("case", {}) if isinstance(item, dict) else {}
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


def _case_reports_html(report: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    if not cases:
        return '<p class="empty">No case reports.</p>'
    return "".join(_case_report_html(report, item) for item in cases)


def _case_report_html(report: dict[str, Any], item: dict[str, Any]) -> str:
    case = item.get("case", {}) if isinstance(item, dict) else {}
    steps = item.get("steps", []) if isinstance(item.get("steps"), list) else []
    logs = item.get("logs", []) if isinstance(item.get("logs"), list) else []
    key_logs = item.get("key_logs", []) if isinstance(item.get("key_logs"), list) else []
    status = _safe_text(case.get("status")) or "-"
    nodeid = _safe_text(case.get("case_nodeid"))
    title = _safe_text(case.get("title") or nodeid)
    detail_open = " open" if status != "passed" else ""
    return (
        f'<article class="case-report" id="case-{_anchor_id(nodeid)}">'
        '<header>'
        f'<div><h3>Case Report: {_esc(title)}</h3><p>{_esc(nodeid)}</p></div>'
        f'<span class="pill" style="--status:{_status_color(status)}">{_esc(status)}</span>'
        '</header>'
        '<div class="grid two">'
        f'<div><h4>Run Context</h4>{_case_context_html(report, case)}</div>'
        f'<details class="case-detail"{detail_open}><summary>Detail</summary>{_steps_html(steps)}</details>'
        '</div>'
        f'<details class="case-detail"{detail_open}><summary>Case Key Logs ({len(key_logs)})</summary>{_logs_html(key_logs, include_case=False)}</details>'
        f'<details class="case-detail"><summary>Case Logs ({len(logs)})</summary>{_logs_html(logs, include_case=False)}</details>'
        '</article>'
    )


def _case_context_html(report: dict[str, Any], case: dict[str, Any]) -> str:
    rows = [
        ("DUT", report.get("adb_serial") or "No DUT"),
        ("Run ID", report.get("run_id")),
        ("Return Code", report.get("returncode")),
        ("Case Status", case.get("status")),
        ("Duration", _duration_text(case.get("duration_ms"))),
    ]
    body = "".join(f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows if _safe_text(value))
    return f'<table class="kv"><tbody>{body}</tbody></table>'


def _chart_html(counts: dict[str, Any]) -> str:
    chart_items = [
        ("passed", _safe_int(counts.get("passed"))),
        ("failed", _safe_int(counts.get("failed"))),
        ("skipped", _safe_int(counts.get("skipped"))),
        ("running", _safe_int(counts.get("running"))),
    ]
    total = sum(value for _, value in chart_items)
    if total <= 0:
        return '<p class="empty">No case results.</p>'
    x = 0
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


def _duration_ranking_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="empty">No case duration data.</p>'
    max_duration = max(_safe_int(row.get("duration_ms")) for row in rows) or 1
    items = []
    for row in rows:
        duration = _safe_int(row.get("duration_ms"))
        width = max(2, duration / max_duration * 100)
        items.append(
            '<li>'
            f'<div><strong>{_esc(row.get("title"))}</strong><span>{_esc(row.get("case_nodeid"))}</span></div>'
            f'<em>{_esc(duration)} ms</em><i style="width:{width:.2f}%"></i>'
            '</li>'
        )
    return f'<ul class="metric-bars">{"".join(items)}</ul>'


def _log_distribution_html(distribution: dict[str, dict[str, int]]) -> str:
    level_items = _count_bar_items(distribution.get("levels", {}), color_by_level=True)
    domain_items = _count_bar_items(distribution.get("domains", {}), color_by_level=False)
    if not level_items and not domain_items:
        return '<p class="empty">No log data.</p>'
    return (
        '<div class="distribution">'
        f'<h3>By Level</h3><ul class="metric-bars compact">{level_items or "<li>No level data</li>"}</ul>'
        f'<h3>By Domain</h3><ul class="metric-bars compact">{domain_items or "<li>No domain data</li>"}</ul>'
        '</div>'
    )


def _count_bar_items(counts: dict[str, int], *, color_by_level: bool) -> str:
    if not counts:
        return ""
    max_count = max(counts.values()) or 1
    items = []
    for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        width = max(2, value / max_count * 100)
        color = _LEVEL_COLORS.get(key, _DOMAIN_COLORS.get(key, "#616161")) if color_by_level else _DOMAIN_COLORS.get(key, "#616161")
        items.append(
            '<li>'
            f'<div><strong>{_esc(key)}</strong></div><em>{_esc(value)}</em>'
            f'<i style="width:{width:.2f}%;background:{color}"></i>'
            '</li>'
        )
    return "".join(items)


def _failure_first_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        steps,
        key=lambda row: (
            0 if _safe_text(row.get("status")) == "failed" else 1,
            0 if _safe_text(row.get("kind")) == "case" else 1,
        ),
    )


def _key_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in logs
        if _safe_text(row.get("level")).lower() in {"warning", "error", "critical"}
    ]


def _failure_analysis_html(analysis: dict[str, Any]) -> str:
    primary = analysis.get("primary_failure") if isinstance(analysis.get("primary_failure"), dict) else {}
    if not primary:
        status = _safe_text(analysis.get("status")) or "passed"
        return f'<p class="empty">No failed step detected. Analysis status: {_esc(status)}.</p>'

    failed_cases = analysis.get("failed_cases") if isinstance(analysis.get("failed_cases"), list) else []
    evidence_logs = primary.get("evidence_logs") if isinstance(primary.get("evidence_logs"), list) else []
    case_items = "".join(
        f"<li>{_esc(row.get('title') or row.get('case_nodeid'))}<span>{_esc(row.get('case_nodeid'))}</span></li>"
        for row in failed_cases
        if isinstance(row, dict)
    )
    log_items = "".join(
        f"<li><strong>{_esc(row.get('level') or 'info')}</strong><pre>{_esc(row.get('line'))}</pre></li>"
        for row in evidence_logs[:8]
        if isinstance(row, dict)
    )
    facts = [
        ("Category", primary.get("category")),
        ("Case", primary.get("case_nodeid")),
        ("Step", primary.get("title")),
        ("Kind", primary.get("kind")),
        ("Error", primary.get("error")),
        ("Expected", primary.get("expected")),
        ("Actual", primary.get("actual")),
    ]
    rows = "".join(f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in facts if _safe_text(value))
    cases_html = f'<div><h3>Affected Cases</h3><ul class="failure-list">{case_items}</ul></div>' if case_items else ""
    logs_html = f'<div><h3>Evidence Logs</h3><ul class="failure-logs">{log_items}</ul></div>' if log_items else '<p class="empty">No related warning/error logs found for the primary failure.</p>'
    return f'<div class="failure-grid"><table class="kv"><tbody>{rows}</tbody></table>{cases_html}{logs_html}</div>'


def _steps_html(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return '<p class="empty">No steps recorded.</p>'
    rows = []
    for row in steps:
        status = _safe_text(row.get("status")) or "-"
        error = row.get("error")
        error_text = "" if error in (None, "", {}) else json.dumps(error, ensure_ascii=False, sort_keys=True)
        rows.append(
            "<tr>"
            f'<td><span class="pill" style="--status:{_status_color(status)}">{_esc(status)}</span></td>'
            f"<td>{_esc(row.get('kind') or 'step')}</td>"
            f"<td>{_esc(row.get('title') or row.get('id'))}</td>"
            f"<td>{_esc(row.get('definition_id') or row.get('id'))}</td>"
            f"<td>{_esc(row.get('duration_ms') or 0)} ms</td>"
            f"<td>{_esc(error_text)}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>Status</th><th>Kind</th><th>Title</th><th>Definition</th><th>Duration</th><th>Error</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def _logs_html(logs: list[dict[str, Any]], *, include_case: bool = True) -> str:
    if not logs:
        return '<p class="empty">No logs recorded.</p>'
    rows = []
    for row in logs:
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
:root{color-scheme:light dark;font-family:"Segoe UI",Arial,sans-serif;background:#f5f7fb;color:#111827}
body{margin:0;background:#f5f7fb;color:#111827}
main{max-width:1280px;margin:0 auto;padding:28px}
.hero{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:18px}
.eyebrow{margin:0 0 8px;color:#526071;font-size:13px;font-weight:600;text-transform:uppercase}
h1{margin:0;font-size:28px;font-weight:650;letter-spacing:0}
h2{margin:0 0 14px;font-size:18px;font-weight:650}
.meta{margin:8px 0 0;color:#526071}
.status,.pill{background:color-mix(in srgb,var(--status) 12%,white);border:1px solid color-mix(in srgb,var(--status) 42%,white);color:var(--status);border-radius:999px;padding:5px 10px;font-weight:650}
section,article{background:#fff;border:1px solid #e5e7eb;border-radius:8px}
section{margin-top:14px;padding:16px}
article{padding:16px}
.summary{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:10px;background:transparent;border:0;padding:0}
.summary article span{display:block;color:#526071;font-size:12px}.summary article strong{display:block;margin-top:6px;font-size:22px}
.grid{display:grid;gap:14px}.two{grid-template-columns:1fr 1fr}.three{grid-template-columns:1fr 1fr 1fr}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #edf0f5;padding:9px;text-align:left;vertical-align:top}th{color:#526071;font-weight:650;background:#fafbfc}
.kv th{width:160px}.bar{width:100%;height:38px;border-radius:6px;overflow:hidden;background:#eef2f7}.legend{display:flex;gap:14px;list-style:none;padding:0;margin:12px 0 0;flex-wrap:wrap}.legend span{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.metric-bars{list-style:none;margin:0;padding:0}.metric-bars li{position:relative;padding:8px 0 10px;border-bottom:1px solid #edf0f5}.metric-bars li:last-child{border-bottom:0}.metric-bars div{display:flex;flex-direction:column;gap:2px;max-width:72%}.metric-bars strong{font-size:13px}.metric-bars span{font-size:12px;color:#526071;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.metric-bars em{position:absolute;right:0;top:8px;font-style:normal;color:#526071;font-size:12px}.metric-bars i{display:block;height:4px;margin-top:8px;border-radius:999px;background:#2563eb}.metric-bars.compact h3{margin-top:0}.distribution h3{margin:0 0 6px;font-size:13px}.distribution h3:not(:first-child){margin-top:12px}
.case-overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.case-chip{display:grid;grid-template-columns:auto 1fr;gap:6px 10px;align-items:center;text-decoration:none;color:inherit;border:1px solid #edf0f5;border-radius:8px;padding:10px}.case-chip strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.case-chip em{grid-column:2;color:#526071;font-size:12px;font-style:normal;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.case-report{margin-top:14px}.case-report header{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:12px}.case-report h3{margin:0;font-size:18px}.case-report h4{margin:0 0 10px;font-size:14px}.case-report p{margin:4px 0 0;color:#526071;word-break:break-all}.case-detail{border:1px solid #edf0f5;border-radius:8px;padding:10px;background:#fff}.case-detail summary{cursor:pointer;font-weight:650}.case-detail table,.case-detail .empty{margin-top:10px}
.failure-grid{display:grid;grid-template-columns:minmax(280px,1fr) minmax(220px,.7fr);gap:14px}.failure-grid table{grid-column:1/-1}.failure-grid h3{margin:0 0 8px;font-size:14px}.failure-list,.failure-logs{list-style:none;margin:0;padding:0}.failure-list li,.failure-logs li{border:1px solid #edf0f5;border-radius:6px;padding:8px;margin-bottom:8px}.failure-list span{display:block;color:#526071;font-size:12px;margin-top:4px}.failure-logs pre{margin:4px 0 0;white-space:pre-wrap;word-break:break-word;font-family:"Cascadia Mono",Consolas,monospace}
.logs tr{border-left:3px solid var(--accent)}.logs td:first-child{color:var(--text);font-weight:650}.logs pre{margin:0;white-space:pre-wrap;word-break:break-word;font-family:"Cascadia Mono",Consolas,monospace}
.empty{color:#526071;margin:0}
@media (max-width:1100px){.three{grid-template-columns:1fr 1fr}}@media (max-width:900px){main{padding:16px}.summary{grid-template-columns:repeat(2,1fr)}.two,.three,.failure-grid{grid-template-columns:1fr}.hero{display:block}.status{display:inline-block;margin-top:12px}}
@media (prefers-color-scheme:dark){:root,body{background:#111827;color:#f3f4f6}section,article,.case-detail{background:#1f2937;border-color:#374151}th,td{border-color:#374151}th{background:#243041;color:#cbd5e1}.meta,.eyebrow,.empty,.failure-list span,.metric-bars span,.metric-bars em,.case-chip em,.case-report p{color:#cbd5e1}.summary{background:transparent}.status,.pill{background:color-mix(in srgb,var(--status) 24%,#111827);border-color:color-mix(in srgb,var(--status) 56%,#111827)}.bar{background:#374151}.failure-list li,.failure-logs li,.metric-bars li,.case-chip{border-color:#374151}}
"""
