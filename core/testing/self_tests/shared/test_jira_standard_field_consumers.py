from __future__ import annotations

from datetime import date

import pytest

from core.domain.detail import DetailState
from core.jira.gateway import JiraGateway
from core.jira.services.issue_service import JiraIssueService
from core.tools.common.daily_report.report import records_to_issues
from core.tools.common.daily_report import PROJECTS, DailyReportService


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


@pytest.mark.parametrize("resolution,expected", [({"id": "1", "name": "Fixed"}, "Fixed"), (None, "")])
def test_standard_fields_reach_daily_report_without_registry_or_custom_fetch(resolution, expected):
    api = StandardFieldApi(resolution)
    service = JiraIssueService(JiraGateway("https://jira.example", "u", "p", api=api))

    records = service.search_records("project = SH")

    assert [component.name for component in records[0].components] == ["Video"]
    assert (records[0].resolution.name if records[0].resolution else "") == expected
    assert records_to_issues(records)[0].components == ("Video",)
    assert records[0].custom_fields.state is DetailState.UNLOADED
    assert len(api.calls) == 1


def test_daily_preview_uses_lightweight_issue_service_for_current_and_history(tmp_path):
    api = StandardFieldApi(None)
    issue_service = JiraIssueService(JiraGateway("https://jira.example", "u", "p", api=api))

    class OneProject:
        def enabled(self):
            return (PROJECTS[0],)

    service = DailyReportService(
        issue_service_factory=lambda _username, _password: issue_service,
        project_store=OneProject(), report_root=tmp_path,
        today=lambda: date(2026, 8, 31),
        logger=lambda *_args, **_kwargs: None,
    )

    batch = service.preview("u", "p")

    assert batch.failures == ()
    assert len(batch.reports) == 1
    assert batch.reports[0].history_failures == ()
    assert batch.reports[0].artifacts.html_path.is_file()
    assert len(api.calls) == 14
    assert all(call[0] == "search" for call in api.calls)
