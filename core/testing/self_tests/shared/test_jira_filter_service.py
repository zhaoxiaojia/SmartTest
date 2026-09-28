from core.jira.services.filter_service import JiraFilterService
from datetime import date
import pytest


@pytest.mark.parametrize(("draft", "expected"), [
    ("", 'channel = "Self-Test"'),
    ('project = A OR project = B ORDER BY created DESC',
     '(project = A OR project = B) AND (channel = "Self-Test") ORDER BY created DESC'),
    ('text ~ "ORDER BY \\"quoted\\"" order by priority ASC',
     '(text ~ "ORDER BY \\"quoted\\"") AND (channel = "Self-Test") order by priority ASC'),
    ("ORDER BY created DESC", 'channel = "Self-Test" ORDER BY created DESC'),
])
def test_fixed_conditions_intersect_user_predicate_without_corrupting_order_or_literals(draft, expected):
    from core.jira.services.filter_service import compose_jql
    assert compose_jql(draft, 'channel = "Self-Test"') == expected


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


def test_year_period_starts_on_current_january_first_and_excludes_prior_december_31():
    from core.jira.services.filter_service import jira_period_condition

    condition = jira_period_condition("year", date(2026, 9, 21))

    assert condition == 'created >= "2026-01-01" AND created <= now()'
    assert "2025-12-31" not in condition


@pytest.mark.parametrize(("today", "quarter_start"), [
    (date(2026, 1, 1), "2026-01-01"),
    (date(2026, 4, 30), "2026-04-01"),
    (date(2026, 9, 24), "2026-07-01"),
    (date(2026, 12, 31), "2026-10-01"),
])
def test_quarter_period_starts_on_the_current_calendar_quarter(today, quarter_start):
    from core.jira.services.filter_service import jira_period_condition

    assert jira_period_condition("quarter", today) == (
        f'created >= "{quarter_start}" AND created <= now()'
    )


@pytest.mark.parametrize(("period", "today", "current_start", "previous_start"), [
    ("week", date(2026, 9, 24), "2026-09-21", "2026-09-14"),
    ("week", date(2026, 9, 21), "2026-09-21", "2026-09-14"),
    ("month", date(2026, 3, 1), "2026-03-01", "2026-02-01"),
    ("quarter", date(2026, 1, 1), "2026-01-01", "2025-10-01"),
    ("year", date(2024, 2, 29), "2024-01-01", "2023-01-01"),
])
def test_natural_period_pair_has_adjacent_left_closed_right_open_ranges(
    period, today, current_start, previous_start,
):
    from core.jira.services.filter_service import jira_period_ranges

    assert jira_period_ranges(period, today) == {
        "current": {"start": current_start, "end": None,
                    "condition": f'created >= "{current_start}" AND created <= now()'},
        "previous": {"start": previous_start, "end": current_start,
                     "condition": f'created >= "{previous_start}" AND created < "{current_start}"'},
    }
