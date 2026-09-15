from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _name(value: Any) -> str:
    return str(value.get("name") or "") if isinstance(value, dict) else ""


_PERSONNEL_PATH = Path(__file__).resolve().parents[2] / "config" / "personnel.json"
TEAM_BUG_PROJECTS = (("DOPL", "IPTV"), ("SDPL", "SH"), ("TV", "TV"), ("OOPL", "OTT"))


@dataclass(frozen=True)
class QARoster:
    accounts: tuple[str, ...]
    fingerprint: str


def load_fae_qa_roster(path: str | Path = _PERSONNEL_PATH) -> QARoster:
    personnel = json.loads(Path(path).read_text(encoding="utf-8"))
    employees = personnel["amlogic"]["departments"]["FAE-QA"]["employees"]
    accounts = tuple(sorted({
        str(employee.get("account") or "").strip().casefold()
        for employee in employees
        if employee.get("active") is not False and str(employee.get("account") or "").strip()
    }))
    encoded = json.dumps(
        {"accounts": accounts, "projects": TEAM_BUG_PROJECTS},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    return QARoster(accounts, hashlib.sha256(encoded).hexdigest())


def team_bug_jql(accounts: Iterable[str]) -> str:
    quoted = [f'"{str(account).replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
              for account in accounts]
    projects = ", ".join(f'"{project}"' for _line, project in TEAM_BUG_PROJECTS)
    return f"issuetype = Bug AND assignee IN ({', '.join(quoted)}) AND project IN ({projects})"


@dataclass(frozen=True)
class TeamBugPerson:
    identity: str
    displayName: str
    bugCount: int
    resolvedCount: int
    p0Count: int
    invalidCount: int


@dataclass(frozen=True)
class TeamBugProductLine:
    id: str
    projectKey: str
    people: tuple[TeamBugPerson, ...]


@dataclass(frozen=True)
class TeamBugOverview:
    teamTotal: int
    productLines: tuple[TeamBugProductLine, ...]

    def to_payload(self) -> dict[str, Any]:
        return {"teamTotal": self.teamTotal, "productLines": [{
            "id": line.id, "projectKey": line.projectKey,
            "people": [asdict(person) for person in line.people],
        } for line in self.productLines]}


def aggregate_team_bugs(issues: Iterable[dict[str, Any]], accounts: Iterable[str]) -> TeamBugOverview:
    allowed = {str(account).strip().casefold() for account in accounts}
    people: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {
        "identity": "", "displayName": "", "bugCount": 0,
        "resolvedCount": 0, "p0Count": 0, "invalidCount": 0,
    }))
    project_to_line = {project: line for line, project in TEAM_BUG_PROJECTS}
    total = 0
    for issue in issues:
        fields = issue.get("fields") if isinstance(issue, dict) else None
        if not isinstance(fields, dict) or _name(fields.get("issuetype")) != "Bug":
            continue
        assignee = fields.get("assignee")
        if not isinstance(assignee, dict):
            continue
        identity = str(assignee.get("name") or assignee.get("accountId") or assignee.get("key") or "").strip().casefold()
        display_name = str(assignee.get("displayName") or identity)
        if identity not in allowed:
            continue
        project = fields.get("project")
        project_key = str(project.get("key") or "") if isinstance(project, dict) else ""
        product_line = project_to_line.get(project_key)
        if product_line is None:
            continue
        row = people[product_line][identity]
        row["identity"], row["displayName"] = identity, display_name
        row["bugCount"] += 1
        row["resolvedCount"] += _name(fields.get("resolution")) == "Resolved"
        row["p0Count"] += _name(fields.get("priority")) == "P0"
        row["invalidCount"] += _name(fields.get("resolution")) == "Invalid"
        total += 1

    product_lines = []
    for line, project in TEAM_BUG_PROJECTS:
        rows = [TeamBugPerson(**row) for row in people[line].values()]
        rows.sort(key=lambda row: (-row.bugCount, row.displayName.casefold(), row.identity))
        product_lines.append(TeamBugProductLine(line, project, tuple(rows)))
    return TeamBugOverview(total, tuple(product_lines))
