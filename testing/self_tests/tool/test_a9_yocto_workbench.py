from __future__ import annotations

import ast
import builtins
from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from tool.common.daily_report.workflows import daily_report_workflow as workflow


def test_workbench_source_uses_only_allowed_imports():
    source_path = Path(workflow.__file__)
    tree = ast.parse(source_path.read_text("utf-8"), filename=str(source_path))
    allowed = {"base64", "collections", "datetime", "html", "json", "math", "re"}
    imported = {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported.update(
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert imported <= allowed


def test_workbench_source_does_not_access_dunder_attributes():
    source_path = Path(workflow.__file__)
    tree = ast.parse(source_path.read_text("utf-8"), filename=str(source_path))
    forbidden = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr.startswith("__")
        and node.attr.endswith("__")
    ]

    assert forbidden == []


def test_workbench_source_does_not_reference_restricted_binary_builtins():
    source_path = Path(workflow.__file__)
    tree = ast.parse(source_path.read_text("utf-8"), filename=str(source_path))

    assert {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }.isdisjoint({"bytes", "bytearray"})


def test_jira_pages_load_when_workbench_does_not_expose_bytes_builtins(tmp_path):
    source_path = Path(workflow.__file__)
    restricted_builtins = dict(vars(builtins))
    restricted_builtins.pop("bytes", None)
    restricted_builtins.pop("bytearray", None)
    namespace = {"__builtins__": restricted_builtins, "__name__": "workbench_test"}
    exec(compile(source_path.read_text("utf-8"), str(source_path), "exec"), namespace)
    wf = FakeWorkflow(
        tmp_path,
        jira_results=['search_id: current\n分为 1 页'],
        files={"jira/current/page_1.json": json.dumps({"issues": [_issue()]})},
    )

    issues = namespace["_search_issues"](wf, "labels = Linux-A9_Yocto")

    assert [issue["key"] for issue in issues] == ["A9-1"]


class _Step:
    def __init__(self, workflow, step_id, title):
        self.workflow = workflow
        self.step_id = step_id
        self.title = title

    def __enter__(self):
        self.workflow.steps.append((self.step_id, self.title))

    def __exit__(self, *_):
        return False


class FakeWorkflow:
    def __init__(
        self, tmp_path: Path, *, inputs=None, jira_results=None, files=None,
        chart_results=None,
    ):
        self.tmp_path = tmp_path
        self.inputs = inputs or {}
        self.jira_results = list(jira_results or [])
        self.files = {
            "charts/status.png": "\x89PNG\r\n\x1a\ndefault-pie",
            "charts/trend.png": "\x89PNG\r\n\x1a\ndefault-line",
        }
        self.files.update(files or {})
        self.chart_results = chart_results or {
            "chart_render_pie": "Success: pie chart saved to charts/status.png (200x200)",
            "chart_render_line": "Success: line chart saved to charts/trend.png (640x320)",
        }
        self.input_calls = []
        self.tool_calls = []
        self.read_calls = []
        self.write_calls = []
        self.artifacts = []
        self.steps = []
        self.outputs = {}
        self.logs = []
        self.events = []

    def input(self, name, default=None, description=None):
        self.input_calls.append((name, default, description))
        return self.inputs.get(name, default)

    def call_tool(self, name, **arguments):
        self.tool_calls.append((name, arguments))
        self.events.append(("tool", name))
        if name == "jira_search_issues":
            result = self.jira_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        if name == "email_send_html":
            return {"sent": True}
        if name in self.chart_results:
            result = self.chart_results[name]
            if isinstance(result, Exception):
                raise result
            return result
        raise AssertionError(f"unexpected tool: {name}")

    def read_file(self, path):
        self.read_calls.append(path)
        result = self.files[path]
        if isinstance(result, Exception):
            raise result
        return result

    def write_file(self, path, content):
        self.write_calls.append((path, content))
        self.events.append(("write", path))
        (self.tmp_path / path).write_text(content, encoding="utf-8")

    def emit_artifact(self, path):
        self.artifacts.append(path)

    def step(self, step_id, title):
        return _Step(self, step_id, title)

    def set_output(self, name, value):
        self.outputs[name] = value

    def log(self, message, level="info"):
        self.logs.append((level, message))


def _issue(key="A9-1", **fields):
    complete = {
        "summary": "Boot smoke failure",
        "status": {"name": "Open"},
        "assignee": {"displayName": "Engineer"},
        "priority": {"name": "P0"},
        "components": [{"name": "Kernel"}],
        "labels": ["Linux-A9_Yocto"],
        "created": "2026-08-11T01:00:00+00:00",
        "updated": "2026-08-10T01:00:00+00:00",
    }
    complete.update(fields)
    return {"key": key, "fields": complete}


def test_native_png_charts_are_embedded_in_the_only_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={"send_email": True, "trend_days": 3},
        files={
            "charts/status.png": "\x89PNG\r\n\x1a\npie-png",
            "charts/trend.png": "\x89PNG\r\n\x1a\nline-png",
        },
        jira_results=[
            {"issues": [_issue("A9-1"), _issue("A9-2", status={"name": "Resolved"})]},
            {"issues": [_issue("A9-1")]},
            {"issues": [_issue("A9-1"), _issue("A9-2"), _issue("A9-3")]},
        ],
    )

    report_path = workflow.main(wf)

    assert report_path == "a9-yocto-daily-report.html"
    assert [path for path, _ in wf.write_calls] == [report_path]
    html = (tmp_path / report_path).read_text("utf-8")
    assert 'src="data:image/png;base64,iVBORw0KGgpwaWUtcG5n"' in html
    assert 'src="data:image/png;base64,iVBORw0KGgpsaW5lLXBuZw=="' in html
    assert 'class="donut-ring"' not in html
    assert 'class="trend-line"' not in html
    assert wf.read_calls[-2:] == ["charts/status.png", "charts/trend.png"]
    pie = next(args for name, args in wf.tool_calls if name == "chart_render_pie")
    line = next(args for name, args in wf.tool_calls if name == "chart_render_line")
    assert pie["segments"] == [
        {"label": "Open", "value": 1}, {"label": "Resolved", "value": 1}
    ]
    assert line["series"] == [{"label": "未关闭 Issue", "values": [3, 1, 2]}]
    assert wf.tool_calls[-1][0] == "email_send_html"
    assert wf.tool_calls[-1][1]["file_path"] == report_path


