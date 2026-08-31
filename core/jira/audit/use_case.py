from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from core.jira.domain import Issue, IssueDetails

from .models import AuditReport, JiraAuditScope
from .rules import active_rules, audit_issue, is_audit_eligible


class JiraAuditIssueSource(Protocol):
    def list_issues(self, scope: JiraAuditScope, cancellation) -> tuple[Issue, ...]: ...
    def load_details(self, issue: Issue, details: IssueDetails) -> Issue: ...


class _NoCancellation:
    def raise_if_cancelled(self) -> None:
        return None


class JiraAuditUseCase:
    def __init__(self, source: JiraAuditIssueSource):
        self._source = source

    def run(
        self,
        scope: JiraAuditScope,
        *,
        cancellation=None,
        progress=lambda *_: None,
    ) -> AuditReport:
        token = cancellation or _NoCancellation()
        token.raise_if_cancelled()
        progress("fetching_issues", 0, 0)
        issues = self._source.list_issues(scope, token)
        token.raise_if_cancelled()
        results = []
        eligible = [issue for issue in issues if is_audit_eligible(issue)]
        for index, issue in enumerate(eligible, 1):
            token.raise_if_cancelled()
            progress("loading_details", index - 1, len(eligible))
            loaded = self._source.load_details(
                issue, IssueDetails(description=True),
            )
            token.raise_if_cancelled()
            progress("rule_auditing", index - 1, len(eligible))
            results.append(audit_issue(loaded))
        progress("finalizing", len(results), len(results))
        return AuditReport(
            scope, datetime.now(timezone.utc), active_rules(), tuple(results),
        )
