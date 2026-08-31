from __future__ import annotations

from typing import Any

from core.jira.commands import CreateIssueCommand, UpdateIssueCommand
from core.jira.domain import Issue, IssueDetails, IssuePage, IssueRef
from core.jira.mapper import JiraIssueMapper


class IssueRepository:
    def __init__(self, gateway: Any, mapper: JiraIssueMapper | None = None) -> None:
        self._gateway = gateway
        self._mapper = mapper or JiraIssueMapper()

    def search(self, query: str, page: int = 0) -> IssuePage:
        payload = self._gateway.search_issues(query, page)
        rows = payload.get("issues") or ()
        page_size = int(payload.get("maxResults") or payload.get("page_size") or len(rows))
        start = int(payload.get("startAt") or 0)
        return IssuePage(
            tuple(self._mapper.from_search(row) for row in rows),
            int(payload.get("page") if payload.get("page") is not None else (start // page_size if page_size else page)),
            page_size,
            int(payload.get("total") or len(rows)),
        )

    def get(self, issue_key: str) -> Issue:
        return self._mapper.from_search(self._gateway.get_issue(issue_key))

    def load_details(self, issue: Issue, details: IssueDetails) -> Issue:
        sections = details.sections()
        if not sections:
            return issue
        payload = self._gateway.load_issue_sections(issue.identity.key, sections)
        return self._mapper.with_sections(issue, payload, sections)

    def find_for_external_url(self, project_key: str, external_url: str) -> IssueRef | None:
        payload = self._gateway.find_issue_for_external_url(project_key, external_url)
        return self._mapper.ref(payload) if payload else None

    def find_for_source(self, command: CreateIssueCommand) -> IssueRef | None:
        payload = self._gateway.find_issue_for_source(command)
        return self._mapper.ref(payload) if payload else None

    def create(self, command: CreateIssueCommand) -> IssueRef:
        return self._mapper.ref(self._gateway.create_issue(command))

    def update(self, command: UpdateIssueCommand) -> Issue:
        return self._mapper.from_search(self._gateway.update_issue(command))
