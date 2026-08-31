from __future__ import annotations

import pytest

from core.domain.detail import DetailState
from core.jira.gateway import JiraGateway
from core.jira.presenter import record_to_issue_row
from core.jira.services.issue_service import JiraIssueService
from core.tools.common.daily_report.report import records_to_issues


class StandardFieldApi:
    def __init__(self, resolution):
        self.resolution = resolution
        self.calls = []

    def payload(self, fields):
        available = {
            "summary": "Standard fields", "components": [{"id": "10", "name": "Video"}],
            "resolution": self.resolution, "project": {"key": "SH"},
            "status": {"name": "Closed"}, "issuetype": {"name": "Bug"},
        }
        return {"id": "1", "key": "SH-1", "fields": {
            key: value for key, value in available.items() if key in fields
        }}

    def jql(self, query, *, fields, start, limit, **kwargs):
        self.calls.append(("search", fields))
        return {"issues": [self.payload(fields)], "startAt": start, "total": 1, "maxResults": limit}

    def get_issue(self, key, *, fields=None, **kwargs):
        self.calls.append(("get", fields))
        return self.payload(fields or [])


@pytest.mark.parametrize("resolution,expected", [({"id": "1", "name": "Fixed"}, "Fixed"), (None, "")])
def test_standard_fields_reach_presenter_and_daily_report_without_custom_fetch(resolution, expected):
    api = StandardFieldApi(resolution)
    service = JiraIssueService(JiraGateway("https://jira.example", "u", "p", api=api))

    records = service.search_records("project = SH", specs=("components", "resolution"))

    row = record_to_issue_row(records[0])
    assert row["components"] == ["Video"]
    assert row["resolution"] == expected
    assert records_to_issues(records)[0].components == ("Video",)
    assert records[0].custom_fields.state is DetailState.UNLOADED
    assert len(api.calls) == 1

    issue = service.hydrate_issue("SH-1", specs=("components", "resolution"))
    assert record_to_issue_row(issue)["resolution"] == expected
    assert issue.custom_fields.state is DetailState.UNLOADED
    assert len(api.calls) == 2
