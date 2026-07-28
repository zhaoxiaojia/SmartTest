from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

import pytest
from openpyxl import load_workbook

from support.jira_integration.audit import (
    AuditReport,
    JiraAuditService,
    ResolvedAuditInput,
    active_rules,
    audit_issue,
    export_audit_xlsx,
    resolve_audit_input,
)
from support.jira_integration.audit.rules import ai_reviewable_violations
from support.jira_integration.core.models import SearchPage


RULE_IDS = tuple(
    """
    SUMMARY.FORMAT SUMMARY.CUSTOMER SUMMARY.CHIP SUMMARY.VERSION
    SUMMARY.CUSTOMER_ENGLISH
    SUMMARY.DESCRIPTION_ENGLISH SUMMARY.PROBABILITY COMPONENT.REQUIRED
    DESCRIPTION.STEPS_TO_REPRODUCE DESCRIPTION.ACTUAL_RESULTS
    DESCRIPTION.EXPECTED_RESULTS DESCRIPTION.COMPARISON DESCRIPTION.NOTES
    DESCRIPTION.RATE_FORMAT DESCRIPTION.NOTES_HW DESCRIPTION.NOTES_SW
    REGRESSION.EVIDENCE
    """.split()
)


def _description(
    *,
    steps="1. Start playback.\n2. Seek to 00:30.",
    actual="Video freezes.",
    expected="Playback continues.",
    rate="2/2",
    comparison="Previous version V1.0 is normal; current version V1.1 is broken.",
    notes="HW info: T7 reference board\nSW info: V1.1",
):
    values = (
        ("Steps to reproduce", steps),
        ("Actual results", actual),
        ("Expected results", expected),
        ("Reproducibility rate", rate),
        ("Comparison", comparison),
        ("Notes", notes),
    )
    return "\n".join(f"[{heading}]:\n{value}" for heading, value in values)


def _issue(
    key="SH-123",
    *,
    summary="[ACME][T7][V1.1][Video]: Video freezes after seeking,2/2",
    description=None,
    components=("Video",),
    labels=("regression",),
):
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": _description() if description is None else description,
            "reporter": {"displayName": "Coco"},
            "components": [{"name": value} for value in components],
            "labels": list(labels),
        },
    }


def _violations(**changes):
    return {
        item.rule_id
        for item in audit_issue(_issue(**changes), base_url="https://jira.example.com").violations
    }


def test_complete_issue_accepts_four_five_and_six_summary_groups():
    summaries = (
        "[ACME][T7][V1.1][Video]: Video freezes,50%",
        "[SH-1][ACME][T7][V1.1][Video]: Video freezes,1/2",
        "[SH-1][BUG-2][ACME][T7][V1.1][Video]: Video freezes,100%.",
        "【ACME】 [T7] 【V1.1】 [Video]： Video freezes,50%",
    )

    assert tuple(rule.rule_id for rule in active_rules()) == RULE_IDS
    assert all(audit_issue(_issue(summary=value), base_url="https://jira.example.com").passed
               for value in summaries)


EMPTY_DESCRIPTION = _description(
    steps="",
    actual="",
    expected="",
    rate="",
    comparison="",
    notes="",
)


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({"summary": "invalid"}, {"SUMMARY.FORMAT"}),
        (
            {"summary": "[ ][ ][ ][Video]: Video freezes,50%"},
            {"SUMMARY.FORMAT"},
        ),
        ({"summary": "[客户][T7][V1][Video]: 播放冻结,50%"},
         {"SUMMARY.CUSTOMER_ENGLISH", "SUMMARY.DESCRIPTION_ENGLISH"}),
        (
            {"summary": "[ACME][T7][V1][Video]: Video freezes,3/2"},
            {"SUMMARY.PROBABILITY"},
        ),
        ({"components": ()}, {"COMPONENT.REQUIRED"}),
        (
            {"description": EMPTY_DESCRIPTION, "labels": ()},
            {
                "DESCRIPTION.STEPS_TO_REPRODUCE",
                "DESCRIPTION.ACTUAL_RESULTS",
                "DESCRIPTION.EXPECTED_RESULTS",
                "DESCRIPTION.COMPARISON",
                "DESCRIPTION.NOTES",
                "DESCRIPTION.NOTES_HW",
                "DESCRIPTION.NOTES_SW",
            },
        ),
        (
            {
                "description": _description(
                    rate="3/2",
                    notes="HW info:\nSW info:",
                ),
                "labels": (),
            },
            {
                "DESCRIPTION.RATE_FORMAT",
                "DESCRIPTION.NOTES_HW",
                "DESCRIPTION.NOTES_SW",
            },
        ),
        ({"description": _description(comparison="V1 and V2 compared.")},
         {"REGRESSION.EVIDENCE"}),
    ),
)
def test_rule_failure_matrix(changes, expected):
    assert expected == _violations(**changes)


