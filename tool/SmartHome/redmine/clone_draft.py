from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

from support.jira_integration.core.create_schema import (
    CreateFieldControl,
    CreateFieldOption,
    CreateFieldSchema,
)
from support.jira_integration.core.models import CreateIssueRequest
from support.jira_integration.core.third_party_bug import ThirdPartyBugAttachment
from tool.SmartHome.redmine.mapping import redmine_tracker_to_jira_type
from tool.SmartHome.redmine.models import RedmineIssueDetail, RedmineProject


@dataclass(frozen=True)
class CloneDraftError:
    field_id: str
    message: str
    blocking: bool = True


@dataclass(frozen=True)
class CloneDraftField:
    schema: CreateFieldSchema
    value: Any
    error: str = ""

    @property
    def field_id(self) -> str:
        return self.schema.field_id


@dataclass
class CloneDraft:
    source_id: str
    source_url: str
    fields: tuple[CloneDraftField, ...]
    source_attachments: tuple[ThirdPartyBugAttachment, ...] = ()

    @property
    def id(self) -> str:
        return self.source_id

    def value(self, field_id: str) -> Any:
        field = self._field(field_id)
        return field.value if field is not None else None

    @property
    def errors(self) -> tuple[CloneDraftError, ...]:
        return tuple(
            CloneDraftError(field_id=field.field_id, message=field.error)
            for field in self.fields
            if field.error
        )

    def update(self, field_id: str, value: Any) -> None:
        updated = []
        found = False
        for field in self.fields:
            if field.field_id != field_id:
                updated.append(field)
                continue
            found = True
            error = _validate_value(field.schema, value)
            updated.append(replace(field, value=value, error=error))
        if not found:
            raise KeyError(field_id)
        self.fields = tuple(updated)

    def to_request(self) -> CreateIssueRequest:
        controls = {
            field.field_id: field.schema.control.value
            for field in self.fields
            if field.value not in (None, "", [], {})
        }
        standard_ids = {
            "project",
            "issuetype",
            "summary",
            "description",
            "priority",
            "components",
        }
        extra_fields = {
            field.field_id: field.value
            for field in self.fields
            if field.field_id not in standard_ids and field.value not in (None, "", [], {})
        }
        return CreateIssueRequest(
            project_key=str(self.value("project") or ""),
            issue_type=str(self.value("issuetype") or ""),
            summary=str(self.value("summary") or ""),
            description=str(self.value("description") or ""),
            priority=str(self.value("priority") or ""),
            components=tuple(self.value("components") or ()),
            source_system="redmine",
            source_id=self.source_id,
            source_url=self.source_url,
            description_includes_source_identity=True,
            extra_fields=extra_fields,
            field_controls=controls,
        )

    def _field(self, field_id: str) -> CloneDraftField | None:
        return next((field for field in self.fields if field.field_id == field_id), None)


class RedmineCloneDraftService:
    def build(
        self,
        issue: RedmineIssueDetail,
        project: RedmineProject,
        schema: Iterable[CreateFieldSchema],
        account: str,
        department: str,
        prepared_description: str,
    ) -> CloneDraft:
        fields = tuple(
            _draft_field(
                item,
                issue=issue,
                project=project,
                account=str(account or "").strip(),
                department=str(department or "").strip(),
                prepared_description=str(prepared_description or ""),
            )
            for item in schema
        )
        return CloneDraft(
            source_id=issue.id,
            source_url=issue.url,
            fields=fields,
            source_attachments=issue.attachments,
        )


def _draft_field(
    schema: CreateFieldSchema,
    *,
    issue: RedmineIssueDetail,
    project: RedmineProject,
    account: str,
    department: str,
    prepared_description: str,
) -> CloneDraftField:
    initial = _initial_value(
        schema,
        issue=issue,
        project=project,
        account=account,
        department=department,
        prepared_description=prepared_description,
    )
    value, option_error = _resolve_options(schema, initial)
    error = option_error or _validate_value(schema, value)
    return CloneDraftField(schema=schema, value=value, error=error)


