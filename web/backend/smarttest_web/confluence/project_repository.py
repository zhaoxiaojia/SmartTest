from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from typing import Callable, Iterable

from core.confluence.project import (
    ConfluencePageRef,
    ProductSpaceRef,
    Project,
    ProjectDetails,
    ProjectIdentity,
    ProjectMilestones,
    ProjectPage,
    ProjectQuery,
    ProjectRole,
    SourceEvidence,
)
from core.domain.detail import DetailSection, DetailState
from core.domain.values import FieldBag, NamedValue, PersonRef, SourceRevision

from ..database import WebDatabase
from .schema import initialize_confluence_schema


_SECTIONS = ("roles", "milestones", "hardware", "software", "facts", "evidence")


class ConfluenceProjectRepository:
    def __init__(self, database: WebDatabase):
        self.database = database
        initialize_confluence_schema(database)

    def get(self, project_id: str, details: ProjectDetails) -> Project | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM confluence_projects WHERE project_id=?", (project_id,)
            ).fetchone()
            if row is None:
                return None
            project = self._project_from_row(connection, row)
            changes = {
                section: self._load_section(connection, row[0], section)
                for section in details.sections()
            }
            return replace(project, **changes)

    def list(self, query: ProjectQuery, page: int = 0, page_size: int = 100, *, visible_ids=None) -> ProjectPage:
        clauses: list[str] = []
        parameters: list[str] = []
        if visible_ids is not None:
            identifiers = tuple(visible_ids)
            clauses.append(f"project_id IN ({','.join('?' for _ in identifiers)})")
            parameters.extend(identifiers)
        if query.search.strip():
            needle = f"%{query.search.strip()}%"
            clauses.append("(project_id LIKE ? OR name LIKE ? OR customer_summary LIKE ?)")
            parameters.extend((needle, needle, needle))
        columns = {
            "project status": "status_name", "status": "status_name",
            "current stage": "stage_name", "stage": "stage_name",
            "support mode": "support_mode_name",
            "product space": "product_space_key", "product line": "product_space_key",
        }
        for key, values in query.filters:
            column = columns.get(key.casefold())
            if column and values:
                clauses.append(f"{column} IN ({','.join('?' for _ in values)})")
                parameters.extend(values)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connect() as connection:
            total = int(connection.execute(
                f"SELECT count(*) FROM confluence_projects {where}", tuple(parameters)
            ).fetchone()[0])
            rows = connection.execute(
                f"SELECT * FROM confluence_projects {where} ORDER BY project_id LIMIT ? OFFSET ?",
                (*parameters, int(page_size), int(page) * int(page_size)),
            ).fetchall()
            projects = tuple(self._project_from_row(connection, row) for row in rows)
        return ProjectPage(projects, int(page), int(page_size), total)

    def save_core(self, projects: Iterable[Project]) -> None:
        cached_at = _now()
        with self.database.transaction() as connection:
            for project in projects:
                old = connection.execute(
                    "SELECT source_revision FROM confluence_projects WHERE confluence_id=?",
                    (project.identity.confluence_id,),
                ).fetchone()
                connection.execute(
                    """INSERT INTO confluence_projects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(confluence_id) DO UPDATE SET
                    project_id=excluded.project_id,name=excluded.name,
                    product_space_key=excluded.product_space_key,
                    product_space_name=excluded.product_space_name,
                    product_space_url=excluded.product_space_url,
                    catalog_page_id=excluded.catalog_page_id,
                    catalog_page_title=excluded.catalog_page_title,
                    catalog_page_url=excluded.catalog_page_url,
                    catalog_page_version=excluded.catalog_page_version,
                    status_id=excluded.status_id,status_name=excluded.status_name,
                    stage_id=excluded.stage_id,stage_name=excluded.stage_name,
                    support_mode_id=excluded.support_mode_id,
                    support_mode_name=excluded.support_mode_name,
                    customer_summary=excluded.customer_summary,
                    source_revision=excluded.source_revision,cached_at=excluded.cached_at""",
                    _project_values(project, cached_at),
                )
                connection.execute(
                    "DELETE FROM confluence_project_owners WHERE confluence_id=?",
                    (project.identity.confluence_id,),
                )
                connection.executemany(
                    "INSERT INTO confluence_project_owners VALUES(?,?,?,?)",
                    ((project.identity.confluence_id, *person_values(person)) for person in project.owner_summary),
                )
                for section in _SECTIONS:
                    connection.execute(
                        """INSERT OR IGNORE INTO confluence_project_detail_states
                        (confluence_id,section_name,state,source_revision,error_code,cached_at)
                        VALUES(?,?,'unloaded','','',?)""",
                        (project.identity.confluence_id, section, cached_at),
                    )
                if old is not None and str(old[0]) != project.revision.value:
                    connection.execute(
                        """UPDATE confluence_project_detail_states SET state='stale',cached_at=?
                        WHERE confluence_id=? AND state='loaded'""",
                        (cached_at, project.identity.confluence_id),
                    )

    def replace_roles(self, project_id: str, section: DetailSection[tuple[ProjectRole, ...]]) -> None:
        def write(connection, confluence_id):
            connection.execute("DELETE FROM confluence_project_roles WHERE confluence_id=?", (confluence_id,))
            for role in section.value or ():
                role_id = role.role.id or role.role.name
                connection.execute("INSERT INTO confluence_project_roles VALUES(?,?,?)", (confluence_id, role_id, role.role.name))
                connection.executemany(
                    "INSERT INTO confluence_project_role_people VALUES(?,?,?,?,?)",
                    ((confluence_id, role_id, *person_values(person)) for person in role.people),
                )
        self._replace(project_id, "roles", section, write)

    def replace_milestones(self, project_id: str, section: DetailSection[ProjectMilestones]) -> None:
        def write(connection, confluence_id):
            connection.execute("DELETE FROM confluence_project_milestones WHERE confluence_id=?", (confluence_id,))
            connection.executemany(
                "INSERT INTO confluence_project_milestones VALUES(?,?,?)",
                ((confluence_id, key, value) for key, value in (section.value.values if section.value else ())),
            )
        self._replace(project_id, "milestones", section, write)

    def replace_hardware(self, project_id: str, section: DetailSection[FieldBag]) -> None:
        self._replace_fields(project_id, "hardware", section)

    def replace_software(self, project_id: str, section: DetailSection[FieldBag]) -> None:
        self._replace_fields(project_id, "software", section)

    def replace_facts(self, project_id: str, section: DetailSection[FieldBag]) -> None:
        self._replace_fields(project_id, "facts", section)

    def replace_evidence(self, project_id: str, section: DetailSection[tuple[SourceEvidence, ...]]) -> None:
        def write(connection, confluence_id):
            connection.execute("DELETE FROM confluence_project_evidence WHERE confluence_id=?", (confluence_id,))
            connection.executemany(
                "INSERT INTO confluence_project_evidence VALUES(?,?,?,?,?,?)",
                ((confluence_id, item.source, item.page.page_id, item.page.title,
                  item.page.url, item.page.version) for item in section.value or ()),
            )
        self._replace(project_id, "evidence", section, write)

    def mark_details_stale(self, project_id: str, sections: Iterable[str]) -> None:
        names = tuple(name for name in sections if name in _SECTIONS)
        if not names:
            return
        placeholders = ",".join("?" for _ in names)
        with self.database.transaction() as connection:
            connection.execute(
                f"""UPDATE confluence_project_detail_states SET state='stale',cached_at=?
                WHERE confluence_id=(SELECT confluence_id FROM confluence_projects WHERE project_id=?)
                AND section_name IN ({placeholders}) AND state='loaded'""",
                (_now(), project_id, *names),
            )

    def delete(self, project_id: str) -> None:
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM confluence_projects WHERE project_id=?", (project_id,))

    def clear(self) -> None:
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM confluence_projects")
            connection.execute("DELETE FROM confluence_sync_state")

    def _replace_fields(self, project_id: str, name: str, section: DetailSection[FieldBag]) -> None:
        def write(connection, confluence_id):
            connection.execute(
                "DELETE FROM confluence_project_fields WHERE confluence_id=? AND section_name=?",
                (confluence_id, name),
            )
            for key, value in section.value.values if section.value is not None else ():
                connection.execute(
                    "INSERT INTO confluence_project_fields VALUES(?,?,?,?)",
                    (confluence_id, name, key, json.dumps(value, ensure_ascii=False)),
                )
        self._replace(project_id, name, section, write)

    def _replace(self, project_id: str, name: str, section: DetailSection, writer: Callable) -> None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT confluence_id FROM confluence_projects WHERE project_id=?", (project_id,)
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            writer(connection, row[0])
            connection.execute(
                """INSERT INTO confluence_project_detail_states
                (confluence_id,section_name,state,source_revision,error_code,has_value,cached_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(confluence_id,section_name) DO UPDATE SET
                state=excluded.state,source_revision=excluded.source_revision,
                error_code=excluded.error_code,has_value=excluded.has_value,
                cached_at=excluded.cached_at""",
                (row[0], name, section.state.value, section.source_revision,
                 section.error_code, int(section.value is not None), _now()),
            )

    def _project_from_row(self, connection, row) -> Project:
        owners = tuple(PersonRef(item[0], item[1], item[2]) for item in connection.execute(
            "SELECT identity,account,display_name FROM confluence_project_owners WHERE confluence_id=? ORDER BY identity",
            (row[0],),
        ))
        return Project(
            ProjectIdentity(row[0], row[1]), row[2], ProductSpaceRef(row[3], row[4], row[5]),
            ConfluencePageRef(row[6], row[7], row[8], int(row[9])),
            named(row[10], row[11]), named(row[12], row[13]), named(row[14], row[15]),
            row[16], owners, SourceRevision(row[17]),
        )

    def _load_section(self, connection, confluence_id: str, name: str) -> DetailSection:
        state = connection.execute(
            """SELECT state,source_revision,error_code,has_value FROM confluence_project_detail_states
            WHERE confluence_id=? AND section_name=?""", (confluence_id, name)
        ).fetchone()
        if state is None:
            return DetailSection()
        detail_state = DetailState(state[0])
        value = self._load_value(connection, confluence_id, name) if bool(state[3]) else None
        if value is None and bool(state[3]):
            value = _empty_value(name)
        return DetailSection(detail_state, value, state[1], state[2])

    @staticmethod
    def _load_value(connection, confluence_id: str, name: str):
        if name == "roles":
            roles = []
            for role_id, role_name in connection.execute(
                "SELECT role_id,role_name FROM confluence_project_roles WHERE confluence_id=? ORDER BY role_id", (confluence_id,)
            ):
                people = tuple(PersonRef(*row) for row in connection.execute(
                    "SELECT identity,account,display_name FROM confluence_project_role_people WHERE confluence_id=? AND role_id=? ORDER BY identity",
                    (confluence_id, role_id),
                ))
                roles.append(ProjectRole(NamedValue(role_id, role_name), people))
            return tuple(roles) if roles else None
        if name == "milestones":
            rows = tuple(connection.execute(
                "SELECT milestone_key,milestone_value FROM confluence_project_milestones WHERE confluence_id=? ORDER BY milestone_key", (confluence_id,)
            ))
            return ProjectMilestones(rows) if rows else None
        if name in {"hardware", "software", "facts"}:
            rows = tuple(connection.execute(
                "SELECT field_key,value_json FROM confluence_project_fields WHERE confluence_id=? AND section_name=? ORDER BY field_key", (confluence_id, name)
            ))
            return FieldBag(tuple((key, json.loads(value)) for key, value in rows)) if rows else None
        rows = tuple(connection.execute(
            "SELECT source,page_id,page_title,page_url,page_version FROM confluence_project_evidence WHERE confluence_id=? ORDER BY source,page_id", (confluence_id,)
        ))
        return tuple(SourceEvidence(row[0], ConfluencePageRef(row[1], row[2], row[3], int(row[4]))) for row in rows) if rows else None


def _project_values(project: Project, cached_at: str) -> tuple:
    return (
        project.identity.confluence_id, project.identity.project_id, project.name,
        project.product_space.key, project.product_space.name, project.product_space.url,
        project.catalog_page.page_id, project.catalog_page.title, project.catalog_page.url,
        project.catalog_page.version, *named_values(project.status), *named_values(project.stage),
        *named_values(project.support_mode), project.customer_summary,
        project.revision.value, cached_at,
    )


def person_values(person: PersonRef) -> tuple[str, str, str]:
    return person.identity, person.account, person.display_name


def named_values(value: NamedValue | None) -> tuple[str | None, str | None]:
    return (value.id, value.name) if value else (None, None)


def named(identity, name) -> NamedValue | None:
    return NamedValue(str(identity or ""), str(name or "")) if identity is not None or name is not None else None


def _empty_value(name: str):
    if name in {"roles", "evidence"}:
        return ()
    if name == "milestones":
        return ProjectMilestones()
    return FieldBag()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