def test_legacy_comparision_heading_is_a_hard_missing_section_violation():
    description = _description().replace("[Comparison]", "[Comparision]")

    result = audit_issue(
        _issue(description=description, labels=()),
        base_url="https://jira.example.com",
    )

    assert {item.rule_id for item in result.violations} == {
        "DESCRIPTION.COMPARISON"
    }
    assert not ai_reviewable_violations(result)


def test_only_declared_ambiguous_violations_become_ai_candidates():
    hard_failure = audit_issue(
        _issue(description=_description(actual="")),
        base_url="https://jira.example.com",
    )
    fuzzy_failures = (
        audit_issue(
            _issue(
                summary="[ACME][T7][V1.1][Video]: Video freezes,often",
                labels=(),
            ),
            base_url="https://jira.example.com",
        ),
        audit_issue(
            _issue(description=_description(rate="intermittent"), labels=()),
            base_url="https://jira.example.com",
        ),
        audit_issue(
            _issue(description=_description(comparison=""), labels=()),
            base_url="https://jira.example.com",
        ),
        audit_issue(
            _issue(
                description=_description(
                    notes="Hardware information:\nSoftware information: V1.1"
                ),
                labels=(),
            ),
            base_url="https://jira.example.com",
        ),
        audit_issue(
            _issue(
                description=_description(notes="HW info: T7\nSW info:"),
                labels=(),
            ),
            base_url="https://jira.example.com",
        ),
    )

    assert not ai_reviewable_violations(hard_failure)
    assert [bool(ai_reviewable_violations(result)) for result in fuzzy_failures] == [
        True,
        True,
        True,
        True,
        True,
    ]


@dataclass
class FakeClient:
    pages: list[SearchPage] | None = None
    filter_payload: dict | None = None
    error: Exception | None = None

    def __post_init__(self):
        self.search_calls = []
        self.filter_calls = []

    def search_page(self, jql, **kwargs):
        self.search_calls.append((jql, kwargs))
        if self.error:
            raise self.error
        if self.pages:
            return self.pages.pop(0)
        return SearchPage([], 0, kwargs.get("max_results", 1), 0, True)

    def fetch_filter(self, filter_id):
        self.filter_calls.append(filter_id)
        return dict(self.filter_payload or {})


@pytest.mark.parametrize(
    ("text", "kind", "jql", "filter_payload"),
    (
        ("project = SH", "jql", "project = SH", None),
        ("https://jira.example.com/browse/SH-123", "issue_url", 'key = "SH-123"', None),
        ("https://jira.example.com/issues/?jql=project%20%3D%20SH",
         "jql_url", "project = SH", None),
        ("https://jira.example.com/filter/42", "filter_url", "labels = regression",
         {"jql": "labels = regression"}),
    ),
)
def test_resolves_supported_jql_and_jira_urls(text, kind, jql, filter_payload):
    client = FakeClient(filter_payload=filter_payload)

    result = resolve_audit_input(text, base_url="https://jira.example.com", client=client)

    assert (result.source_kind, result.jql) == (kind, jql)
    assert client.search_calls[0][0] == jql