def _initial_value(
    schema: CreateFieldSchema,
    *,
    issue: RedmineIssueDetail,
    project: RedmineProject,
    account: str,
    department: str,
    prepared_description: str,
) -> Any:
    field_id = schema.field_id
    name = schema.name.strip().casefold()
    if field_id == "project" or name == "project":
        return "SH"
    if field_id == "issuetype" or name == "issue type":
        return redmine_tracker_to_jira_type(issue.tracker)
    if field_id == "summary" or name == "summary":
        return issue.subject
    if field_id == "description" or name == "description":
        return prepared_description
    if name == "attachment links":
        return issue.url
    if field_id == "priority" or name == "priority":
        return "P2"
    if field_id == "components" or name in {"component/s", "components"}:
        return ["Customization"]
    if name == "channel of reporter":
        return {"parent": "Customer-Feedback", "child": ""}
    if name == "severity":
        return "Major"
    if name == "product":
        return ["BDS Reference"]
    if name == "project id":
        return [project.project_id] if project.project_id else []
    if field_id == "reporter" or name == "reporter":
        return account
    if name in {"manager", "fae manager"}:
        return "fred.chen"
    if name == "fae coworker":
        return account if department == "FAE-SW" else ""
    if schema.value is not None:
        return schema.value
    if schema.control == CreateFieldControl.MULTI:
        return []
    if schema.control == CreateFieldControl.CASCADE:
        return {}
    return ""


def _resolve_options(schema: CreateFieldSchema, initial: Any) -> tuple[Any, str]:
    if not schema.options or initial in (None, "", [], {}):
        return initial, ""
    if schema.control == CreateFieldControl.CASCADE:
        parent_label = str((initial or {}).get("parent") or "")
        child_label = str((initial or {}).get("child") or "")
        parent = _find_option(schema.options, parent_label)
        child = _find_option(parent.children, child_label) if parent else None
        if parent is None or (child_label and child is None):
            return {}, f"Configured option is unavailable for {schema.name}"
        return {
            "parent": parent.value,
            "child": child.value if child else "",
        }, ""
    if schema.control == CreateFieldControl.MULTI:
        resolved = [_find_option(schema.options, str(label)) for label in initial]
        if any(item is None for item in resolved):
            return [], f"Configured option is unavailable for {schema.name}"
        return [item.value for item in resolved if item is not None], ""
    if schema.control == CreateFieldControl.SINGLE:
        resolved = _find_option(schema.options, str(initial))
        if resolved is None:
            return "", f"Configured option is unavailable for {schema.name}"
        return resolved.value, ""
    return initial, ""


def _find_option(
    options: Iterable[CreateFieldOption],
    label_or_value: str,
) -> CreateFieldOption | None:
    return next(
        (
            option
            for option in options
            if option.label == label_or_value or option.value == label_or_value
        ),
        None,
    )


def _validate_value(schema: CreateFieldSchema, value: Any) -> str:
    if schema.required and value in (None, "", [], {}):
        return f"{schema.name} is required"
    if not schema.options or value in (None, "", [], {}):
        return ""
    if schema.control == CreateFieldControl.CASCADE:
        if not isinstance(value, dict):
            return f"Invalid option for {schema.name}"
        parent = _find_option(schema.options, str(value.get("parent") or ""))
        child_value = str(value.get("child") or "")
        child = _find_option(parent.children, child_value) if parent and child_value else None
        return "" if parent and (not child_value or child) else f"Invalid option for {schema.name}"
    if schema.control == CreateFieldControl.MULTI:
        if not isinstance(value, (list, tuple)):
            return f"Invalid option for {schema.name}"
        return (
            ""
            if all(_find_option(schema.options, str(item)) for item in value)
            else f"Invalid option for {schema.name}"
        )
    if schema.control == CreateFieldControl.SINGLE:
        return "" if _find_option(schema.options, str(value)) else f"Invalid option for {schema.name}"
    return ""
