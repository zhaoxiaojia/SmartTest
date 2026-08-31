from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


_DETAIL_STATES = frozenset({"unloaded", "loading", "loaded", "failed"})


@dataclass(frozen=True)
class RedmineIssue:
    id: str = ""
    key: str = ""
    source_url: str = ""
    title: str = ""
    web_url: str = ""
    project: dict[str, Any] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)
    issue_type: dict[str, Any] = field(default_factory=dict)
    priority: dict[str, Any] = field(default_factory=dict)
    assignee: dict[str, Any] = field(default_factory=dict)
    reporter: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    description: str = ""
    detail_fields: list[dict[str, Any]] = field(default_factory=list)
    people_fields: list[dict[str, Any]] = field(default_factory=list)
    date_fields: list[dict[str, Any]] = field(default_factory=list)
    extra_sections: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    detail_state: str = "unloaded"
    detail_error: str = ""
    clone: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.detail_state not in _DETAIL_STATES:
            raise ValueError(f"Invalid detail_state: {self.detail_state}")

    def to_dict(self) -> dict[str, Any]:
        return _json_copy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RedmineIssue":
        return cls(**_json_copy(data))


class RedmineIssueStore:
    def __init__(self, issues: Iterable[RedmineIssue] = ()) -> None:
        self._issue_list: list[RedmineIssue] = []
        self._selected_id: str | None = None
        self.replace_all(issues)

    @property
    def issue_list(self) -> tuple[RedmineIssue, ...]:
        return tuple(_copy_issue(issue) for issue in self._issue_list)

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    @property
    def selected_issue(self) -> RedmineIssue | None:
        return self.get(self._selected_id) if self._selected_id is not None else None

    def replace_all(self, issues: Iterable[RedmineIssue]) -> None:
        replacements: list[RedmineIssue] = []
        issue_ids: set[str] = set()
        for issue in issues:
            issue_id = _validated_issue_id(issue)
            if issue_id in issue_ids:
                raise ValueError(f"Duplicate issue id: {issue_id}")
            issue_ids.add(issue_id)
            replacements.append(_copy_issue(issue))
        self._issue_list = replacements
        if self._selected_id not in issue_ids:
            self._selected_id = None

    def upsert(self, issue: RedmineIssue) -> RedmineIssue:
        _validated_issue_id(issue)
        replacement = _copy_issue(issue)
        index = self._index_of(issue.id)
        if index is None:
            self._issue_list.append(replacement)
        else:
            self._issue_list[index] = replacement
        return _copy_issue(replacement)

    def patch(self, issue_id: str, **changes: Any) -> RedmineIssue:
        index = self._index_of(issue_id)
        if index is None:
            raise KeyError(issue_id)
        if "id" in changes and changes["id"] != issue_id:
            raise ValueError("Issue id cannot be changed by patch")
        payload = self._issue_list[index].to_dict()
        payload.update(changes)
        replacement = RedmineIssue.from_dict(payload)
        self._issue_list[index] = replacement
        return _copy_issue(replacement)

    def get(self, issue_id: str) -> RedmineIssue | None:
        index = self._index_of(issue_id)
        return _copy_issue(self._issue_list[index]) if index is not None else None

    def snapshot(self) -> dict[str, Any]:
        return {
            "issue_list": [issue.to_dict() for issue in self._issue_list],
            "selected_id": self._selected_id,
        }

    def select(self, issue_id: str | None) -> RedmineIssue | None:
        if issue_id is None:
            self._selected_id = None
            return None
        issue = self.get(issue_id)
        if issue is None:
            raise KeyError(issue_id)
        self._selected_id = issue_id
        return issue

    def _index_of(self, issue_id: str) -> int | None:
        return next((index for index, issue in enumerate(self._issue_list) if issue.id == issue_id), None)


def _copy_issue(issue: RedmineIssue) -> RedmineIssue:
    return RedmineIssue.from_dict(issue.to_dict())


def _validated_issue_id(issue: RedmineIssue) -> str:
    if not isinstance(issue.id, str) or not issue.id.strip():
        raise ValueError("Issue id cannot be empty")
    return issue.id


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
