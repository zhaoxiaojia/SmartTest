from __future__ import annotations

from typing import Protocol

from core.jira.domain import Issue


class IssueHistoryRepository(Protocol):
    def append(self, issue: Issue) -> None: ...
