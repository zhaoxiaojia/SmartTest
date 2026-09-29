from datetime import date
from contextlib import nullcontext
import re

import pytest

from .daily_report_workflow import (
    _names,
    _render_html,
    _search_issues,
    _status_legend,
    main,
)


def test_names_splits_comma_separated_components():
    assert _names("Audio(AQ), Audio(Driver), Audio(DSP)") == (
        "Audio(AQ)",
        "Audio(Driver)",
        "Audio(DSP)",
    )


def test_names_ignores_unset_component_marker():
    assert _names("Audio(AQ), None") == ("Audio(AQ)",)
    assert _names("None") == ()


def test_search_error_includes_jql_and_original_response():
    class Workflow:
        def call_tool(self, tool_name, **arguments):
            assert tool_name == "jira_search_issues"
            return "The component value does not exist"

    jql = 'labels = BDS_IFPD AND component = "missing"'

    with pytest.raises(ValueError) as error:
        _search_issues(Workflow(), jql)

    message = str(error.value)
    assert jql in message
    assert "The component value does not exist" in message


def test_status_chart_preserves_the_rendered_image_aspect_ratio():
    html = _render_html(
        {
            "project_name": "A9 Yocto",
            "jql": "labels = Linux-A9_Yocto",
            "stale_days": 7,
            "trend_days": 14,
            "detail_priorities": ["P0", "P1"],
        },
        [],
        [],
        date(2026, 9, 3),
        "data:image/png;base64,status",
        "data:image/png;base64,trend",
    )

    status_tag = re.search(
        r'<img data-chart="status-composition"[^>]+>', html
    ).group(0)

    assert 'width="200"' not in status_tag
    assert 'height="200"' not in status_tag
    assert "height:200px" in status_tag
    assert "width:auto" in status_tag
    assert 'class="status-chart-crop"' in html


def test_status_legend_displays_status_names_and_percentages():
    legend = _status_legend(
        (("To Do", 18), ("In Progress", 18), ("Resolved", 13), ("Open", 10))
    )

    assert ["To Do", "In Progress", "Resolved", "Open"] == re.findall(
        r'<td class="status-name">([^<]+)</td>', legend
    )
    assert ["30.5%", "30.5%", "22.0%", "16.9%"] == re.findall(
        r'<td class="status-percentage">([^<]+)</td>', legend
    )


def test_summary_cards_use_today_transitions_instead_of_current_status_totals():
    issues = [
        {
            "key": key,
            "summary": key,
            "status": status,
            "priority": "P0",
            "assignee": "Engineer",
            "components": (),
            "created": None,
            "updated": None,
            "url": "",
        }
        for key, status in (
            ("A9-1", "Resolved"),
            ("A9-2", "Resolved"),
            ("A9-3", "Closed"),
            ("A9-4", "Open"),
        )
    ]
    html = _render_html(
        {
            "project_name": "A9 Yocto",
            "jql": "labels = Linux-A9_Yocto",
            "stale_days": 7,
            "trend_days": 14,
            "detail_priorities": ["P0", "P1"],
        },
        issues,
        [],
        date(2026, 9, 3),
        "status",
        "trend",
        resolved_today_keys={"A9-5"},
        closed_today_keys={"A9-6", "A9-7"},
    )

    resolved = re.search(
        r'data-metric="resolved".*?<div class="metric-value">(\d+)</div>', html
    )
    closed = re.search(
        r'data-metric="closed".*?<div class="metric-value">(\d+)</div>', html
    )
    assert resolved and resolved.group(1) == "1"
    assert closed and closed.group(1) == "2"
    assert "今日解决" in html and "今日关闭" in html
    assert "当天转为 Resolved" in html and "当天转为 Closed" in html
    assert 'data-metric="p0"' not in html
    assert 'data-metric="stale"' not in html


def test_summary_cards_show_zero_when_resolved_and_closed_are_absent():
    html = _render_html(
        {
            "project_name": "A9 Yocto",
            "jql": "labels = Linux-A9_Yocto",
            "stale_days": 7,
            "trend_days": 14,
            "detail_priorities": ["P0", "P1"],
        },
        [],
        [],
        date(2026, 9, 3),
        "status",
        "trend",
    )

    assert re.search(
        r'data-metric="resolved".*?<div class="metric-value">0</div>', html
    )
    assert re.search(
        r'data-metric="closed".*?<div class="metric-value">0</div>', html
    )


@pytest.mark.parametrize("base, transition_scope", [
    (
        "status not in (Closed, Done, Verified) AND labels = Linux-A9_Yocto",
        '{condition} AND labels = Linux-A9_Yocto',
    ),
    (
        'project = A9 AND labels = Linux-A9_Yocto',
        '(project = A9 AND labels = Linux-A9_Yocto) AND {condition}',
    ),
])
def test_main_counts_today_transitions_outside_current_results(base, transition_scope):
    resolved_jql = transition_scope.format(
        condition='status CHANGED TO "Resolved" AFTER startOfDay()'
    )
    closed_jql = transition_scope.format(
        condition='status CHANGED TO "Closed" AFTER startOfDay()'
    )

    class Workflow:
        def __init__(self):
            self.queries = []
            self.html = ""

        def input(self, name, default=None, description=None):
            return {"project_name": "A9", "jql": base, "trend_days": 2,
                    "send_email": False}.get(name, default)

        def step(self, *_):
            return nullcontext()

        def call_tool(self, name, **arguments):
            if name == "jira_search_issues":
                query = arguments["jql"]
                self.queries.append(query)
                # Jira returns only issues whose transition happened today;
                # current results need not contain these now-closed issues.
                return {resolved_jql: [{"key": "A9-1"}],
                        closed_jql: [{"key": "A9-2"}, {"key": "A9-3"}]}.get(query, [])
            assert name in ("chart_render_pie", "chart_render_line")
            return "Success: chart saved to charts/report.png"

        def read_file(self, path):
            assert path == "charts/report.png"
            return "data:image/png;base64,iVBORw0KGgo="

        def write_file(self, path, content):
            self.html = content

        def emit_artifact(self, path):
            pass

        def set_output(self, name, value):
            pass

    wf = Workflow()
    main(wf)

    assert resolved_jql in wf.queries
    assert closed_jql in wf.queries
    assert f"({base}) AND created >= startOfDay()" in wf.queries
    assert f"({base}) AND updated >= startOfDay()" in wf.queries
    assert re.findall(r'data-metric="[^"]+".*?<div class="metric-value">(\d+)</div>', wf.html) == ["0", "0", "1", "2"]
