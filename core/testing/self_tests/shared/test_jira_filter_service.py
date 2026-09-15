from core.jira.services.filter_service import JiraFilterService


class Gateway:
    def fetch_query_fields(self):
        return {"visibleFieldNames": [
            {"value": "status", "displayName": "Status", "types": ["com.atlassian.jira.issue.status.Status"], "operators": ["=", "IN"]},
            {"value": "customfield_1", "displayName": "Team", "types": ["com.atlassian.jira.issue.customfields.option.Option"], "operators": ["=", "IN"]},
            {"value": "customfield_2", "displayName": "Cascade", "types": ["com.atlassian.jira.issue.customfields.option.CascadingOption"], "operators": ["="]},
        ]}

    def fetch_saved_filters(self):
        return [{"id": "7", "name": "Mine", "jql": "project = SH", "owner": {"displayName": "User"}}]

    def fetch_filter(self, filter_id):
        return {"id": filter_id, "name": "Mine", "jql": "project = SH"}

    def validate_jql(self, jql):
        return {"valid": bool(jql), "errors": [] if jql else ["JQL is required"]}

    def fetch_query_suggestions(self, field_name, query):
        assert (field_name, query) == ("status", "op")
        return {"results": [
            {"value": "1", "displayName": "Open", "extra": "ignored"},
            {"value": "2", "displayName": "In Progress"},
            {"displayName": "missing value"},
        ]}


def test_normalizes_query_fields_and_marks_unproven_candidates_advanced_only():
    service = JiraFilterService(Gateway())

    fields = service.fields()

    assert fields[0]["control"] == "multi"
    assert fields[0]["queryable"] is True
    assert fields[1]["control"] == "advanced"
    assert fields[1]["queryable"] is False
    assert fields[2]["control"] == "advanced"


def test_saved_filters_are_projected_without_write_capabilities():
    service = JiraFilterService(Gateway())

    assert service.saved_filters() == [{"id": "7", "name": "Mine", "owner": "User"}]
    assert service.saved_filter("7") == {"id": "7", "name": "Mine", "jql": "project = SH"}
    assert service.validate("project = SH")["valid"] is True


def test_suggestions_preserve_only_jira_value_and_display_name():
    service = JiraFilterService(Gateway())

    assert service.suggestions("status", "op") == [
        {"value": "1", "displayName": "Open"},
        {"value": "2", "displayName": "In Progress"},
    ]
