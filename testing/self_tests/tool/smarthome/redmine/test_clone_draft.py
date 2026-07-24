from __future__ import annotations

from dataclasses import replace

import pytest

from support.jira_integration.core.create_schema import (
    CreateFieldControl,
    CreateFieldOption,
    CreateFieldSchema,
)
from support.jira_integration.services.create_issue_service import CreateIssueService
from support.jira_integration.core.description import render_notes_description
from tool.SmartHome.redmine.clone_draft import RedmineCloneDraftService
from tool.SmartHome.redmine.models import RedmineIssueDetail, RedmineJournal, RedmineProject


def option(value, label, children=()):
    return CreateFieldOption(value=value, label=label, children=tuple(children))


def field(field_id, name, control, *, required=False, options=(), value=None):
    return CreateFieldSchema(
        field_id=field_id,
        name=name,
        required=required,
        control=CreateFieldControl(control),
        options=tuple(options),
        value=value,
    )


SCHEMA = (
    field("project", "Project", "single", required=True),
    field("issuetype", "Issue Type", "single", required=True),
    field("summary", "Summary", "text", required=True),
    field("description", "Description", "multiline"),
    field("customfield_attachment_real", "Attachment links", "text"),
    field("priority", "Priority", "single", required=True, options=(option("2", "P2"),)),
    field("customfield_12200", "Channel of Reporter", "cascade", required=True, options=(option("", "None"), option("13251", "Customer-Feedback", (option("", "None"),)), option("13261", "Self-Test"))),
    field("customfield_10109", "Severity", "single", required=True, options=(option("20", "Major"),)),
    field("customfield_10107", "Product", "multi", required=True, options=(option("30", "BDS Reference"),)),
    field("components", "Component/s", "multi", required=True, options=(option("40", "Customization"),)),
    field("customfield_10407", "Project ID", "multi", required=True, options=(option("50", "AN40BF-A311D2"), option("51", "WRONG-NAME-GUESS"))),
    field("customfield_10300", "Software Release", "multi"),
    field("reporter", "Reporter", "user"),
    field("customfield_10700", "Manager", "user", required=True),
    field("customfield_10409", "FAE Coworker", "user"),
    field("customfield_11002", "FAE Manager", "user", required=True),
)

REDMINE_BUG = RedmineIssueDetail(
    id="61043",
    url="https://support.amlogic.com/issues/61043",
    project_identifier="an40bf",
    tracker="Bug",
    subject="HDMI output fails",
    description="Reproduction steps",
)
PROJECT = RedmineProject(
    name="A misleading project name WRONG-NAME-GUESS",
    identifier="an40bf",
    url="https://support.amlogic.com/projects/an40bf",
    project_id="AN40BF-A311D2",
)


def build(*, issue=REDMINE_BUG, schema=SCHEMA, account="defeng.zhai", department="FAE-SW"):
    return RedmineCloneDraftService().build(
        issue=issue,
        project=PROJECT,
        schema=schema,
        account=account,
        department=department,
        prepared_description=render_notes_description(issue.description),
    )


@pytest.mark.parametrize("tracker, expected_type", [("Bug", "Bug"), ("Support", "Feature")])
def test_clone_draft_prefills_confirmed_mappings_with_current_option_ids(tracker, expected_type):
    draft = build(issue=replace(REDMINE_BUG, tracker=tracker))

    assert draft.value("project") == "SH"
    assert draft.value("issuetype") == expected_type
    assert draft.value("summary") == REDMINE_BUG.subject
    assert draft.value("priority") == "2"
    assert draft.value("customfield_12200") == {"parent": "13251", "child": ""}
    assert draft.value("customfield_10109") == "20"
    assert draft.value("customfield_10107") == ["30"]
    assert draft.value("components") == ["40"]
    assert draft.value("customfield_10407") == ["50"]
    assert draft.value("customfield_10300") == []
    assert draft.value("reporter") == "defeng.zhai"
    assert draft.value("customfield_10700") == "fred.chen"
    assert draft.value("customfield_10409") == "defeng.zhai"
    assert draft.value("customfield_11002") == "fred.chen"
    assert "[Notes]:\nReproduction steps\nHW info:" in draft.value("description")
    assert "Source" not in draft.value("description")
    assert REDMINE_BUG.url not in draft.value("description")
    assert not draft.errors


@pytest.mark.parametrize("department", ["FAE-QA", "FAE-HW", "", "fae-sw"])
def test_only_exact_fae_sw_prefills_coworker(department):
    assert build(account="hardware.user", department=department).value("customfield_10409") == ""


