from __future__ import annotations

from typing import Protocol

from core.confluence.project import Project


class ProjectHistoryRepository(Protocol):
    def append(self, project: Project) -> None: ...
