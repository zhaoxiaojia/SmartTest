from __future__ import annotations

from collections import Counter
from datetime import datetime
from uuid import uuid4

from support.logging import smart_log

from .discovery import discover_project_collection, discover_project_pages
from .models import (
    AuditBatch, AuditExecutionContext, ProjectAudit,
    ProjectCandidate, ProjectCollectionFilter,
)
from .rules import DISPLAY, StaticAuditService


class ConfluenceAuditService:
    def __init__(self, client):
        self.client = client
        self._rules = StaticAuditService()

    def run(
        self,
        criteria: ProjectCollectionFilter,
        period,
        context: AuditExecutionContext,
        progress=lambda *_: None,
    ):
        collection = discover_project_collection(
            self.client, criteria,
            lambda done, total: progress("discovering", done, total),
        )
        results = []
        for index, source in enumerate(collection.projects, 1):
            project = ProjectCandidate(
                source.status_page_id, source.project_id, source.name,
                source.status_url, source.home_url, source.year,
                source.support_mode, source.project_status,
                source.matching_years or (source.year,),
                source.space_key, source.page_identity,
            )
            progress("reviewing", index - 1, len(collection.projects))
            results.append(self._audit_project(project, period))
            progress("reviewing", index, len(collection.projects))
        batch = AuditBatch(
            datetime.now().strftime("%Y%m%dT%H%M%S") + uuid4().hex[:4],
            period, datetime.now(period.start.tzinfo), results,
            collection.filter, context,
        )
        return batch

    def _audit_project(self, project, period):
        try:
            discovered, discovery_errors = discover_project_pages(
                self.client, project, return_errors=True,
            )
        except Exception as exc:
            smart_log(
                "Confluence project page discovery failed",
                domain="confluence", source="project_audit", level="error",
                extra={
                    "project_id": project.project_id,
                    "exception_type": type(exc).__name__,
                },
            )
            findings = self._rules.audit(
                project, {}, period, unreadable=set(DISPLAY),
            )
            return ProjectAudit(project, findings)

        pages = {}
        unreadable = {
            kind for kind in discovery_errors if kind in DISPLAY
        }
        if any(key.startswith("branch:") for key in discovery_errors):
            unreadable.update(set(DISPLAY) - set(discovered))
        for kind, page in discovered.items():
            if kind in unreadable:
                continue
            try:
                pages[kind] = self.client.get_page(page.id)
            except Exception:
                unreadable.add(kind)

        attachments = {}
        report_page = pages.get("report_store")
        if report_page:
            try:
                attachments["report_store"] = self.client.get_attachments(
                    report_page.id,
                )
            except Exception:
                attachments["report_store"] = []

        findings = self._rules.audit(
            project, pages, period, attachments, unreadable,
        )
        smart_log(
            "Confluence project content audit completed",
            domain="confluence", source="project_audit",
            level="warning" if unreadable else "info",
            extra={
                "project_id": project.project_id,
                "page_count": len(pages),
                "unreadable_kinds": sorted(unreadable),
                "finding_counts": dict(sorted(Counter(
                    finding.status.value for finding in findings
                ).items())),
            },
        )
        return ProjectAudit(project, findings)
