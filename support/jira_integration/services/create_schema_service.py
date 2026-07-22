from __future__ import annotations

from typing import Any

from support.jira_integration.core.create_schema import (
    CreateFieldControl,
    CreateFieldOption,
    CreateFieldSchema,
)
from support.jira_integration.core.errors import JiraRequestError
from support.jira_integration.transport.client import JiraClient


_USER_FIELD_NAMES = {"assignee", "reporter", "manager", "fae coworker", "fae manager"}


class JiraCreateSchemaService:
    def __init__(self, client: JiraClient):
        self._client = client

    def schema(self, project_key: str, issue_type: str) -> tuple[CreateFieldSchema, ...]:
        metadata = self._client.fetch_create_metadata(project_key, issue_type)
        project = next(
            (
                item
                for item in metadata.get("projects") or ()
                if isinstance(item, dict) and str(item.get("key") or "") == project_key
            ),
            None,
        )
        if project is None:
            raise JiraRequestError(f"Jira create metadata has no project {project_key}")
        issue_type_metadata = next(
            (
                item
                for item in project.get("issuetypes") or ()
                if isinstance(item, dict) and str(item.get("name") or "") == issue_type
            ),
            None,
        )
        if issue_type_metadata is None:
            raise JiraRequestError(
                f"Jira create metadata has no issue type {issue_type} for project {project_key}"
            )
        fields = issue_type_metadata.get("fields")
        if not isinstance(fields, dict):
            raise JiraRequestError(
                f"Jira create metadata has no fields for {project_key} {issue_type}"
            )
        return tuple(
            _field_schema(str(field_id), field)
            for field_id, field in fields.items()
            if isinstance(field, dict)
        )


def _field_schema(field_id: str, metadata: dict[str, Any]) -> CreateFieldSchema:
    name = str(metadata.get("name") or field_id)
    return CreateFieldSchema(
        field_id=field_id,
        name=name,
        required=bool(metadata.get("required", False)),
        control=_control(field_id, name, metadata),
        options=tuple(
            _option(item)
            for item in metadata.get("allowedValues") or ()
            if isinstance(item, dict)
        ),
    )


def _control(
    field_id: str,
    name: str,
    metadata: dict[str, Any],
) -> CreateFieldControl:
    schema = metadata.get("schema") or {}
    schema_type = str(schema.get("type") or "").casefold()
    schema_custom = str(schema.get("custom") or "").casefold()
    field_name = name.strip().casefold()
    if field_id == "description" or field_name == "description":
        return CreateFieldControl.MULTILINE
    if "cascadingselect" in schema_custom or field_name == "channel of reporter":
        return CreateFieldControl.CASCADE
    if (
        schema_type == "user"
        or "userpicker" in schema_custom
        or field_name in _USER_FIELD_NAMES
    ):
        return CreateFieldControl.USER
    if schema_type == "array":
        return CreateFieldControl.MULTI
    if metadata.get("allowedValues"):
        return CreateFieldControl.SINGLE
    return CreateFieldControl.TEXT


def _option(metadata: dict[str, Any]) -> CreateFieldOption:
    value = str(metadata.get("id") or metadata.get("value") or metadata.get("name") or "")
    label = str(
        metadata.get("value")
        or metadata.get("name")
        or metadata.get("displayName")
        or value
    )
    return CreateFieldOption(
        value=value,
        label=label,
        children=tuple(
            _option(item)
            for item in metadata.get("children") or ()
            if isinstance(item, dict)
        ),
    )
