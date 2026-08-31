from dataclasses import replace
from collections import Counter
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlsplit
import re
from core.logging import smart_log
from .html import html_tables, links, text
from .models import ConfluenceProject, ProductLine, ProjectCandidate, ProjectCollectionFilter
from .project_collection import filter_projects
from .rules import BASIC_INFORMATION_RULE

PAGE_ALIASES = (
    (BASIC_INFORMATION_RULE.output_key, re.compile(
        re.escape(BASIC_INFORMATION_RULE.source_field).replace("\\ ", r"\s*") + r"\s*$", re.I,
    )),
    ("status", re.compile(r"(?:project\s*)?status\s*report\s*$", re.I)),
    ("test_information", re.compile(r"test\s*information\s*$", re.I)),
    ("test_plan", re.compile(r"test\s*plan\s*$", re.I)),
    ("environment", re.compile(r"test\s*environment(?:\s*setup\s*(?:and|&)\s*precautions)?\s*$", re.I)),
    ("experience", re.compile(r"(?:summary\s*of\s*)?experience\s*(?:and|&)\s*typical\s*cases\s*$", re.I)),
    ("report_store", re.compile(r"test\s*report\s*store\s*$", re.I)),
)

class ProjectCollectionDiscoveryError(RuntimeError):
    pass

def canonical_page_kind(title: str) -> str | None:
    return _page_kind_and_prefix(title)[0]


def _page_kind_and_prefix(title):
    clean = re.sub(r"^[\d\s.★*#_-]+", "", str(title or "").strip())
    clean = re.sub(r"\s+", " ", clean)
    for kind, pattern in PAGE_ALIASES:
        if pattern.fullmatch(clean):
            return kind, ""
        separated = re.fullmatch(r"(.*\S)\s*[-–—:]\s*(.+)", clean)
        if separated and pattern.fullmatch(separated.group(2)):
            return kind, separated.group(1).strip()
    return None, ""

PRODUCT_LINES = (
    ProductLine(
        "DOPL", "https://confluence.amlogic.com/display/DOPL/Project+Space",
        "China Operator Business",
    ),
    ProductLine(
        "SDPL", "https://confluence.amlogic.com/display/SDPL/Project+Space",
        "Smart Device Business",
    ),
    ProductLine(
        "TV", "https://confluence.amlogic.com/display/TV/Project+Space",
        "TV Business",
    ),
    ProductLine(
        "OOPL", "https://confluence.amlogic.com/display/OOPL/Project+Space",
        "Global Operator & STB Business",
    ),
)
UNIFIED_SOURCE = "Confluence Product Line Project Spaces"


def discover_project_collection(client, criteria: ProjectCollectionFilter, progress=lambda *_: None):
    projects = []
    selected_keys = set(criteria.product_line_keys)
    product_lines = tuple(
        line for line in PRODUCT_LINES
        if line.key in selected_keys
    )
    progress(0, len(product_lines))
    for index, line in enumerate(product_lines, 1):
        space_key, source_url = line.key, line.source_url
        fetch_error = ""
        fetch_exception = None
        source_diagnostic = {}
        try:
            source = client.get_page_by_url(source_url)
            rows, table_count, row_errors, source_diagnostic = _summary_projects(
                source, space_key, diagnostic=True,
            )
        except Exception as exc:
            rows, table_count, row_errors = [], 0, 0
            fetch_error = type(exc).__name__
            fetch_exception = exc
        projects.extend(rows)
        filter_diagnostic = _line_filter_diagnostic(rows, criteria)
        smart_log(
            "Confluence product line projects filtered",
            domain="confluence", source="project_collection",
            level="warning" if fetch_error or row_errors else "info",
            extra={
                "space_key": space_key,
                "table_count": table_count,
                "row_count": len(rows),
                "error_count": row_errors,
                "fetch_error_type": fetch_error,
                **source_diagnostic, **filter_diagnostic,
            },
        )
        if fetch_error:
            raise ProjectCollectionDiscoveryError(
                f"{space_key} Project Space is unreadable: {fetch_error}"
            ) from fetch_exception
        if table_count == 0:
            raise ProjectCollectionDiscoveryError(
                f"{space_key} Project Space has no readable project table with "
                "Page and Project ID columns"
            )
        progress(index, len(product_lines))
    criteria = replace(
        criteria, source_url=UNIFIED_SOURCE, current_stages=(),
    )
    collection = filter_projects(projects, criteria)
    return replace(
        collection,
        visible_years=tuple(sorted({
            project.year for project in projects if project.year > 0
        })),
        discovery_errors={},
        product_lines=PRODUCT_LINES,
    )


