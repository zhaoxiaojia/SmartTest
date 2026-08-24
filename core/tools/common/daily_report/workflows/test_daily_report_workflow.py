import pytest

from .daily_report_workflow import _names, _search_issues


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
