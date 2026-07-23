from __future__ import annotations

import re
from dataclasses import dataclass, field


def parse_terms(text: str) -> tuple[str, ...]:
    terms = re.split(r"[\s,，;；]+", str(text or ""))
    return tuple(dict.fromkeys(term.strip() for term in terms if term.strip()))


@dataclass(frozen=True)
class RedmineQueryBranch:
    kind: str
    project: str = ""
    conditions: tuple[tuple[str, str, tuple[str, ...]], ...] = field(default_factory=tuple)

    def params(self, page: int, per_page: int) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        for name, operator, values in self.conditions:
            params.extend((("f[]", name), (f"op[{name}]", operator)))
            params.extend((f"v[{name}][]", value) for value in values)
        params.extend((
            ("sort", "id:desc"),
            ("page", str(page)),
            ("per_page", str(per_page)),
            ("set_filter", "1"),
        ))
        return params


@dataclass(frozen=True)
class RedmineQuery:
    project: str = ""
    status: str = ""
    tracker: str = ""
    subject: str = ""
    text: str = ""
    issue_ids: tuple[str, ...] = field(default_factory=tuple)

    def _common(self) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
        conditions = []
        status = str(self.status or "").strip().casefold()
        if status not in ("", "all statuses"):
            operator = {"open": "o", "closed": "c"}.get(status)
            if not operator:
                raise ValueError(f"Unsupported Redmine status semantic: {self.status}")
            conditions.append(("status_id", operator, ()))
        tracker = str(self.tracker or "").strip()
        if tracker:
            if not tracker.isdecimal():
                raise ValueError(f"Redmine tracker must be a canonical option value: {tracker}")
            conditions.append(("tracker_id", "=", (tracker,)))
        subject = str(self.subject or "").strip()
        if subject:
            conditions.append(("subject", "~", (subject,)))
        return tuple(conditions)

    def branches(self) -> tuple[RedmineQueryBranch, ...]:
        common = self._common()
        terms = parse_terms(self.text)
        explicit_ids = tuple(dict.fromkeys(str(value).strip() for value in self.issue_ids if str(value).strip()))
        branches = []
        if terms:
            branches.append(RedmineQueryBranch("fulltext", self.project, common + (("any_searchable", "*~", terms),)))
        numeric_ids = tuple(dict.fromkeys((*explicit_ids, *(term for term in terms if term.isdecimal()))))
        for issue_id in numeric_ids:
            branches.append(RedmineQueryBranch("issue_id", self.project, common + (("issue_id", "=", (issue_id,)),)))
        if not branches:
            branches.append(RedmineQueryBranch("default", self.project, common))
        return tuple(branches)