_SUMMARY_FIELDS = {
    "page", "date of commercial approval", "support mode", "project status",
    "project id", "current stage",
}


def _line_filter_diagnostic(projects, criteria):
    years = set(criteria.years)
    support_modes = {_normalize(value) for value in criteria.support_modes}
    project_statuses = {_normalize(value) for value in criteria.project_statuses}
    missing = Counter()
    mismatches = Counter()
    matched = 0
    for project in projects:
        excluded = False
        for active, field, value, normalized_values in (
            (years, "year", project.year, years),
            (support_modes, "support_mode", project.support_mode, support_modes),
            (project_statuses, "project_status", project.project_status, project_statuses),
        ):
            if not active:
                continue
            if value in {None, "", 0}:
                missing[field] += 1
                excluded = True
            elif (_normalize(value) if field != "year" else value) not in normalized_values:
                mismatches[field] += 1
                excluded = True
        if not excluded:
            matched += 1
    return {
        "missing_field_exclusions": dict(sorted(missing.items())),
        "criterion_mismatch_counts": dict(sorted(mismatches.items())),
        "matched_count": matched,
        "emitted_frontend_count": matched,
    }


def _summary_projects(source, space_key, *, diagnostic=False):
    merged_rows = {}
    table_count = 0
    errors = 0
    rejection_counts = Counter()
    parsed_tables = html_tables(source.view_body or source.body)
    identity_headers = {"page", "project id"}
    for table in parsed_tables:
        header_index = None
        for index, row in enumerate(table):
            row_headers = {_summary_header(cell) for cell in row}
            if identity_headers <= row_headers:
                header_index = index
                break
        if header_index is None:
            rejection_counts["table_header_mismatch"] += 1
            continue
        table_count += 1
        headers = [_summary_header(cell) for cell in table[header_index]]
        for cells in table[header_index + 1:]:
            if len(cells) < len(headers):
                errors += 1
                rejection_counts["short_row"] += 1
                continue
            values = dict(zip(headers, cells))
            if identity_headers <= {_summary_header(cell) for cell in cells}:
                continue
            page_links = links(values["page"])
            project_id = text(values["project id"]).strip()
            if not page_links or not project_id:
                errors += 1
                if not page_links:
                    rejection_counts["missing_page_link"] += 1
                if not project_id:
                    rejection_counts["missing_project_id"] += 1
                continue
            href, label = page_links[0]
            page_url = urljoin(source.url, href)
            page_id = (parse_qs(urlsplit(page_url).query).get("pageId") or [""])[0]
            project_id_key = _normalize(project_id)
            merged = merged_rows.setdefault(project_id_key, {
                "page": values["page"], "project id": values["project id"],
                "page_url": page_url, "page_id": page_id,
                "label": label,
            })
            for field in _SUMMARY_FIELDS - identity_headers:
                if field not in values or not text(values[field]).strip():
                    continue
                merged.setdefault(field, values[field])

    projects = {}
    for merged in merged_rows.values():
        commercial_date = text(merged.get("date of commercial approval", ""))
        year = _commercial_year(commercial_date) or 0
        project_id = text(merged["project id"]).strip()
        project_status = text(merged.get("project status", "")).strip()
        current_stage = text(merged.get("current stage", "")).strip()
        support_mode = text(merged.get("support mode", "")).strip()
        label = merged["label"]
        page_url = merged["page_url"]
        page_id = merged["page_id"]
        projects.setdefault(_normalize(project_id), ConfluenceProject(
                year=year,
                project_id=project_id,
                name=label or text(merged["page"]).strip(),
                status_page_id=page_id,
                status_url=page_url,
                home_url=page_url,
                project_status=project_status,
                current_stage=current_stage,
                support_mode=support_mode,
                attributes={
                    "year_source": "date of commercial approval",
                    "support_mode_source": "support mode",
                    "project_status_source": "project status",
                },
                display_name=label or text(merged["page"]).strip(),
                space_key=space_key,
                page_identity=project_id,
            ))
    if table_count == 0:
        errors += 1
    result = (list(projects.values()), table_count, errors)
    if not diagnostic:
        return result
    return (*result, {
        "page_id": str(source.id or ""),
        "page_title": _safe_title(source.title),
        "body_length": len(source.body or ""),
        "view_body_length": len(source.view_body or ""),
        "parsed_table_count": len(parsed_tables),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "merged_project_count": len(merged_rows),
        "project_identity_sample": sorted(
            project.project_identity for project in projects.values()
        )[:10],
    })


