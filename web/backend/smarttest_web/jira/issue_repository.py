from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from typing import Callable, Iterable

from core.domain.detail import DetailSection, DetailState
from core.domain.values import FieldBag, NamedValue, PersonRef, SourceRevision
from core.jira.domain import (
    Issue,
    IssueAttachment,
    IssueComment,
    IssueDetails,
    IssueIdentity,
    IssueLink,
    IssuePage,
    IssueRef,
    JiraProjectRef,
    RichText,
)

from ..database import WebDatabase
from .schema import initialize_jira_schema


_SECTIONS = ("description", "comments", "attachments", "links", "custom_fields")


class JiraIssueRepository:
    def __init__(self, database: WebDatabase):
        self.database = database
        initialize_jira_schema(database)

    def get(self, issue_key: str, details: IssueDetails) -> Issue | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jira_issues WHERE issue_key=?", (issue_key,)
            ).fetchone()
            if row is None:
                return None
            issue = self._issue_from_row(connection, row)
            changes = {
                section: self._load_section(connection, row[0], section)
                for section in details.sections()
            }
            return replace(issue, **changes)

    def list(self, query: str = "", page: int = 0, page_size: int = 100) -> IssuePage:
        with self.database.connect() as connection:
            total = int(connection.execute("SELECT count(*) FROM jira_issues").fetchone()[0])
            rows = connection.execute(
                "SELECT * FROM jira_issues ORDER BY issue_key LIMIT ? OFFSET ?",
                (int(page_size), int(page) * int(page_size)),
            ).fetchall()
            issues = tuple(self._issue_from_row(connection, row) for row in rows)
        return IssuePage(issues, int(page), int(page_size), total)

    def save_core(self, issues: Iterable[Issue]) -> None:
        cached_at = _now()
        with self.database.transaction() as connection:
            for issue in issues:
                old = connection.execute(
                    "SELECT source_revision FROM jira_issues WHERE issue_id=?",
                    (issue.identity.id,),
                ).fetchone()
                connection.execute(
                    """INSERT INTO jira_issues VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(issue_id) DO UPDATE SET
                    issue_key=excluded.issue_key,web_url=excluded.web_url,summary=excluded.summary,
                    project_id=excluded.project_id,project_key=excluded.project_key,
                    project_name=excluded.project_name,status_id=excluded.status_id,
                    status_name=excluded.status_name,issue_type_id=excluded.issue_type_id,
                    issue_type_name=excluded.issue_type_name,priority_id=excluded.priority_id,
                    priority_name=excluded.priority_name,assignee_identity=excluded.assignee_identity,
                    assignee_account=excluded.assignee_account,
                    assignee_display_name=excluded.assignee_display_name,
                    reporter_identity=excluded.reporter_identity,
                    reporter_account=excluded.reporter_account,
                    reporter_display_name=excluded.reporter_display_name,
                    created_at=excluded.created_at,updated_at=excluded.updated_at,
                    source_revision=excluded.source_revision,cached_at=excluded.cached_at,
                    creator_identity=excluded.creator_identity,
                    creator_account=excluded.creator_account,
                    creator_display_name=excluded.creator_display_name,
                    resolution_id=excluded.resolution_id,
                    resolution_name=excluded.resolution_name""",
                    _issue_values(issue, cached_at),
                )
                connection.execute(
                    "DELETE FROM jira_issue_labels WHERE issue_id=?", (issue.identity.id,)
                )
                connection.executemany(
                    "INSERT INTO jira_issue_labels(issue_id,label) VALUES(?,?)",
                    ((issue.identity.id, label) for label in issue.labels),
                )
                connection.execute(
                    "DELETE FROM jira_issue_components WHERE issue_id=?", (issue.identity.id,)
                )
                connection.executemany(
                    "INSERT INTO jira_issue_components(issue_id,component_id,component_name) VALUES(?,?,?)",
                    (
                        (issue.identity.id, component.id, component.name)
                        for component in issue.components
                    ),
                )
                for section in _SECTIONS:
                    connection.execute(
                        """INSERT OR IGNORE INTO jira_issue_detail_states
                        (issue_id,section_name,state,source_revision,error_code,cached_at)
                        VALUES(?,?,'unloaded','','',?)""",
                        (issue.identity.id, section, cached_at),
                    )
                if old is not None and str(old[0]) != issue.revision.value:
                    connection.execute(
                        """UPDATE jira_issue_detail_states SET state='stale',cached_at=?
                        WHERE issue_id=? AND state='loaded'""",
                        (cached_at, issue.identity.id),
                    )

    def replace_description(self, issue_key: str, section: DetailSection[RichText]) -> None:
        def write(connection, issue_id):
            connection.execute("DELETE FROM jira_issue_descriptions WHERE issue_id=?", (issue_id,))
            if section.value is not None:
                encoded = json.dumps(section.value.value, ensure_ascii=False)
                connection.execute(
                    "INSERT INTO jira_issue_descriptions(issue_id,content_json) VALUES(?,?)",
                    (issue_id, encoded),
                )
        self._replace(issue_key, "description", section, write)

    def replace_comments(self, issue_key: str, section: DetailSection[tuple[IssueComment, ...]]) -> None:
        def write(connection, issue_id):
            connection.execute("DELETE FROM jira_issue_comments WHERE issue_id=?", (issue_id,))
            for item in section.value or ():
                connection.execute(
                    "INSERT INTO jira_issue_comments VALUES(?,?,?,?,?,?,?,?)",
                    (issue_id, item.id, json.dumps(item.body, ensure_ascii=False),
                     *_person_values(item.author), _time(item.created_at), _time(item.updated_at)),
                )
        self._replace(issue_key, "comments", section, write)

    def replace_attachments(self, issue_key: str, section: DetailSection[tuple[IssueAttachment, ...]]) -> None:
        def write(connection, issue_id):
            connection.execute("DELETE FROM jira_issue_attachments WHERE issue_id=?", (issue_id,))
            for item in section.value or ():
                connection.execute(
                    "INSERT INTO jira_issue_attachments VALUES(?,?,?,?,?,?,?,?)",
                    (issue_id, item.id, item.filename, item.url, item.size, *_person_values(item.author)),
                )
        self._replace(issue_key, "attachments", section, write)

    def replace_links(self, issue_key: str, section: DetailSection[tuple[IssueLink, ...]]) -> None:
        def write(connection, issue_id):
            connection.execute("DELETE FROM jira_issue_links WHERE issue_id=?", (issue_id,))
            for item in section.value or ():
                connection.execute(
                    "INSERT INTO jira_issue_links VALUES(?,?,?,?,?,?,?,?,?)",
                    (issue_id, item.id, item.link_type, item.direction, item.issue.id,
                     item.issue.key, item.issue.web_url, item.issue.summary),
                )
        self._replace(issue_key, "links", section, write)

    def replace_custom_fields(self, issue_key: str, section: DetailSection[FieldBag]) -> None:
        def write(connection, issue_id):
            connection.execute("DELETE FROM jira_issue_custom_fields WHERE issue_id=?", (issue_id,))
            for key, value in section.value.values if section.value is not None else ():
                connection.execute(
                    "INSERT INTO jira_issue_custom_fields VALUES(?,?,?)",
                    (issue_id, key, json.dumps(value, ensure_ascii=False)),
                )
        self._replace(issue_key, "custom_fields", section, write)

    def mark_details_stale(self, issue_key: str, sections: Iterable[str]) -> None:
        names = tuple(name for name in sections if name in _SECTIONS)
        if not names:
            return
        placeholders = ",".join("?" for _ in names)
        with self.database.transaction() as connection:
            connection.execute(
                f"""UPDATE jira_issue_detail_states SET state='stale',cached_at=?
                WHERE issue_id=(SELECT issue_id FROM jira_issues WHERE issue_key=?)
                AND section_name IN ({placeholders}) AND state='loaded'""",
                (_now(), issue_key, *names),
            )

    def delete(self, issue_key: str) -> None:
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_issues WHERE issue_key=?", (issue_key,))

    def clear(self) -> None:
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM jira_issues")
            connection.execute("DELETE FROM jira_sync_state")

    def _replace(self, issue_key: str, name: str, section: DetailSection, writer: Callable) -> None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT issue_id FROM jira_issues WHERE issue_key=?", (issue_key,)
            ).fetchone()
            if row is None:
                raise KeyError(issue_key)
            writer(connection, row[0])
            connection.execute(
                """INSERT INTO jira_issue_detail_states
                (issue_id,section_name,state,source_revision,error_code,has_value,cached_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(issue_id,section_name) DO UPDATE SET
                state=excluded.state,source_revision=excluded.source_revision,
                error_code=excluded.error_code,has_value=excluded.has_value,
                cached_at=excluded.cached_at""",
                (row[0], name, section.state.value, section.source_revision,
                 section.error_code, int(section.value is not None), _now()),
            )

    def _issue_from_row(self, connection, row) -> Issue:
        labels = tuple(item[0] for item in connection.execute(
            "SELECT label FROM jira_issue_labels WHERE issue_id=? ORDER BY label", (row[0],)
        ))
        components = tuple(
            NamedValue(item[0], item[1])
            for item in connection.execute(
                "SELECT component_id,component_name FROM jira_issue_components "
                "WHERE issue_id=? ORDER BY component_id,component_name", (row[0],),
            )
        )
        return Issue(
            IssueIdentity(row[0], row[1], row[2]), row[3],
            JiraProjectRef(row[5], row[4], row[6]),
            NamedValue(row[7], row[8]), NamedValue(row[9], row[10]),
            _named(row[11], row[12]), _person(row[13:16]), _person(row[16:19]),
            _datetime(row[19]), _datetime(row[20]), labels, SourceRevision(row[21]),
            _person(row[23:26]), components, _named(row[26], row[27]),
        )

    def _load_section(self, connection, issue_id: str, name: str) -> DetailSection:
        state = connection.execute(
            """SELECT state,source_revision,error_code,has_value FROM jira_issue_detail_states
            WHERE issue_id=? AND section_name=?""", (issue_id, name)
        ).fetchone()
        if state is None:
            return DetailSection()
        detail_state = DetailState(state[0])
        value = self._load_value(connection, issue_id, name) if bool(state[3]) else None
        return DetailSection(detail_state, value, state[1], state[2])

    @staticmethod
    def _load_value(connection, issue_id: str, name: str):
        if name == "description":
            row = connection.execute("SELECT content_json FROM jira_issue_descriptions WHERE issue_id=?", (issue_id,)).fetchone()
            return RichText(json.loads(row[0])) if row else None
        if name == "comments":
            return tuple(IssueComment(row[0], json.loads(row[1]), _person(row[2:5]), _datetime(row[5]), _datetime(row[6])) for row in connection.execute(
                "SELECT comment_id,body_json,author_identity,author_account,author_display_name,created_at,updated_at FROM jira_issue_comments WHERE issue_id=? ORDER BY comment_id", (issue_id,)))
        if name == "attachments":
            return tuple(IssueAttachment(row[0], row[1], row[2], row[3], _person(row[4:7])) for row in connection.execute(
                "SELECT attachment_id,filename,url,size,author_identity,author_account,author_display_name FROM jira_issue_attachments WHERE issue_id=? ORDER BY attachment_id", (issue_id,)))
        if name == "links":
            return tuple(IssueLink(row[0], row[1], row[2], IssueRef(row[3], row[4], row[5], row[6])) for row in connection.execute(
                "SELECT link_id,link_type,direction,target_id,target_key,target_web_url,target_summary FROM jira_issue_links WHERE issue_id=? ORDER BY link_id", (issue_id,)))
        return FieldBag(tuple((row[0], json.loads(row[1])) for row in connection.execute(
            "SELECT field_key,value_json FROM jira_issue_custom_fields WHERE issue_id=? ORDER BY field_key", (issue_id,))))


def _issue_values(issue: Issue, cached_at: str) -> tuple:
    return (
        issue.identity.id, issue.identity.key, issue.identity.web_url, issue.summary,
        issue.project.id, issue.project.key, issue.project.name,
        issue.status.id, issue.status.name, issue.issue_type.id, issue.issue_type.name,
        issue.priority.id if issue.priority else None,
        issue.priority.name if issue.priority else None,
        *_person_values(issue.assignee), *_person_values(issue.reporter),
        _time(issue.created_at), _time(issue.updated_at), issue.revision.value, cached_at,
        *_person_values(issue.creator),
        issue.resolution.id if issue.resolution else None,
        issue.resolution.name if issue.resolution else None,
    )


def _person_values(person: PersonRef | None) -> tuple[str | None, str | None, str | None]:
    return (person.identity, person.account, person.display_name) if person else (None, None, None)


def _person(values) -> PersonRef | None:
    return PersonRef(str(values[0]), str(values[1] or ""), str(values[2] or "")) if values[0] is not None else None


def _named(identity, name) -> NamedValue | None:
    return NamedValue(str(identity or ""), str(name or "")) if identity is not None or name is not None else None


def _time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
