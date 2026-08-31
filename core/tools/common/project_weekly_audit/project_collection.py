from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from collections.abc import Iterable
import json
import re

from core.logging import smart_log
from .models import ConfluenceProject, ProjectCollection, ProjectCollectionFilter


LOGGABLE_FILTER_VALUES = frozenset({
    "__PRODUCT_SPACE__", "DATE OF COMMERCIAL APPROVAL", "PROJECT STATUS",
    "CURRENT STAGE", "SUPPORT MODE",
})


def summarize_project_fact_filters(filters):
    """Return bounded filter diagnostics without project/person identifiers."""
    summary = {}
    for key, raw_values in list((filters or {}).items())[:20]:
        values = raw_values if isinstance(raw_values, (list, tuple, set)) else (raw_values,)
        values = [str(value) for value in values if str(value).strip()][:20]
        item = {"selected_count": len(values)}
        if _normalize(key) in LOGGABLE_FILTER_VALUES:
            item["values"] = values
        summary[str(key)] = item
    return summary


def default_project_filter(now: datetime, source_url: str) -> ProjectCollectionFilter:
    return ProjectCollectionFilter(
        source_url=str(source_url).strip(),
        years=(now.year - 1, now.year),
        support_modes=("A",),
        project_statuses=("NORMAL",),
    )


def filter_projects(
    projects: Iterable[ConfluenceProject],
    criteria: ProjectCollectionFilter,
) -> ProjectCollection:
    years = set(criteria.years)
    support_modes = _values(criteria.support_modes)
    project_statuses = _values(criteria.project_statuses)
    current_stages = _values(criteria.current_stages)
    included_ids = _values(criteria.included_project_ids)
    product_line_keys = _values(criteria.product_line_keys)
    project_space_fields = {
        _normalize(key): _values(values if isinstance(values, (tuple, list, set)) else (values,))
        for key, values in criteria.project_space_fields
        if _values(values if isinstance(values, (tuple, list, set)) else (values,))
    }
    included = []
    excluded = Counter()
    independent_excluded = Counter()
    independent_excluded["current_stage"] = 0
    for active, key in (
        (years, "year"),
        (support_modes, "support_mode"),
        (project_statuses, "project_status"),
        (current_stages, "current_stage_filter"),
        (included_ids, "project_selection"),
        (product_line_keys, "product_line"),
    ):
        if active:
            independent_excluded[key] = 0
    input_count = 0

    for project in projects:
        input_count += 1
        reason = None
        stage_match = re.match(r"^\s*(\d+)", str(project.current_stage or ""))
        stage_excluded = bool(
            criteria.exclude_late_stages and stage_match and int(stage_match.group(1)) >= 4
        )
        project_years = set(project.matching_years or (project.year,))
        matching_years = tuple(sorted(project_years & years if years else project_years))
        if stage_excluded:
            independent_excluded["current_stage"] += 1
        if years and not matching_years:
            independent_excluded["year"] += 1
        if support_modes and _normalize(project.support_mode) not in support_modes:
            independent_excluded["support_mode"] += 1
        if project_statuses and _normalize(project.project_status) not in project_statuses:
            independent_excluded["project_status"] += 1
        if current_stages and _normalize(project.current_stage) not in current_stages:
            independent_excluded["current_stage_filter"] += 1
        if included_ids and _normalize(project.project_identity) not in included_ids:
            independent_excluded["project_selection"] += 1
        if product_line_keys and _normalize(project.space_key) not in product_line_keys:
            independent_excluded["product_line"] += 1
        field_mismatch = any(
            _normalize(project.attributes.get(key.casefold(), "")) not in values
            for key, values in project_space_fields.items()
        )
        if field_mismatch:
            independent_excluded["project_space_field"] += 1
        if stage_excluded:
            reason = "current_stage"
        elif years and not matching_years:
            reason = "year"
        elif support_modes and _normalize(project.support_mode) not in support_modes:
            reason = "support_mode"
        elif project_statuses and _normalize(project.project_status) not in project_statuses:
            reason = "project_status"
        elif current_stages and _normalize(project.current_stage) not in current_stages:
            reason = "current_stage_filter"
        elif included_ids and _normalize(project.project_identity) not in included_ids:
            reason = "project_selection"
        elif product_line_keys and _normalize(project.space_key) not in product_line_keys:
            reason = "product_line"
        elif field_mismatch:
            reason = "project_space_field"

        if reason:
            excluded[reason] += 1
        else:
            included.append(replace(project, matching_years=matching_years))

    included = _consolidate_project_identities(included)
    included.sort(key=lambda row: (
        row.name.casefold(), row.project_id.casefold(), row.project_identity.casefold(),
    ))
    smart_log(
        "Confluence project collection filtered: input=%s matched=%s excluded=%s",
        input_count, len(included), input_count - len(included),
        domain="confluence", source="project_collection",
        extra={
            "source_url": criteria.source_url,
            "input_count": input_count,
            "active_filters": {
                "years": sorted(years),
                "support_modes": sorted(support_modes),
                "project_statuses": sorted(project_statuses),
                "current_stages": sorted(current_stages),
                "project_selection_count": len(included_ids),
                "product_line_keys": sorted(product_line_keys),
                **(
                    {"project_space_fields": summarize_project_fact_filters(project_space_fields)}
                    if project_space_fields else {}
                ),
            },
            "independent_excluded_counts": dict(independent_excluded),
            "pipeline_excluded_counts": dict(excluded),
            "final_candidate_count": len(included),
        },
    )
    return ProjectCollection(
        collection_id=_collection_id(criteria),
        name="Confluence Project Collection",
        filter=criteria,
        discovered_at=datetime.now(timezone.utc),
        projects=tuple(included),
        excluded_counts=dict(excluded),
        visible_years=criteria.years,
    )


def _consolidate_project_identities(projects):
    grouped = {}
    for project in projects:
        key = _normalize(project.project_identity)
        grouped.setdefault(key, []).append(project)
    result = []
    for rows in grouped.values():
        canonical = max(rows, key=lambda row: (
            row.year,
            row.project_id.casefold(),
            row.name.casefold(),
            row.status_page_id,
            row.status_url,
            row.home_url,
        ))
        matching_years = sorted({
            year
            for row in rows
            for year in (row.matching_years or (row.year,))
        })
        result.append(replace(canonical, matching_years=tuple(matching_years)))
    return result


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def _values(values) -> set[str]:
    return {_normalize(value) for value in values if _normalize(value)}


def _collection_id(criteria: ProjectCollectionFilter) -> str:
    payload = {
        "years": sorted(set(criteria.years)),
        "support_modes": sorted(_values(criteria.support_modes)),
        "project_statuses": sorted(_values(criteria.project_statuses)),
        "current_stages": sorted(_values(criteria.current_stages)),
        "included_project_ids": sorted(_values(criteria.included_project_ids)),
        "product_line_keys": sorted(_values(criteria.product_line_keys)),
        "project_space_fields": sorted(
            (_normalize(key), sorted(_values(values if isinstance(values, (tuple, list, set)) else (values,))))
            for key, values in criteria.project_space_fields
        ),
        "exclude_late_stages": criteria.exclude_late_stages,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