def test_existing_data_uri_and_plain_base64_png_are_recognized_without_reencoding(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    png_base64 = "iVBORw0KGgo="
    wf = FakeWorkflow(
        tmp_path,
        inputs={"trend_days": 2},
        files={
            "charts/status.png": "data:image/png;base64," + png_base64,
            "charts/trend.png": png_base64,
        },
        jira_results=[{"issues": [_issue()]}, {"issues": [_issue()]}],
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert html.count('src="data:image/png;base64,' + png_base64 + '"') == 2


@pytest.mark.parametrize(
    "chart_results,files,error",
    [
        ({"chart_render_pie": RuntimeError("pie failed")}, {}, "pie failed"),
        (
            {
                "chart_render_pie": "Success: pie chart saved to charts/status.png",
                "chart_render_line": "Success: line chart saved to charts/trend.png",
            },
            {"charts/trend.png": RuntimeError("trend binary unavailable")},
            "trend binary unavailable",
        ),
    ],
)
def test_chart_generation_or_binary_read_failure_writes_nothing_and_does_not_send(
    tmp_path, monkeypatch, chart_results, files, error
):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={"send_email": True, "trend_days": 2},
        chart_results=chart_results,
        files=files,
        jira_results=[{"issues": [_issue()]}, {"issues": [_issue()]}],
    )

    with pytest.raises((RuntimeError, KeyError), match=error.replace("/", r"\/")):
        workflow.main(wf)

    assert wf.write_calls == []
    assert all(name != "email_send_html" for name, _ in wf.tool_calls)


def test_unsafe_chart_path_is_rejected_before_read_write_or_send(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={"send_email": True, "trend_days": 2},
        chart_results={
            "chart_render_pie": "Success: pie chart saved to charts/../secret.png"
        },
        jira_results=[{"issues": [_issue()]}, {"issues": [_issue()]}],
    )

    with pytest.raises(RuntimeError, match="safe PNG path"):
        workflow.main(wf)

    assert all(not path.startswith("charts/") for path in wf.read_calls)
    assert wf.write_calls == []
    assert all(name != "email_send_html" for name, _ in wf.tool_calls)


def test_main_uses_defaults_queries_current_and_history_and_keeps_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    today = date.today()
    wf = FakeWorkflow(
        tmp_path,
        jira_results=[{"issues": [_issue()]}] + [{"issues": []}] * 13,
    )

    artifact = workflow.main(wf)

    assert Path(artifact).is_file()
    html = Path(artifact).read_text("utf-8")
    assert "A9 Yocto 公版状态日报" in html
    assert "当前未关闭" in html and "14 日未关闭趋势" in html
    assert "A9-1" in html and "Boot smoke failure" in html
    assert wf.tool_calls[0] == (
        "jira_search_issues",
        {"jql": "status not in (Closed, Done, Verified) AND labels = Linux-A9_Yocto"},
    )
    jira_calls = [call for call in wf.tool_calls if call[0] == "jira_search_issues"]
    assert [call[1]["jql"] for call in jira_calls[1:]] == [
        f'status WAS NOT IN (Closed, Done, Verified) ON "{(today - timedelta(days=offset)).isoformat()}" AND labels = Linux-A9_Yocto'
        for offset in range(1, 14)
    ]
    assert all(name != "email_send_html" for name, _ in wf.tool_calls)
    defaults = {name: default for name, default, _ in wf.input_calls}
    assert defaults["recipients"] == "chao.li@amlogic.com"
    assert defaults["cc"] == ""
    assert defaults["send_email"] is False
    assert len(wf.input_calls) == 10
    assert all(description for _, _, description in wf.input_calls)
    assert wf.write_calls[0][0] == "a9-yocto-daily-report.html"
    assert wf.artifacts == ["a9-yocto-daily-report.html"]
    assert wf.outputs == {
        "report_path": "a9-yocto-daily-report.html",
        "total": 1,
    }
    assert wf.steps == [
        ("n0", "读取并校验配置"),
        ("n1", "查询当前 Jira Issue"),
        ("n2", "查询历史趋势"),
        ("n3", "生成并发布 HTML 日报"),
    ]


def test_jira_summary_pages_are_loaded_through_workbench_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={"trend_days": 2},
        jira_results=[
            "找到相关问题，search_id: current_123，分为 2 页",
            "未找到匹配问题，共 0 个问题",
        ],
        files={
            "jira/current_123/page_1.json": json.dumps({"issues": [_issue("A9-1")]}),
            "jira/current_123/page_2.json": json.dumps({"issues": [_issue("A9-2")]}),
        },
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert wf.read_calls[:2] == [
        "jira/current_123/page_1.json",
        "jira/current_123/page_2.json",
    ]
    assert "A9-1" in html and "A9-2" in html


def test_jira_summary_without_page_count_defaults_to_first_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={"trend_days": 2},
        jira_results=[
            "Jira 查询完成，search_id: single_page",
            "未找到匹配问题，共 0 个问题",
        ],
        files={
            "jira/single_page/page_1.json": json.dumps({"issues": [_issue("A9-3")]}),
        },
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert wf.read_calls[0] == "jira/single_page/page_1.json"
    assert "A9-3" in html


def test_report_restores_smarttest_sections_panels_and_native_status_chart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    issues = [
        _issue("A9-1", status={"name": "Open"}),
        _issue("A9-2", status={"name": "Resolved"}, priority={"name": "P1"}),
        _issue("A9-3", status={"name": "In Progress"}, priority={"name": "P2"}),
    ]
    wf = FakeWorkflow(
        tmp_path,
        inputs={"trend_days": 2},
        jira_results=[{"issues": issues}, {"issues": []}],
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert 'class="report-canvas"' in html
    assert 'class="hero"' in html and 'class="eyebrow"' in html
    assert "DAILY PROJECT INTELLIGENCE" in html
    assert "01 数据全景" in html
    assert html.count('class="metric-card"') == 4
    for title in ("优先级 / 停滞", "状态构成", "模块分布 · Top 5", "问题内外部"):
        assert title in html
    assert 'data-chart="status-composition"' in html
    assert 'src="data:image/png;base64,' in html
    assert html.count('class="status-legend-item"') == 3
    assert "02 Issue 明细" in html
    assert "03 口径与附件" in html
    assert "不生成附件" in html and "Excel" not in html
    assert html.count("<img") == 2


def test_status_chart_limits_legend_and_escapes_dynamic_labels(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    issues = [
        _issue(f"A9-{index}", status={"name": label}, priority={"name": "P2"})
        for index, label in enumerate(
            ("<Open&>", "Resolved", "In Progress", "To Do", "Reopened", "Blocked", "Extra"),
            start=1,
        )
    ]
    wf = FakeWorkflow(
        tmp_path,
        inputs={"trend_days": 2},
        jira_results=[{"issues": issues}, {"issues": []}],
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert html.count('class="status-legend-item"') == 6
    assert "&lt;Open&amp;&gt;" in html
    assert "<Open&>" not in html


def test_main_normalizes_flat_field_variants_and_renders_deterministic_metrics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    flat_issue = {
        "key": "A9-2",
        "summary": "Codec <failure>",
        "status": "In Progress",
        "assignee": {"name": "Owner"},
        "priority": {"value": "P1"},
        "components": "Media",
        "created": date.today().isoformat(),
        "updated": "not-a-date",
        "url": "https://jira.example/browse/A9-2?x=1&y=2",
    }
    wf = FakeWorkflow(
        tmp_path,
        inputs={"project_name": "A9 Yocto"},
        jira_results=[[flat_issue]] + [[]] * 13,
    )

    artifact = Path(workflow.main(wf))

    html = artifact.read_text("utf-8")
    assert "Codec &lt;failure&gt;" in html
    assert "In Progress" in html and "Media" in html
    assert "https://jira.example/browse/A9-2?x=1&amp;y=2" in html
    stale_card = html[html.index('data-metric="stale"') :][:300]
    assert "停滞 ≥ 7 天" in stale_card
    assert '<div class="metric-value">1</div>' in stale_card
    assert html.count("<img") == 2 and ".xlsx" not in html


def test_component_count_queries_split_comma_joined_component_strings(tmp_path):
    wf = FakeWorkflow(
        tmp_path,
        jira_results=[{"issues": []}, {"issues": []}],
    )
    issues = workflow._records([_issue(components="Audio(AQ), Audio(Driver)")])

    counts = workflow._server_component_counts(wf, 'labels = "BDS_IFPD"', issues)

    assert counts == [("Audio(AQ)", 0), ("Audio(Driver)", 0)]
    jira_calls = [args["jql"] for name, args in wf.tool_calls if name == "jira_search_issues"]
    assert jira_calls == [
        '(labels = "BDS_IFPD") AND component = "Audio(AQ)"',
        '(labels = "BDS_IFPD") AND component = "Audio(Driver)"',
    ]


def test_empty_current_result_still_produces_complete_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(tmp_path, jira_results=[{"issues": []}] * 14)

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert "当前无 Issue" in html
    assert "当前未关闭" in html
    assert 'data-chart="status-composition"' in html
    assert "暂无状态数据" in html


def test_detail_priorities_override_controls_rows_and_visible_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p2 = _issue("A9-2", priority={"name": "P2"}, summary="Configured detail")
    wf = FakeWorkflow(
        tmp_path,
        inputs={"detail_priorities": "P2", "trend_days": 2},
        jira_results=[{"issues": [_issue(), p2]}, {"issues": []}],
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert "展示优先级：P2" in html
    assert "Configured detail" in html
    assert "Boot smoke failure" not in html


def test_history_failure_marks_missing_point_and_continues(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        jira_results=[{"issues": [_issue()]} , RuntimeError("history unavailable")]
        + [{"issues": []}] * 12,
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert "缺失" in html
    assert len([call for call in wf.tool_calls if call[0] == "jira_search_issues"]) == 14


def test_malformed_current_search_summary_fails_without_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(tmp_path, inputs={"trend_days": 2}, jira_results=["search completed"])

    with pytest.raises(ValueError, match="search response"):
        workflow.main(wf)

    assert wf.write_calls == [] and wf.artifacts == []


def test_malformed_history_search_summary_becomes_missing_point(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={"trend_days": 2},
        jira_results=["未找到匹配问题，共 0 个问题", "history response malformed"],
    )

    html = Path(workflow.main(wf)).read_text("utf-8")

    assert "缺失" in html


def test_current_query_failure_does_not_create_or_send_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(tmp_path, inputs={"send_email": True}, jira_results=[RuntimeError("current unavailable")])

    with pytest.raises(RuntimeError, match="current unavailable"):
        workflow.main(wf)

    assert not (tmp_path / "a9-yocto-daily-report.html").exists()
    assert [name for name, _ in wf.tool_calls] == ["jira_search_issues"]


@pytest.mark.parametrize(
    "inputs",
    [
        {"project_name": " "},
        {"project_label": ""},
        {"jql": ""},
        {"subject": ""},
        {"recipients": "not-an-email"},
        {"cc": "valid@example.com,broken"},
        {"detail_priorities": ""},
        {"trend_days": 1},
        {"trend_days": 366},
        {"trend_days": 2.5},
        {"stale_days": 0},
        {"send_email": "sometimes"},
    ],
)
def test_invalid_inputs_fail_before_any_external_tool_call(tmp_path, monkeypatch, inputs):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(tmp_path, inputs=inputs)

    with pytest.raises(ValueError):
        workflow.main(wf)

    assert wf.tool_calls == []


def test_send_email_true_uses_only_html_tool_and_includes_nonempty_cc(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    wf = FakeWorkflow(
        tmp_path,
        inputs={
            "recipients": "first@example.com; second@example.com",
            "cc": "copy@example.com",
            "subject": "Daily status",
            "send_email": "true",
            "trend_days": 2,
        },
        jira_results=[{"issues": []}, {"issues": []}],
    )

    artifact = workflow.main(wf)

    assert wf.tool_calls[-1] == (
        "email_send_html",
        {
            "recipients": "first@example.com,second@example.com",
            "subject": "Daily status",
            "file_path": "a9-yocto-daily-report.html",
            "add_footer": False,
            "cc_addresses": "copy@example.com",
        },
    )
    assert artifact == "a9-yocto-daily-report.html"
    assert [event for event in wf.events if event[0] == "write"] == [
        ("write", "a9-yocto-daily-report.html"),
    ]
    assert wf.events.index(("write", "a9-yocto-daily-report.html")) < wf.events.index(
        ("tool", "email_send_html")
    )
    assert wf.steps[-1] == ("n4", "发送 HTML 日报")


def test_send_email_omits_empty_cc_and_preserves_artifact_when_send_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class FailingEmailWorkflow(FakeWorkflow):
        def call_tool(self, name, **arguments):
            if name == "email_send_html":
                self.tool_calls.append((name, arguments))
                raise RuntimeError("send rejected")
            return super().call_tool(name, **arguments)

    wf = FailingEmailWorkflow(
        tmp_path,
        inputs={"send_email": True, "trend_days": 2},
        jira_results=[{"issues": []}, {"issues": []}],
    )

    with pytest.raises(RuntimeError, match="send rejected"):
        workflow.main(wf)

    assert (tmp_path / "a9-yocto-daily-report.html").is_file()
    assert not (tmp_path / "a9-yocto-daily-report-mail.html").exists()
    assert "cc_addresses" not in wf.tool_calls[-1][1]
