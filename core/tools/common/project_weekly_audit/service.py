from __future__ import annotations

from datetime import datetime
import hashlib
from uuid import uuid4

from core.logging import smart_log

from .discovery import discover_project_collection, discover_project_pages
from .models import (
    AuditBatch,
    AuditExecutionContext,
    AuditFinding,
    AuditStatus,
    MISSING_QA,
    ProjectAudit,
    ProjectCandidate,
    ProjectCollectionFilter,
    UPDATE_MATRIX_POINTS,
)
from .regions import extract_page_region, extract_project_owner


class ConfluenceAuditService:
    def __init__(self, client):
        self.client = client

    def run(
        self,
        criteria: ProjectCollectionFilter,
        period,
        context: AuditExecutionContext,
        progress=lambda *_: None,
    ):
        audit_id = datetime.now().strftime("%Y%m%dT%H%M%S") + uuid4().hex[:4]
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
            results.append(self._audit_project(project, period, audit_id))
            progress("reviewing", index, len(collection.projects))
        selected_line_keys = {key.casefold() for key in criteria.product_line_keys}
        batch = AuditBatch(
            audit_id,
            period,
            datetime.now(period.start.tzinfo),
            results,
            collection.filter,
            context,
            tuple(
                line for line in collection.product_lines
                if not selected_line_keys
                or line.key.casefold() in selected_line_keys
            ),
        )
        smart_log(
            "Confluence project weekly audit completed",
            domain="confluence", source="project_audit",
            extra={
                "audit_id": audit_id,
                "period_start": period.start.isoformat(),
                "period_end": period.end.isoformat(),
                "timezone": str(period.start.tzinfo),
                "project_count": len(results),
                "attention_point_count": len(UPDATE_MATRIX_POINTS),
                "status_counts": {
                    state.value: sum(
                        finding.status is state
                        for result in results for finding in result.findings
                    )
                    for state in (
                        AuditStatus.UPDATED, AuditStatus.NOT_UPDATED,
                        AuditStatus.INVALID_FORMAT,
                    )
                },
            },
        )
        return batch

    def _audit_project(self, project, period, audit_id=""):
        try:
            pages, errors = discover_project_pages(
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
            pages = {}
            errors = {
                point.page_kind: (
                    f"{type(exc).__name__}|projectId={project.project_id}"
                )
                for point in UPDATE_MATRIX_POINTS
            }

        branch_error = next(
            (value for key, value in errors.items() if key.startswith("branch:")),
            "",
        )
        owner = MISSING_QA
        status_page = pages.get("status")
        if status_page is not None:
            try:
                owner_page = (
                    status_page
                    if status_page.body or status_page.view_body
                    else self.client.get_page(status_page.id)
                )
            except Exception:
                pass
            else:
                owner = extract_project_owner(owner_page)
        findings = []
        page_kinds = dict.fromkeys(
            point.page_kind for point in UPDATE_MATRIX_POINTS
        )
        for page_kind in page_kinds:
            points = tuple(
                point for point in UPDATE_MATRIX_POINTS
                if point.page_kind == page_kind
            )
            page = pages.get(page_kind)
            diagnostic = errors.get(page_kind, "") or (
                branch_error if page is None else ""
            )
            if page is None or diagnostic:
                for point in points:
                    finding = self._invalid_finding(
                        project, point, page, diagnostic,
                    )
                    findings.append(finding)
                    self._log_rule_trace(
                        audit_id, project, point, page, (), (), False,
                        finding, read_error=diagnostic,
                    )
                continue
            findings.extend(self._audit_page_regions(
                project, page, points, period, audit_id,
            ))
        smart_log(
            "Confluence project update matrix completed",
            domain="confluence",
            source="project_audit",
            level=(
                "warning"
                if any(row.status is AuditStatus.INVALID_FORMAT for row in findings)
                else "info"
            ),
            extra={
                "project_id": project.project_id,
                "page_count": len(pages),
                "matrix_counts": {
                    state.value: sum(row.status is state for row in findings)
                    for state in (
                        AuditStatus.UPDATED,
                        AuditStatus.NOT_UPDATED,
                        AuditStatus.INVALID_FORMAT,
                    )
                },
            },
        )
        return ProjectAudit(project, findings, owner)

    def _audit_page_regions(
        self, project, page, points, period, audit_id="",
    ):
        try:
            versions = self._page_versions(page, period)
        except Exception as exc:
            diagnostic = f"{type(exc).__name__}|pageId={page.id}"
            findings = []
            for point in points:
                finding = self._invalid_finding(
                    project, point, page, diagnostic,
                )
                findings.append(finding)
                self._log_rule_trace(
                    audit_id, project, point, page, (), (), False,
                    finding, read_error=diagnostic,
                    exception=exc,
                )
            return findings
        current = versions[-1]
        findings = []
        for point in points:
            updated, extractions, comparisons = self._region_history(
                versions, point, period,
            )
            current_region = extractions[-1]
            if not current_region.found:
                finding = AuditFinding(
                    project.project_id, current.title, point.rule_id,
                    AuditStatus.INVALID_FORMAT, "格式有误",
                    page_url=current.url,
                    explanation=f"格式有误：查询不到{point.standard_name}",
                )
            else:
                finding = AuditFinding(
                    project.project_id, current.title, point.rule_id,
                    AuditStatus.UPDATED if updated else AuditStatus.NOT_UPDATED,
                    (
                        "Region updated in audit period."
                        if updated else "Region not updated in audit period."
                    ),
                    page_url=current.url,
                )
            findings.append(finding)
            self._log_rule_trace(
                audit_id, project, point, current, versions, extractions,
                updated, finding, comparisons=comparisons,
            )
        return findings

    def _page_versions(self, page, period):
        current = self.client.get_page(page.id)
        versions = [current]
        if current.updated_at is None:
            raise ValueError("MissingVersionTimestamp")
        if current.updated_at >= period.start:
            for version in range(current.version - 1, 0, -1):
                historical = self.client.get_page_version(page.id, version)
                versions.append(historical)
                if historical.updated_at is None or historical.updated_at < period.start:
                    break
        return list(reversed(versions))

    @staticmethod
    def _region_history(versions, point, period):
        extractions = [
            extract_page_region(page, point) for page in versions
        ]
        comparisons = []
        if len(versions) == 1:
            page = versions[0]
            changed = page.version == 1 and period.contains(page.updated_at)
            return changed, extractions, comparisons
        changed = False
        for older, newer, old_region, new_region in zip(
            versions, versions[1:], extractions, extractions[1:],
        ):
            if not period.contains(newer.updated_at):
                continue
            pair_changed = (
                old_region.found, old_region.content,
            ) != (
                new_region.found, new_region.content,
            )
            changed = changed or pair_changed
            comparisons.append({
                "older_version": older.version,
                "newer_version": newer.version,
                "newer_in_period": True,
                "changed": pair_changed,
            })
        return changed, extractions, comparisons

    @staticmethod
    def _log_rule_trace(
        audit_id, project, point, page, versions, extractions, changed,
        finding, *, comparisons=(), read_error="", exception=None,
    ):
        version_traces = []
        for version, extraction in zip(versions, extractions):
            content = extraction.content
            version_traces.append({
                "version": version.version,
                "updated_at": (
                    version.updated_at.isoformat()
                    if version.updated_at else None
                ),
                "storage_length": len(version.body or ""),
                "view_length": len(version.view_body or ""),
                "source": extraction.source,
                "found": extraction.found,
                "locator_type": extraction.locator_type,
                "element_type": extraction.element_type,
                "matched_locator": extraction.locator,
                "boundary": extraction.boundary,
                "content_length": len(content),
                "content_hash": hashlib.sha256(
                    content.encode("utf-8"),
                ).hexdigest(),
            })
        response = getattr(exception, "response", None)
        smart_log(
            "Confluence audit rule trace (project=%s, rule=%s, status=%s)",
            project.project_id, point.rule_id, finding.status.value,
            domain="confluence", source="project_audit",
            level=(
                "warning"
                if finding.status is AuditStatus.INVALID_FORMAT else "info"
            ),
            extra={
                "audit_id": audit_id,
                "project_id": project.project_id,
                "project_name": project.name,
                "project_home_url": project.home_url,
                "rule_id": point.rule_id,
                "standard_name": point.standard_name,
                "page_kind": point.page_kind,
                "page_id": page.id if page else "",
                "page_title": page.title if page else "",
                "page_url": page.url if page else project.home_url,
                "configured_locators": {
                    "heading_names": list(point.heading_names),
                    "table_fields": list(point.table_fields),
                    "table_region_fields": list(
                        point.table_region_fields,
                    ),
                    "use_page_body": point.use_page_body,
                    "heading_boundary": point.heading_boundary,
                },
                "versions": version_traces,
                "baseline_version": (
                    versions[0].version if versions else None
                ),
                "comparisons": list(comparisons),
                "changed": changed,
                "final_status": finding.status.value,
                "final_reason": finding.explanation or finding.reason,
                "read_error": read_error,
                "exception_type": (
                    type(exception).__name__ if exception else ""
                ),
                "http_status": getattr(response, "status_code", None),
            },
        )

    @staticmethod
    def _invalid_finding(project, point, page, diagnostic):
        if page is None and not diagnostic:
            return AuditFinding(
                project.project_id,
                point.label.split(".")[-1],
                point.rule_id,
                AuditStatus.INVALID_FORMAT,
                "格式有误",
                page_url=project.home_url,
                explanation=f"格式有误：查询不到{point.standard_name}",
            )
        error_type, _, response = diagnostic.partition("|")
        return AuditFinding(
            project.project_id,
            page.title if page else point.label.split(".", 1)[0],
            point.rule_id,
            AuditStatus.INVALID_FORMAT,
            error_type or "InvalidFormat",
            page_url=page.url if page else project.home_url,
            explanation=response or diagnostic,
        )