def test_empty_description_keeps_empty_notes_and_project_id_uses_metadata():
    draft = build(issue=replace(REDMINE_BUG, description=""))

    assert "[Notes]:\n\nHW info:" in draft.value("description")
    assert "Source" not in draft.value("description")
    assert REDMINE_BUG.url not in draft.value("description")
    assert draft.value("customfield_10407") == ["50"]


def test_missing_confirmed_option_is_empty_and_blocking():
    schema = tuple(
        replace(item, options=(option("99", "Minor"),))
        if item.name == "Severity"
        else item
        for item in SCHEMA
    )

    draft = build(schema=schema)

    assert draft.value("customfield_10109") == ""
    assert any(error.field_id == "customfield_10109" and error.blocking for error in draft.errors)


def test_unmapped_required_field_remains_empty_and_blocking():
    schema = SCHEMA + (field("customfield_99999", "Required Unknown", "text", required=True),)

    draft = build(schema=schema)

    assert draft.value("customfield_99999") == ""
    assert any(error.field_id == "customfield_99999" and error.blocking for error in draft.errors)


def test_unmapped_field_preserves_jira_default_and_missing_default_uses_empty_shape():
    schema = tuple(
        replace(item, value=["60"], options=(option("60", "Release-1"),))
        if item.name == "Software Release"
        else item
        for item in SCHEMA
    ) + (field("customfield_99998", "Optional Unknown", "multi"),)

    draft = build(schema=schema)

    assert draft.value("customfield_10300") == ["60"]
    assert draft.value("customfield_99998") == []
    assert not any(error.field_id in {"customfield_10300", "customfield_99998"} for error in draft.errors)


class PayloadClient:
    def search_page(self, *args, **kwargs):
        class Page:
            issues = []
        return Page()

    def create_issue(self, payload):
        self.payload = payload
        return {"key": "SH-1"}


def test_user_edits_replace_initial_values_and_payload_shapes_are_owned_by_create_service():
    draft = build(
        issue=replace(
            REDMINE_BUG,
            attributes={"Board": "A"},
            comments=(RedmineJournal(id="1", note="customer comment"),),
        )
    )
    draft.update("summary", "Edited summary")
    draft.update("customfield_10109", "20")
    draft.update("customfield_10107", ["30"])
    draft.update("customfield_12200", {"parent": "13251", "child": ""})
    draft.update("customfield_10700", "other.user")
    draft.update("customfield_attachment_real", "https://edited.example/link")
    request = draft.to_request()

    assert request.summary == "Edited summary"
    assert request.source_system == "redmine"
    assert request.source_id == "61043"
    assert request.source_url == REDMINE_BUG.url
    assert request.extra_fields["customfield_attachment_real"] == "https://edited.example/link"
    assert "Attachment links" not in request.extra_fields

    client = PayloadClient()
    CreateIssueService(client).create_issue(request)
    fields = client.payload["fields"]
    final_description = fields["description"]
    assert "[Notes]:\nReproduction steps\nHW info:" in final_description
    for excluded in (
        "Source:",
        "Source ID:",
        "Source URL:",
        REDMINE_BUG.url,
        REDMINE_BUG.subject,
        "Board",
        "customer comment",
    ):
        assert excluded not in final_description
    assert fields["priority"] == {"id": "2"}
    assert fields["components"] == [{"id": "40"}]
    assert fields["customfield_10109"] == {"id": "20"}
    assert fields["customfield_10107"] == [{"id": "30"}]
    assert fields["customfield_12200"] == {"id": "13251"}
    assert fields["customfield_10700"] == {"name": "other.user"}
    assert fields["customfield_attachment_real"] == "https://edited.example/link"
    assert {"clone_external", "source_redmine", "redmine_61043"} <= set(fields["labels"])


def test_attachment_links_defaults_to_redmine_identity_url_using_real_schema_field_id():
    draft = build()
    assert draft.value("customfield_attachment_real") == REDMINE_BUG.url
    request = draft.to_request()
    assert request.source_url == REDMINE_BUG.url
    assert request.extra_fields == {**request.extra_fields, "customfield_attachment_real": REDMINE_BUG.url}


def test_channel_child_can_select_reason_then_return_to_empty_none_value():
    channel_schema = tuple(
        replace(
            item,
            options=(option("13251", "Customer-Feedback", (option("", "None"), option("reason1", "Reason 1"))),),
        ) if item.name == "Channel of Reporter" else item
        for item in SCHEMA
    )
    draft = build(schema=channel_schema)
    assert draft.value("customfield_12200") == {"parent": "13251", "child": ""}
    draft.update("customfield_12200", {"parent": "13251", "child": "reason1"})
    assert not draft.errors
    draft.update("customfield_12200", {"parent": "13251", "child": ""})
    assert draft.value("customfield_12200") == {"parent": "13251", "child": ""}
    assert not draft.errors