def _summary_header(value):
    normalized = _normalize(text(value))
    return "page" if normalized in {"页面", "page"} else normalized


def _commercial_year(value):
    clean = re.sub(r"\s+", " ", str(value or "")).strip()
    day_first = re.fullmatch(
        r"(?P<day>\d{1,2}) (?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
        r"(?P<year>\d{4})",
        clean,
        re.IGNORECASE,
    )
    if day_first:
        month = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }[day_first.group("month").casefold()]
        try:
            return datetime(
                int(day_first.group("year")), month, int(day_first.group("day")),
            ).year
        except ValueError:
            return None
    for pattern in (
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%b %d, %Y", "%B %d, %Y",
    ):
        try:
            return datetime.strptime(clean, pattern).year
        except ValueError:
            pass
    return None


_LEADING_PAGE_ORDINAL = re.compile(
    r"^\s*\d+\.\s*(?:[★☆*]\s*)?(?=[^\W\d_])",
)
_PAGE_TYPE_SUFFIX = re.compile(
    r"\s*[-–—]\s*\**\s*"
    r"(?:Basic\s+Information|Project\s+Status\s+Report)\s*\**\s*$",
    re.IGNORECASE,
)


def _project_display_name(title, project_id):
    """Derive a UI name without changing the Confluence audit target title."""
    value = str(title or "").strip()
    value = _LEADING_PAGE_ORDINAL.sub("", value)
    value = _PAGE_TYPE_SUFFIX.sub("", value).strip()
    return value or str(project_id)


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


_PROJECT_GRAPH_MAX_DEPTH = 4
_PROJECT_GRAPH_MAX_NODES = 100


