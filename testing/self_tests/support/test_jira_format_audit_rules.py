from __future__ import annotations

import sys
from pathlib import Path

import pytest


EXPECTED_RULE_IDS = [
    "SUMMARY.FORMAT",
    "SUMMARY.CUSTOMER",
    "SUMMARY.CHIP",
    "SUMMARY.VERSION",
    "SUMMARY.CUSTOMER_ENGLISH",
    "SUMMARY.CHIP_UPPERCASE",
    "SUMMARY.MODULE",
    "SUMMARY.DESCRIPTION_ENGLISH",
    "SUMMARY.PROBABILITY",
    "COMPONENT.REQUIRED",
    "COMPONENT.ALLOWED",
    "DESCRIPTION.STEPS_TO_REPRODUCE",
    "DESCRIPTION.ACTUAL_RESULTS",
    "DESCRIPTION.EXPECTED_RESULTS",
    "DESCRIPTION.REPRODUCIBILITY_RATE",
    "DESCRIPTION.COMPARISION",
    "DESCRIPTION.NOTES",
    "DESCRIPTION.STEPS_ORDERED",
    "DESCRIPTION.RATE_FORMAT",
    "DESCRIPTION.NOTES_HW",
    "DESCRIPTION.NOTES_SW",
    "REGRESSION.EVIDENCE",
    "ATTACHMENT.MAX_SIZE",
]

MOJIBAKE_MARKERS = (
    "\ufffd",
    "锛",
    "銆",
    "鈥",
    "寮€",
    "鏂囦",
    "瀹℃",
    "瑙勮",
    "绀轰",
    "ײ",
)


def _description(
    *,
    steps: str = "1. Start playback.\n2. Seek to 00:30.",
    actual: str = "Video freezes.",
    expected: str = "Playback continues.",
    rate: str = "2/2",
    comparison: str = (
        "Previous version build V1.0 is normal; "
        "current version build V1.1 is broken."
    ),
    notes: str = "HW info: T7 reference board\nSW info: V1.1",
) -> str:
    return "\n".join(
        (
            "[Steps to reproduce]:",
            steps,
            "[Actual results]:",
            actual,
            "[Expected results]:",
            expected,
            "[Reproducibility rate]:",
            rate,
            "[Comparision]:",
            comparison,
            "[Notes]:",
            notes,
        )
    )


