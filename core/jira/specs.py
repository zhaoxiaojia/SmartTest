from __future__ import annotations

from support.jira_integration.fields.specs import FieldSpec


def browse_specs() -> list[str | FieldSpec]:
    return [
        "key",
        "summary",
        "status",
        "assignee",
        "reporter",
        "priority",
        "labels",
        "updated",
        FieldSpec(name="project", path="fields.project.key", jira_fields=("project",)),
    ]


def detail_specs(*, include_comments: bool, include_links: bool) -> list[str | FieldSpec]:
    specs: list[str | FieldSpec] = [
        "key",
        "summary",
        "status",
        "assignee",
        "reporter",
        "priority",
        "labels",
        "updated",
        FieldSpec(name="project", path="fields.project.key", jira_fields=("project",)),
        FieldSpec(name="issueType", path="fields.issuetype.name", jira_fields=("issuetype",)),
        FieldSpec(name="resolution", path="fields.resolution.name", jira_fields=("resolution",)),
        FieldSpec(name="components", path="fields.components[].name", jira_fields=("components",)),
        FieldSpec(name="description", path="fields.description", jira_fields=("description",)),
        FieldSpec(name="attachments", path="fields.attachment[]", jira_fields=("attachment",)),
    ]
    if include_comments:
        specs.append(
            FieldSpec(
                name="comments",
                path="fields.comment.comments[].body",
                jira_fields=("comment",),
            )
        )
    if include_links:
        specs.append(
            FieldSpec(
                name="issuelinks",
                path="fields.issuelinks[]",
                jira_fields=("issuelinks",),
            )
        )
    return specs
