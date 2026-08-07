"""Persistent project configuration for the Daily Report owner."""

from __future__ import annotations

from email.headerregistry import Address
import json
from pathlib import Path
import re

from .report import PROJECTS, ProjectConfig


class ProjectConfigStore:
    def __init__(self, path: str | Path, *, defaults=PROJECTS):
        self.path = Path(path)
        self._defaults = tuple(defaults)

    def list(self) -> tuple[ProjectConfig, ...]:
        if not self.path.is_file():
            self._write(self._defaults)
            return self._defaults
        values = json.loads(self.path.read_text("utf-8"))
        projects = tuple(self._from_payload(value) for value in values)
        self._validate_collection(projects)
        return projects

    def enabled(self) -> tuple[ProjectConfig, ...]:
        return tuple(project for project in self.list() if project.enabled)

    def revision(self) -> tuple:
        return tuple(
            (project.safe_id, project.name, project.label, project.jql,
             project.to, project.cc, project.enabled, project.subject,
             project.detail_priorities)
            for project in self.list()
        )

    def load(self, safe_id: str) -> ProjectConfig:
        return next(
            project for project in self.list() if project.safe_id == str(safe_id)
        )

    def save(self, value: dict | ProjectConfig) -> ProjectConfig:
        projects = list(self.list())
        if isinstance(value, ProjectConfig):
            project = value
        else:
            payload = dict(value)
            if not str(payload.get("safe_id", payload.get("id", ""))).strip():
                payload["safe_id"] = _new_id(
                    str(payload.get("name", "")),
                    {item.safe_id for item in projects},
                )
            project = self._from_payload(payload)
        index = next(
            (i for i, item in enumerate(projects) if item.safe_id == project.safe_id),
            None,
        )
        if index is None:
            projects.append(project)
        else:
            projects[index] = project
        self._validate_collection(tuple(projects))
        self._write(tuple(projects))
        return project

    def delete(self, safe_id: str) -> None:
        projects = tuple(
            project for project in self.list() if project.safe_id != str(safe_id)
        )
        if not projects:
            raise ValueError("Daily Report must keep at least one project")
        self._write(projects)

    def set_enabled(self, safe_id: str, enabled: bool) -> ProjectConfig:
        current = self.load(safe_id)
        return self.save(
            ProjectConfig(
                current.safe_id, current.name, current.label, current.jql,
                current.to, current.cc, bool(enabled), current.subject,
                current.detail_priorities,
            )
        )

    @staticmethod
    def to_payload(project: ProjectConfig) -> dict:
        return {
            "safe_id": project.safe_id, "name": project.name,
            "label": project.label, "jql": project.jql,
            "to": list(project.to), "cc": list(project.cc),
            "enabled": project.enabled,
            "subject": project.subject,
            "detail_priorities": list(project.detail_priorities),
        }

    def _from_payload(self, value: dict) -> ProjectConfig:
        safe_id = str(value.get("safe_id", value.get("id", ""))).strip()
        name = str(value.get("name", "")).strip()
        jql = str(value.get("jql", "")).strip()
        label = str(value.get("label", "")).strip() or _label_from_jql(jql)
        subject = str(value.get("subject", "")).strip()
        project = ProjectConfig(
            safe_id, name, label, jql,
            _emails(value.get("to", ())), _emails(value.get("cc", ())),
            bool(value.get("enabled", True)),
            subject,
            tuple(value.get("detail_priorities", ("P0", "P1"))),
        )
        if not project.safe_id or not project.name or not project.jql or not project.to or not project.subject:
            raise ValueError("Project id, name, JQL and To are required")
        return project

    @staticmethod
    def _validate_collection(projects: tuple[ProjectConfig, ...]) -> None:
        if not projects:
            raise ValueError("Daily Report must keep at least one project")
        ids = [project.safe_id.casefold() for project in projects]
        names = [project.name.casefold() for project in projects]
        if len(ids) != len(set(ids)):
            raise ValueError("Project id must be unique")
        if len(names) != len(set(names)):
            raise ValueError("Project name must be unique")

    def _write(self, projects: tuple[ProjectConfig, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                [self.to_payload(project) for project in projects],
                ensure_ascii=False, indent=2,
            ), encoding="utf-8",
        )
        temporary.replace(self.path)


def _emails(value) -> tuple[str, ...]:
    if isinstance(value, str):
        values = re.split(r"[,;\r\n]+", value)
    else:
        values = value or ()
    result = []
    for raw in values:
        address = str(raw).strip()
        if not address:
            continue
        if "@" not in address:
            address += "@amlogic.com"
        try:
            parsed = Address(addr_spec=address)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid project email address") from exc
        normalized = parsed.addr_spec
        if normalized.casefold() not in {item.casefold() for item in result}:
            result.append(normalized)
    return tuple(result)


def _label_from_jql(jql: str) -> str:
    match = re.search(r"\blabels?\s*=\s*([\w.-]+)", jql, re.IGNORECASE)
    return "" if match is None else match.group(1)


def _new_id(name: str, existing: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(name).casefold()).strip("-") or "project"
    candidate, suffix = base, 2
    folded = {value.casefold() for value in existing}
    while candidate.casefold() in folded:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