def _issue(
    *,
    summary: str = "[ACME][T7][V1.1][Video]: Video freezes after seeking,2/2",
    description: str | None = None,
    components: list[str] | None = None,
    labels: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    return {
        "key": "SH-123",
        "fields": {
            "summary": summary,
            "description": _description() if description is None else description,
            "reporter": {"displayName": "Coco"},
            "components": [
                {"name": name} for name in (["Video"] if components is None else components)
            ],
            "labels": ["regression"] if labels is None else labels,
            "attachment": (
                [{"filename": "evidence.zip", "size": 1024}]
                if attachments is None
                else attachments
            ),
        },
    }


def _rule_ids(issue: dict) -> set[str]:
    from support.jira_integration.audit import audit_issue

    return {
        violation.rule_id
        for violation in audit_issue(issue, base_url="https://jira.example.com").violations
    }


@pytest.mark.parametrize(
    "summary",
    [
        "[ACME][T7][V1.1][Video]: Video freezes after seeking,50%",
        "[SH-123][ACME][T7][V1.1][Video]: Video freezes after seeking,1/2",
        (
            "[SH-123][BUG-456][ACME][T7][V1.1][Video]: "
            "Video freezes after seeking,100%."
        ),
    ],
)
def test_four_five_and_six_group_summaries_pass(summary):
    from support.jira_integration.audit import active_rules, audit_issue

    result = audit_issue(_issue(summary=summary), base_url="https://jira.example.com")

    assert result.passed is True
    assert result.violations == ()
    assert [rule.rule_id for rule in active_rules()] == EXPECTED_RULE_IDS


def test_audit_module_is_independent_and_normalizes_jira_shapes():
    sys.modules.pop("jira_handler", None)

    from support.jira_integration.audit import normalize_issue

    normalized = normalize_issue(_issue(), "https://jira.example.com/")

    assert normalized.key == "SH-123"
    assert normalized.url == "https://jira.example.com/browse/SH-123"
    assert normalized.components == ("Video",)
    assert normalized.labels == ("regression",)
    assert normalized.attachments[0].filename == "evidence.zip"
    assert "jira_handler" not in sys.modules


@pytest.mark.parametrize(
    "summary",
    [
        "[ACME][T7][Video]: Video freezes,50%",
        "[ACME][T7][V1.1][Video] Video freezes,50%",
        "[ACME][T7][V1.1][Video]: Video freezes",
        "[ONE][TWO][ACME][T7][V1.1][Video][EXTRA]: Video freezes,50%",
    ],
)
def test_summary_format_requires_four_to_six_groups_colon_description_and_probability(summary):
    assert "SUMMARY.FORMAT" in _rule_ids(_issue(summary=summary))


def test_summary_required_values_have_granular_rule_ids():
    summary = "[ ][ ][ ][Video]: Video freezes,50%"

    rule_ids = _rule_ids(_issue(summary=summary))

    assert {"SUMMARY.CUSTOMER", "SUMMARY.CHIP", "SUMMARY.VERSION"} <= rule_ids


def test_summary_customer_and_description_must_be_english():
    summary = "[客户][T7][V1.1][Video]: 播放在快进后冻结,50%"

    rule_ids = _rule_ids(_issue(summary=summary))

    assert {"SUMMARY.CUSTOMER_ENGLISH", "SUMMARY.DESCRIPTION_ENGLISH"} <= rule_ids


def test_summary_chip_module_and_probability_are_validated_independently():
    summary = "[ACME][t7][V1.1][Unknown]: Video freezes,3/2"

    rule_ids = _rule_ids(_issue(summary=summary, components=["Audio"]))

    assert {
        "SUMMARY.CHIP_UPPERCASE",
        "SUMMARY.MODULE",
        "SUMMARY.PROBABILITY",
    } <= rule_ids
    assert "COMPONENT.ALLOWED" not in rule_ids


def test_components_are_required_and_each_must_be_allowed_without_summary_equality():
    assert "COMPONENT.REQUIRED" in _rule_ids(_issue(components=[]))
    assert "COMPONENT.ALLOWED" in _rule_ids(_issue(components=["Video", "Unknown"]))

    mismatch_but_allowed = _issue(components=["Audio"])
    assert "COMPONENT.ALLOWED" not in _rule_ids(mismatch_but_allowed)
    assert "COMPONENT.REQUIRED" not in _rule_ids(mismatch_but_allowed)


@pytest.mark.parametrize(
    ("argument", "rule_id"),
    [
        ("steps", "DESCRIPTION.STEPS_TO_REPRODUCE"),
        ("actual", "DESCRIPTION.ACTUAL_RESULTS"),
        ("expected", "DESCRIPTION.EXPECTED_RESULTS"),
        ("rate", "DESCRIPTION.REPRODUCIBILITY_RATE"),
        ("comparison", "DESCRIPTION.COMPARISION"),
        ("notes", "DESCRIPTION.NOTES"),
    ],
)
def test_each_description_section_must_be_present_and_populated(argument, rule_id):
    description = _description(**{argument: ""})

    assert rule_id in _rule_ids(_issue(description=description, labels=[]))


@pytest.mark.parametrize(
    "steps",
    [
        "Start playback.",
        "2. Seek to 00:30.",
        "1. Start playback.\n3. Seek to 00:30.",
        "1. ;\n2. Seek to 00:30.",
    ],
)
def test_steps_must_be_consecutive_non_empty_executable_actions(steps):
    assert "DESCRIPTION.STEPS_ORDERED" in _rule_ids(
        _issue(description=_description(steps=steps), labels=[])
    )


@pytest.mark.parametrize("rate", ["101%", "-1%", "3/2", "1/0", "often"])
def test_description_rate_must_be_percentage_or_bounded_fraction(rate):
    assert "DESCRIPTION.RATE_FORMAT" in _rule_ids(
        _issue(description=_description(rate=rate), labels=[])
    )


def test_notes_requires_populated_hw_and_sw_info():
    hw_missing = _description(notes="HW info:\nSW info: V1.1")
    sw_missing = _description(notes="HW info: T7 reference board\nSW info:")

    assert "DESCRIPTION.NOTES_HW" in _rule_ids(_issue(description=hw_missing, labels=[]))
    assert "DESCRIPTION.NOTES_SW" in _rule_ids(_issue(description=sw_missing, labels=[]))


def test_regression_label_requires_previous_normal_and_current_broken_evidence():
    description = _description(comparison="V1.0 and V1.1 were compared.")

    assert "REGRESSION.EVIDENCE" in _rule_ids(_issue(description=description))
    assert "REGRESSION.EVIDENCE" not in _rule_ids(_issue(description=description, labels=[]))


def test_attachment_limit_is_ten_mibibytes():
    attachments = [
        {"filename": "ok.bin", "size": 10 * 1024 * 1024},
        {"filename": "large.bin", "size": 10 * 1024 * 1024 + 1},
    ]
    from support.jira_integration.audit import audit_issue

    violations = [
        item
        for item in audit_issue(
            _issue(attachments=attachments),
            base_url="https://jira.example.com",
        ).violations
        if item.rule_id == "ATTACHMENT.MAX_SIZE"
    ]

    assert len(violations) == 1
    assert "large.bin" in violations[0].observed


def test_owned_rule_reason_and_qml_text_contains_no_mojibake():
    from support.jira_integration.audit import active_rules, audit_issue

    invalid_issues = [
        _issue(
            summary="invalid summary",
            description="",
            components=[],
            attachments=[{"filename": "large.bin", "size": 11 * 1024 * 1024}],
        ),
        _issue(
            summary="[客户][t7][ ][Unknown]: 中文,3/2",
            description=_description(
                steps="1. ;",
                rate="3/2",
                comparison="",
                notes="HW info:\nSW info:",
            ),
            components=["Unknown"],
            labels=[],
        ),
        _issue(
            summary="[ ][ ][ ][Video]: Video freezes,50%",
            components=["Audio"],
            labels=[],
        ),
    ]
    violations = [
        violation
        for issue in invalid_issues
        for violation in audit_issue(
            issue,
            base_url="https://jira.example.com",
        ).violations
    ]
    owned_text = [
        text
        for rule in active_rules()
        for text in (rule.requirement, rule.guidance)
    ] + [violation.reason for violation in violations]
    qml = (
        Path(__file__).resolve().parents[3]
        / "ui/example/imports/example/qml/component/jiraaudit/JiraAuditWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert {violation.rule_id for violation in violations} == set(EXPECTED_RULE_IDS)
    assert all(marker not in text for text in owned_text for marker in MOJIBAKE_MARKERS)
    assert all(marker not in qml for marker in MOJIBAKE_MARKERS)
    assert ' + " 路 " + ' not in qml
    assert ' + " · " + ' in qml