def discover_project_pages(client, project: ProjectCandidate, *, return_errors=False, return_context=False,
                           resolved_entry_page_id="", resolved_root_page_id=""):
    """Discover audited pages within the owning project's child-page graph."""
    home = (client.get_page(resolved_root_page_id) if resolved_root_page_id
            else client.get_page_by_url(project.home_url))
    candidates = {}
    errors = {}
    error_types = Counter()
    graph_root = home
    if not resolved_root_page_id and canonical_page_kind(home.title) == "status":
        try:
            graph_root = client.get_parent_page(home.id) or home
        except Exception as exc:
            errors["branch:project_root"] = _issue(
                type(exc).__name__,
                f"pageId={home.id}; title={_safe_title(home.title)}",
            )
            error_types[type(exc).__name__] += 1

    queue = [(graph_root, 0, [str(graph_root.id)])]
    visited = set()
    candidate_paths = {}
    while queue and len(visited) < _PROJECT_GRAPH_MAX_NODES:
        page, depth, path = queue.pop(0)
        page_id = str(page.id)
        if not page_id or page_id in visited:
            continue
        visited.add(page_id)
        kind, prefix = _page_kind_and_prefix(page.title)
        if kind:
            kind_candidates = candidates.setdefault(kind, [])
            if all(existing.id != page.id for existing, _ in kind_candidates):
                kind_candidates.append((page, prefix))
                candidate_paths[str(page.id)] = path

        if depth >= _PROJECT_GRAPH_MAX_DEPTH:
            continue
        try:
            children = client.get_page_children(page.id)
        except Exception as exc:
            error_kind = kind or f"branch:{page_id}"
            errors[error_kind] = _issue(
                type(exc).__name__,
                f"pageId={page_id}; title={_safe_title(page.title)}",
            )
            error_types[type(exc).__name__] += 1
        else:
            queue.extend((child, depth + 1, [*path, str(child.id)]) for child in children)

    pages = {}
    conflicts = {}
    identity_tokens = _project_identity_tokens(project)
    for kind, kind_candidates in candidates.items():
        ranked = [
            (page, _project_identity_match_level(prefix, identity_tokens))
            for page, prefix in kind_candidates
        ]
        best_level = max(level for _, level in ranked)
        matching = [page for page, level in ranked if level == best_level]
        if best_level and len(matching) == 1:
            pages[kind] = matching[0]
            continue
        error_type = "AmbiguousPage" if best_level else "ForeignProjectPage"
        candidate_ids = sorted(page.id for page, _ in kind_candidates)
        errors[kind] = _issue(
            error_type, f"candidate pageIds={','.join(candidate_ids)}",
        )
        error_types[error_type] += 1
        conflicts[kind] = candidate_ids

    smart_log(
        "Confluence project page graph discovered",
        domain="confluence", source="project_page_discovery",
        level="warning" if errors else "info",
        extra={
            "project_id": project.project_id,
            "entry_page_id": resolved_entry_page_id or home.id,
            "root_page_id": graph_root.id,
            "visited_count": len(visited),
            "matched_kinds": sorted(pages),
            "error_kinds": sorted(errors),
            "error_types": dict(sorted(error_types.items())),
            "conflicts": dict(sorted(conflicts.items())),
        },
    )
    if return_context:
        return pages, errors, {
            "entry_page_id": str(resolved_entry_page_id or home.id), "root_page_id": str(graph_root.id),
            "page_paths": {kind: candidate_paths[str(page.id)] for kind, page in pages.items()},
        }
    return (pages, errors) if return_errors else pages


def locate_basic_information(client, project: ProjectCandidate, *, resolved_entry_page_id="",
                             resolved_root_page_id="", discovered=None):
    """Single owner for Basic Information location and its discovery metadata."""
    if discovered is None:
        pages, errors, context = discover_project_pages(
            client, project, return_errors=True, return_context=True,
            resolved_entry_page_id=resolved_entry_page_id,
            resolved_root_page_id=resolved_root_page_id,
        )
    else:
        pages, errors, context = discovered
    page = pages.get("basic")
    error = errors.get("basic", BASIC_INFORMATION_RULE.failure_semantic) if page is None else ""
    return page, error, context


def _page_identity(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _issue(error_type, response_summary):
    return f"{error_type}|{response_summary}"


def _safe_title(value):
    return re.sub(r"[\x00-\x1f<>]", " ", str(value or "")).strip()[:160]


def _project_identity_tokens(project):
    values = (
        project.status_page_id,
        project.project_id,
        project.name,
        _project_display_name(project.name, project.project_id),
    )
    return {
        token
        for value in values
        for token in (
            _page_identity(value),
            *(
                _page_identity(match)
                for match in re.findall(
                    r"[A-Za-z][A-Za-z0-9-]*\d[A-Za-z0-9-]*",
                    str(value or ""),
                )
            ),
        )
        if token
    }


def _project_identity_match_level(prefix, identity_tokens):
    if not prefix:
        return 1
    prefix_token = _page_identity(prefix)
    if not prefix_token:
        return 0
    if any(prefix_token == token or prefix_token in token for token in identity_tokens):
        return 2
    if any(
        prefix_token.endswith(token) and len(prefix_token) == len(token) + 1
        for token in identity_tokens
    ):
        return 1
    return 0
