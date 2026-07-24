from __future__ import annotations

import sys


def _valid_issue() -> dict:
    return {
        "key": "SH-123",
        "fields": {
            "summary": "[ACME][T7][Playback] Video freezes after seeking",
            "description": "\n".join(
                (
                    "[Steps to reproduce]:",
                    "1. Start playback",
                    "[Actual results]:",
                    "Video freezes",
                    "[Expected results]:",
                    "Playback continues",
                    "[Reproducibility rate]:",
                    "3/3",
                    "[Comparision]:",
                    "Not reproduced on build 2026.07.20",
                    "[Notes]:",
                    "Regression from build 2026.07.21 to build 2026.07.22",
                    "HW info:",
                    "T7 reference board",
                    "SW info:",
                    "bad: 2026.07.22; good: 2026.07.20",
                )
            ),
            "reporter": {"displayName": "Coco"},
            "components": [{"name": "Playback"}],
            "labels": ["regression"],
            "attachment": [{"filename": "evidence.zip", "size": 1024}],
        },
    }


def test_audit_module_is_independent_and_valid_issue_passes():
    sys.modules.pop("jira_handler", None)

    from support.jira_integration.audit import active_rules, audit_issue

    result = audit_issue(_valid_issue(), base_url="https://jira.example.com")

    assert result.passed is True
    assert result.key == "SH-123"
    assert result.url == "https://jira.example.com/browse/SH-123"
    assert result.reporter == "Coco"
    assert result.violations == ()
    assert [rule.rule_id for rule in active_rules()] == [
        "SUMMARY-001",
        "SUMMARY-002",
        "SUMMARY-003",
        "COMPONENT-001",
        "PROBABILITY-001",
        "DESCRIPTION-001",
        "REGRESSION-001",
        "ATTACHMENT-001",
        "LABEL-001",
    ]
    assert "jira_handler" not in sys.modules


def test_summary_rules_return_structured_violations():
    from support.jira_integration.audit import audit_issue

    issue = _valid_issue()
    issue["fields"]["summary"] = "[ACME][t7] 播放冻结"

    result = audit_issue(issue, base_url="https://jira.example.com/")
    violations = {item.rule_id: item for item in result.violations}

    assert {"SUMMARY-001", "SUMMARY-002", "SUMMARY-003"} <= set(violations)
    chip = violations["SUMMARY-003"]
    assert chip.section == "Summary"
    assert chip.field == "summary"
    assert chip.observed == "[ACME][t7] 播放冻结"
    assert chip.reason
    assert chip.guidance


def test_component_probability_and_description_rules():
    from support.jira_integration.audit import audit_issue

    issue = _valid_issue()
    issue["fields"]["components"] = [{"name": "Audio"}]
    issue["fields"]["description"] = (
        issue["fields"]["description"]
        .replace("3/3", "often")
        .replace("[Expected results]:", "[Missing expected]:")
    )

    rule_ids = {item.rule_id for item in audit_issue(issue, base_url="https://jira.example.com").violations}

    assert {"COMPONENT-001", "PROBABILITY-001", "DESCRIPTION-001"} <= rule_ids


def test_regression_label_requires_version_evidence_and_comparison():
    from support.jira_integration.audit import audit_issue

    issue = _valid_issue()
    issue["fields"]["description"] = issue["fields"]["description"].replace(
        "Not reproduced on build 2026.07.20", ""
    ).replace(
        "Regression from build 2026.07.21 to build 2026.07.22", "Regression found"
    ).replace("bad: 2026.07.22; good: 2026.07.20", "latest build")

    rule_ids = {item.rule_id for item in audit_issue(issue, base_url="https://jira.example.com").violations}

    assert {"REGRESSION-001", "LABEL-001"} <= rule_ids


def test_attachment_limit_is_ten_mibibytes():
    from support.jira_integration.audit import audit_issue

    issue = _valid_issue()
    issue["fields"]["attachment"] = [
        {"filename": "ok.bin", "size": 10 * 1024 * 1024},
        {"filename": "large.bin", "size": 10 * 1024 * 1024 + 1},
    ]

    violations = [
        item
        for item in audit_issue(issue, base_url="https://jira.example.com").violations
        if item.rule_id == "ATTACHMENT-001"
    ]

    assert len(violations) == 1
    assert "large.bin" in violations[0].observed


def test_normalize_issue_handles_jira_field_shapes():
    from support.jira_integration.audit import normalize_issue

    normalized = normalize_issue(_valid_issue(), "https://jira.example.com/")

    assert normalized.key == "SH-123"
    assert normalized.summary.startswith("[ACME]")
    assert normalized.components == ("Playback",)
    assert normalized.labels == ("regression",)
    assert normalized.attachments[0].filename == "evidence.zip"
