from datetime import date
import re

import pytest

from .daily_report_workflow import _names, _render_html, _search_issues


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
    assert "height:auto" in status_tag
