from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from support.jira_integration.core.create_schema import CreateFieldControl
from support.jira_integration.core.errors import JiraRequestError
from support.jira_integration.services.create_schema_service import JiraCreateSchemaService
from support.jira_integration.transport.client import JiraClient


CREATE_META = {
    "projects": [{
        "key": "SH",
        "name": "SmartHome",
        "issuetypes": [{
            "id": "1",
            "name": "Bug",
            "fields": {
                "summary": {"name": "Summary", "required": True, "schema": {"type": "string"}},
                "description": {"name": "Description", "required": False, "schema": {"type": "string"}, "defaultValue": "Jira template"},
                "customfield_12200": {
                    "name": "Channel of Reporter",
                    "required": True,
                    "schema": {"type": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:cascadingselect"},
                    "allowedValues": [{"id": "", "value": "None"}, {"id": "13251", "value": "Customer-Feedback", "children": [{"id": None, "value": "None"}]}, {"id": "13261", "value": "Self-Test"}],
                    "defaultValue": {"id": "13251", "child": {"id": ""}},
                },
                "components": {
                    "name": "Component/s",
                    "required": False,
                    "schema": {"type": "array", "items": "component"},
                    "allowedValues": [{"id": "20", "name": "Customization"}],
                    "defaultValue": [{"id": "20"}],
                },
                "customfield_10700": {
                    "name": "Manager",
                    "required": False,
                    "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:userpicker"},
                    "defaultValue": {"name": "fred.chen", "displayName": "Fred Chen"},
                },
                "priority": {
                    "name": "Priority",
                    "required": True,
                    "schema": {"type": "priority"},
                    "allowedValues": [{"id": "2", "name": "P2"}],
                    "defaultValue": {"id": "2"},
                },
                "labels": {"name": "Labels", "required": False, "schema": {"type": "array", "items": "string"}},
            },
        }],
    }],
}


class RecordingClient(JiraClient):
    def __init__(self, response_data):
        self.response_data = response_data
        self.calls = []

    def _api_path(self, suffix):
        return f"https://jira/rest/api/2/{suffix}"

    def _request(self, method, url, *, params=None, json=None):
        self.calls.append((method, url, params, json))

        class Response:
            data = self.response_data

        return Response()


def test_fetch_create_metadata_scopes_project_and_issue_type():
    client = RecordingClient(CREATE_META)

    payload = client.fetch_create_metadata("SH", "Bug")

    assert payload == CREATE_META
    assert client.calls == [(
        "GET",
        "https://jira/rest/api/2/issue/createmeta",
        {
            "projectKeys": "SH",
            "issuetypeNames": "Bug",
            "expand": "projects.issuetypes.fields",
        },
        None,
    )]


def test_search_users_is_project_scoped_and_normalizes_public_identity_only():
    client = RecordingClient([{
        "name": "fred.chen",
        "displayName": "Fred Chen",
        "avatarUrls": {"48x48": "https://jira/avatar/fred"},
        "password": "must-not-leak",
    }])

    users = client.search_users("fred", project_key="SH")

    assert users == [{
        "account": "fred.chen",
        "display_name": "Fred Chen",
        "avatar_url": "https://jira/avatar/fred",
    }]
    assert client.calls == [(
        "GET",
        "https://jira/rest/api/2/user/assignable/search",
        {"project": "SH", "username": "fred"},
        None,
    )]


def test_current_user_reads_authenticated_identity_from_myself():
    client = RecordingClient({
        "name": "subing.xu",
        "displayName": "Subing Xu",
        "avatarUrls": {"48x48": "https://jira/avatar/subing"},
        "password": "must-not-leak",
    })

    user = client.current_user()

    assert user == {
        "account": "subing.xu",
        "display_name": "Subing Xu",
        "avatar_url": "https://jira/avatar/subing",
    }
    assert client.calls == [(
        "GET", "https://jira/rest/api/2/myself", None, None,
    )]


def test_schema_maps_jira_native_controls_required_options_and_order():
    service = JiraCreateSchemaService(RecordingClient(CREATE_META))

    schema = service.schema("SH", "Bug")
    fields = {item.field_id: item for item in schema}

    assert [item.field_id for item in schema] == [
        "project",
        "issuetype",
        *CREATE_META["projects"][0]["issuetypes"][0]["fields"],
    ]
    assert fields["project"].required and fields["project"].control == "single"
    assert fields["project"].value == "SH"
    assert fields["project"].options[0].value == "SH"
    assert fields["issuetype"].required and fields["issuetype"].control == "single"
    assert fields["issuetype"].value == "Bug"
    assert fields["issuetype"].options[0].value == "Bug"
    assert fields["summary"].control == "text" and fields["summary"].required
    assert fields["description"].control == "multiline"
    assert fields["customfield_12200"].control == "cascade"
    assert fields["components"].control == "multi"
    assert fields["customfield_10700"].control == "user"
    assert fields["priority"].control == "single"
    assert fields["labels"].control == "multi"
    assert fields["description"].value == "Jira template"
    assert fields["priority"].value == "2"
    assert fields["components"].value == ["20"]
    assert fields["customfield_12200"].value == {"parent": "13251", "child": ""}
    assert fields["customfield_10700"].value == "fred.chen"
    assert fields["priority"].options[0].value == "2"
    assert fields["priority"].options[0].label == "P2"
    none_option, cascade, self_test = fields["customfield_12200"].options
    assert none_option.value == "" and none_option.label == "None"
    assert cascade.value == "13251" and cascade.label == "Customer-Feedback"
    assert cascade.children[0].value == "" and cascade.children[0].label == "None"
    assert self_test.value == "13261"

    assert {item.value for item in CreateFieldControl} == {
        "text", "multiline", "single", "multi", "cascade", "user"
    }
    with pytest.raises(FrozenInstanceError):
        fields["summary"].required = False


def test_cascade_schema_injects_selectable_empty_child_when_jira_metadata_omits_placeholder():
    import copy
    payload = copy.deepcopy(CREATE_META)
    channel = payload["projects"][0]["issuetypes"][0]["fields"]["customfield_12200"]
    customer = next(item for item in channel["allowedValues"] if item.get("value") == "Customer-Feedback")
    customer["children"] = [
        {"id": "reason1", "value": "Reason 1"},
        {"id": "reason2", "value": "Reason 2"},
    ]

    field = next(
        item for item in JiraCreateSchemaService(RecordingClient(payload)).schema("SH", "Bug")
        if item.field_id == "customfield_12200"
    )
    customer_option = next(item for item in field.options if item.label == "Customer-Feedback")

    assert [(item.value, item.label) for item in customer_option.children] == [
        ("", "None"), ("reason1", "Reason 1"), ("reason2", "Reason 2")
    ]
    assert field.value == {"parent": "13251", "child": ""}


@pytest.mark.parametrize(
    "payload, project_key, issue_type",
    [({"projects": []}, "SH", "Bug"), (CREATE_META, "MISSING", "Bug"), (CREATE_META, "SH", "Support")],
)
def test_schema_rejects_missing_project_or_issue_type(payload, project_key, issue_type):
    with pytest.raises(JiraRequestError):
        JiraCreateSchemaService(RecordingClient(payload)).schema(project_key, issue_type)
