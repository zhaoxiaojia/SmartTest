from jira_tool.fields.extractors import extract_path, parse_path, project_fields
from jira_tool.fields.specs import FieldSpec


ISSUE_SAMPLE = {
    "key": "ST-1",
    "fields": {
        "summary": "Example summary",
        "status": {"name": "In Progress"},
        "assignee": {"displayName": "Alex"},
        "fixVersions": [{"name": "1.0.0"}, {"name": "1.0.1"}],
        "customfield_12345": {"value": "Wi-Fi"},
    },
    "changelog": {
        "histories": [
            {"items": [{"field": "status", "toString": "In Progress"}]},
            {"items": [{"field": "status", "toString": "Verified"}]},
        ]
    },
}


def test_parse_path_supports_iterable_segments() -> None:
    tokens = parse_path("fields.fixVersions[].name")
    assert [token.key for token in tokens] == ["fields", "fixVersions", "name"]
    assert [token.iterate for token in tokens] == [False, True, False]


def test_extract_path_reads_scalar_nested_value() -> None:
    assert extract_path(ISSUE_SAMPLE, "fields.status.name") == "In Progress"


def test_extract_path_reads_iterable_nested_values() -> None:
    assert extract_path(ISSUE_SAMPLE, "fields.fixVersions[].name") == ["1.0.0", "1.0.1"]


def test_extract_path_reads_deep_history_values() -> None:
    assert extract_path(ISSUE_SAMPLE, "changelog.histories[].items[].toString") == ["In Progress", "Verified"]


def test_project_fields_applies_defaults_and_names() -> None:
    specs = [
        FieldSpec(name="summary", path="fields.summary"),
        FieldSpec(name="component", path="fields.customfield_missing.value", default=""),
        FieldSpec(name="domain", path="fields.customfield_12345.value"),
    ]
    projected = project_fields(ISSUE_SAMPLE, specs)
    assert projected == {"summary": "Example summary", "component": "", "domain": "Wi-Fi"}
