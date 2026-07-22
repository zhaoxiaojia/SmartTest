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
        context_fields = (
            _context_field(
                field_id="project",
                name="Project",
                value=project_key,
                label=str(project.get("name") or project_key),
            ),
            _context_field(
                field_id="issuetype",
                name="Issue Type",
                value=issue_type,
                label=str(issue_type_metadata.get("name") or issue_type),
            ),
        )
        metadata_fields = tuple(
            _field_schema(str(field_id), field)
            for field_id, field in fields.items()
            if isinstance(field, dict) and field_id not in {"project", "issuetype"}
        )
        return context_fields + metadata_fields


def _context_field(
    *,
    field_id: str,
    name: str,
    value: str,
    label: str,
) -> CreateFieldSchema:
    return CreateFieldSchema(
        field_id=field_id,
        name=name,
        required=True,
        control=CreateFieldControl.SINGLE,
        options=(CreateFieldOption(value=value, label=label),),
        value=value,
    )


def _field_schema(field_id: str, metadata: dict[str, Any]) -> CreateFieldSchema:
    name = str(metadata.get("name") or field_id)
    control = _control(field_id, name, metadata)
    options = tuple(
        _option(item)
        for item in metadata.get("allowedValues") or ()
        if isinstance(item, dict)
    )
    return CreateFieldSchema(
        field_id=field_id,
        name=name,
        required=bool(metadata.get("required", False)),
        control=control,
        options=options,
        value=_default_value(metadata.get("defaultValue"), control, options),
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


def _default_value(
    value: Any,
    control: CreateFieldControl,
    options: tuple[CreateFieldOption, ...],
) -> Any:
    if value is None:
        return None
    if control in {CreateFieldControl.TEXT, CreateFieldControl.MULTILINE}:
        return value
    if control == CreateFieldControl.USER:
        if isinstance(value, dict):
            return str(value.get("name") or value.get("accountId") or value.get("key") or "")
        return str(value)
    if control == CreateFieldControl.CASCADE:
        if not isinstance(value, dict):
            return {}
        parent = _default_identity(value, options)
        parent_option = next((item for item in options if item.value == parent), None)
        child_value = value.get("child")
        child = (
            _default_identity(child_value, parent_option.children)
            if isinstance(child_value, dict) and parent_option
            else ""
        )
        return {"parent": parent, "child": child}
    if control == CreateFieldControl.MULTI:
        values = value if isinstance(value, (list, tuple)) else [value]
        return [_default_identity(item, options) for item in values]
    if control == CreateFieldControl.SINGLE:
        return _default_identity(value, options)
    return value


def _default_identity(
    value: Any,
    options: tuple[CreateFieldOption, ...],
) -> str:
    if isinstance(value, dict):
        candidate = str(
            value.get("id")
            or value.get("value")
            or value.get("name")
            or value.get("key")
            or ""
        )
    else:
        candidate = str(value or "")
    option = next(
        (item for item in options if item.value == candidate or item.label == candidate),
        None,
    )
    return option.value if option else candidate
