from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.confluence.project import ConfluencePageRef, ProductSpaceRef, Project, ProjectIdentity, ProjectMilestones, ProjectRole, SourceEvidence
from core.domain.detail import DetailSection
from core.domain.values import FieldBag, NamedValue, PersonRef, SourceRevision
from core.confluence.project_rules import canonical_project_role_id


class ConfluenceProjectMapper:
    def from_catalog(self, payload: dict[str, Any]) -> Project:
        fields = _mapping(payload.get("fields"))
        source = _mapping(payload.get("catalog_source"))
        page = ConfluencePageRef(
            str(payload.get("page_id") or ""),
            str(payload.get("name") or ""),
            str(payload.get("page_url") or ""),
        )
        owners = tuple(
            person for person in (_person(item) for item in payload.get("project_owners") or ()) if person
        )
        return Project(
            ProjectIdentity(str(payload.get("identity") or payload.get("page_id") or ""), str(payload.get("project_id") or "")),
            str(payload.get("name") or ""),
            ProductSpaceRef(str(payload.get("space_key") or ""), str(payload.get("space_name") or payload.get("space_key") or ""), str(payload.get("space_url") or "")),
            page,
            _named(fields.get("project status")),
            _named(fields.get("current stage")),
            _named(fields.get("support mode")),
            str(fields.get("oem/operator") or fields.get("customer") or ""),
            owners,
            SourceRevision(str(source.get("version") or "")),
            facts=DetailSection.loaded(
                FieldBag.from_mapping(fields),
                source_revision=str(source.get("version") or ""),
            ),
        )

    def with_sections(self, project: Project, payload: dict[str, Any], sections: tuple[str, ...]) -> Project:
        revision = project.revision.value
        changes: dict[str, Any] = {}
        if "roles" in sections:
            roles = tuple(
                ProjectRole(
                    NamedValue(canonical_project_role_id(role), str(role)),
                    tuple(person for person in (_person(item) for item in people or ()) if person),
                )
                for role, people in _mapping(payload.get("roles")).items()
            )
            changes["roles"] = DetailSection.loaded(roles, source_revision=revision)
        if "milestones" in sections:
            changes["milestones"] = DetailSection.loaded(ProjectMilestones(tuple((str(key), str(value)) for key, value in _mapping(payload.get("milestones")).items())), source_revision=revision)
        for name in ("hardware", "software", "facts"):
            if name in sections:
                changes[name] = DetailSection.loaded(FieldBag.from_mapping(_mapping(payload.get(name))), source_revision=revision)
        if "evidence" in sections:
            changes["evidence"] = DetailSection.loaded(tuple(_evidence(item) for item in payload.get("evidence") or ()), source_revision=revision)
        return replace(project, **changes)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _named(value: Any) -> NamedValue | None:
    if value in (None, "", {}):
        return None
    payload = _mapping(value)
    return NamedValue(str(payload.get("id") or ""), str(payload.get("name") or value))


def _person(value: Any) -> PersonRef | None:
    payload = _mapping(value)
    if not payload:
        return None
    identity = str(payload.get("identity") or payload.get("accountId") or payload.get("name") or "")
    return PersonRef(identity, str(payload.get("account") or ""), str(payload.get("name") or payload.get("displayName") or identity))


def _evidence(payload: dict[str, Any]) -> SourceEvidence:
    return SourceEvidence(str(payload.get("source") or payload.get("kind") or ""), ConfluencePageRef(str(payload.get("page_id") or ""), str(payload.get("title") or ""), str(payload.get("url") or ""), _int(payload.get("version"))))


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