def test_rejects_empty_external_or_invalid_jira_input():
    invalid = (
        ("", "JQL"),
        ("https://other.example.com/browse/SH-1", "host"),
        ("ftp://jira.example.com/browse/SH-1", "HTTP"),
        ("https://jira.example.com/browse/not-a-key", "URL"),
    )
    for text, message in invalid:
        with pytest.raises(ValueError, match=message):
            resolve_audit_input(text, base_url="https://jira.example.com", client=FakeClient())
    with pytest.raises(ValueError, match="JQL"):
        resolve_audit_input("project =", base_url="https://jira.example.com",
                            client=FakeClient(error=RuntimeError("invalid")))


def test_service_paginates_and_reports_stable_progress_stages():
    client = FakeClient(
        pages=[
            SearchPage([_issue("SH-1"), _issue("SH-2")], 0, 2, 3, False),
            SearchPage([_issue("SH-3")], 2, 2, 3, True),
        ]
    )
    progress = []

    report = JiraAuditService(client, base_url="https://jira.example.com").run(
        ResolvedAuditInput("jql", "project = SH", "project = SH"),
        lambda *value: progress.append(value),
    )

    assert [item.key for item in report.issues] == ["SH-1", "SH-2", "SH-3"]
    assert report.passed_count == 3
    assert progress == [
        ("fetching", 2, 3),
        ("fetching", 3, 3),
        ("rule_auditing", 1, 3),
        ("rule_auditing", 2, 3),
        ("rule_auditing", 3, 3),
        ("ai_reviewing", 0, 0),
        ("finalizing", 3, 3),
    ]


def test_empty_service_run_reports_every_stable_progress_stage():
    progress = []

    JiraAuditService(FakeClient(), base_url="https://jira.example.com").run(
        ResolvedAuditInput("jql", "project = NONE", "project = NONE"),
        lambda *value: progress.append(value),
    )

    assert progress == [
        ("fetching", 0, 0),
        ("rule_auditing", 0, 0),
        ("ai_reviewing", 0, 0),
        ("finalizing", 0, 0),
    ]


def test_export_is_unique_atomic_openpyxl_workbook_with_links(tmp_path):
    failed = audit_issue(_issue(summary="invalid"), base_url="https://jira.example.com")
    failed = replace(
        failed,
        key="@SH-123",
        summary="-invalid\x01",
        reporter="=Coco",
        violations=(
            replace(
                failed.violations[0],
                observed="@invalid\x02",
                reason="+invalid",
                guidance="-invalid",
            ),
        ),
    )
    report = AuditReport(
        resolved=ResolvedAuditInput(
            "jql",
            "=HYPERLINK(\"https://example.invalid\")",
            "+project\x01 = SH",
        ),
        generated_at=datetime(2026, 7, 24, 10, 11, 12),
        rules=active_rules(),
        issues=(failed,),
    )
    now = datetime(2026, 7, 24, 10, 11, 12)

    first = export_audit_xlsx(report, downloads_dir=tmp_path, now=now)
    second = export_audit_xlsx(report, downloads_dir=tmp_path, now=now)
    workbook = load_workbook(first)

    assert first.name == "jira_format_audit_20260724_101112.xlsx"
    assert second.name == "jira_format_audit_20260724_101112_2.xlsx"
    assert not list(tmp_path.glob("*.tmp"))
    assert workbook.sheetnames == ["Summary", "Rules", "Issues", "Violations"]
    assert workbook["Summary"]["B4"].value.startswith("'=")
    assert workbook["Summary"]["B5"].value == "'+project = SH"
    assert workbook["Issues"]["B2"].hyperlink.target.endswith("/browse/SH-123")
    assert workbook["Issues"]["A2"].value == "'@SH-123"
    assert workbook["Issues"]["C2"].value == "'-invalid"
    assert workbook["Issues"]["D2"].value == "'=Coco"
    assert workbook["Violations"]["C2"].value == "SUMMARY.FORMAT"
    assert workbook["Violations"]["F2"].value == "'@invalid"
    assert workbook["Violations"]["H2"].value == "'+invalid"
    assert workbook["Violations"]["I2"].value == "'-invalid"
