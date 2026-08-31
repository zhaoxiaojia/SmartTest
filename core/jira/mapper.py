from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from core.domain.detail import DetailSection
from core.domain.values import FieldBag, NamedValue, PersonRef, SourceRevision
from core.jira.domain import (
    Issue,
    IssueAttachment,
    IssueComment,
    IssueIdentity,
    IssueLink,
    IssueRef,
    JiraProjectRef,
    RichText,
)


class JiraIssueMapper:
    def __init__(self, base_url: str = "") -> None:
        self._base_url = base_url.rstrip("/")

    def from_search(self, payload: dict[str, Any]) -> Issue:
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
        key = str(payload.get("key") or "")
        project = _mapping(fields.get("project"))
        return Issue(
            identity=IssueIdentity(
                id=str(payload.get("id") or ""),
                key=key,
                web_url=f"{self._base_url}/browse/{key}" if self._base_url and key else str(payload.get("self") or ""),
            ),
            summary=str(fields.get("summary") or ""),
            project=JiraProjectRef(
                key=str(project.get("key") or ""),
                id=str(project.get("id") or ""),
                name=str(project.get("name") or ""),
            ),
            status=_named(fields.get("status")),
            issue_type=_named(fields.get("issuetype")),
            priority=_named(fields.get("priority")) if fields.get("priority") else None,
            assignee=_person(fields.get("assignee")),
            reporter=_person(fields.get("reporter")),
            created_at=_datetime(fields.get("created")),
            updated_at=_datetime(fields.get("updated")),
            labels=tuple(str(item) for item in fields.get("labels") or ()),
            revision=SourceRevision(str(fields.get("updated") or "")),
            creator=_person(fields.get("creator")),
            components=tuple(
                _named(item) for item in fields.get("components") or ()
            ),
            resolution=_named(fields.get("resolution")) if fields.get("resolution") else None,
        )

    def with_sections(self, issue: Issue, payload: dict[str, Any], sections: tuple[str, ...]) -> Issue:
        changes: dict[str, Any] = {}
        revision = issue.revision.value
        if "description" in sections:
            changes["description"] = DetailSection.loaded(RichText(payload.get("description")), source_revision=revision)
        if "comments" in sections:
            changes["comments"] = DetailSection.loaded(
                tuple(self._comment(item) for item in payload.get("comments") or ()),
                source_revision=revision,
            )
        if "attachments" in sections:
            changes["attachments"] = DetailSection.loaded(
                tuple(self._attachment(item) for item in payload.get("attachments") or ()),
                source_revision=revision,
            )
        if "links" in sections:
            changes["links"] = DetailSection.loaded(
                tuple(self._link(item) for item in payload.get("links") or ()),
                source_revision=revision,
            )
        if "custom_fields" in sections:
            changes["custom_fields"] = DetailSection.loaded(
                FieldBag.from_mapping(_mapping(payload.get("custom_fields"))),
                source_revision=revision,
            )
        return replace(issue, **changes)

    def ref(self, payload: dict[str, Any]) -> IssueRef:
        fields = _mapping(payload.get("fields"))
        key = str(payload.get("key") or "")
        return IssueRef(
            id=str(payload.get("id") or ""),
            key=key,
            web_url=f"{self._base_url}/browse/{key}" if self._base_url and key else str(payload.get("self") or ""),
            summary=str(fields.get("summary") or ""),
        )

    @staticmethod
    def _comment(payload: dict[str, Any]) -> IssueComment:
        return IssueComment(
            id=str(payload.get("id") or ""),
            body=payload.get("body"),
            author=_person(payload.get("author")),
            created_at=_datetime(payload.get("created")),
            updated_at=_datetime(payload.get("updated")),
        )

    @staticmethod
    def _attachment(payload: dict[str, Any]) -> IssueAttachment:
        size = payload.get("size")
        return IssueAttachment(
            id=str(payload.get("id") or ""),
            filename=str(payload.get("filename") or ""),
            url=str(payload.get("content") or payload.get("self") or ""),
            size=int(size) if isinstance(size, int) and not isinstance(size, bool) else None,
            author=_person(payload.get("author")),
        )

    def _link(self, payload: dict[str, Any]) -> IssueLink:
        outward = payload.get("outwardIssue")
        inward = payload.get("inwardIssue")
        linked = _mapping(outward or inward)
        link_type = _mapping(payload.get("type"))
        return IssueLink(
            id=str(payload.get("id") or ""),
            link_type=str(link_type.get("name") or ""),
            direction="outward" if outward else "inward",
            issue=self.ref(linked),
        )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _named(value: Any) -> NamedValue:
    payload = _mapping(value)
    return NamedValue(str(payload.get("id") or ""), str(payload.get("name") or value or ""))


def _person(value: Any) -> PersonRef | None:
    payload = _mapping(value)
    if not payload:
        return None
    return PersonRef(
        identity=str(payload.get("accountId") or payload.get("key") or payload.get("name") or ""),
        account=str(payload.get("name") or ""),
        display_name=str(payload.get("displayName") or payload.get("name") or ""),
    )


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    if len(text) >= 5 and text[-5] in "+-" and text[-3] != ":":
        text = f"{text[:-2]}:{text[-2:]}"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
