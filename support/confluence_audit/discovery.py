from dataclasses import replace
from collections import Counter
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlsplit
import re
from support.logging import smart_log
from .html import html_tables, links, text
from .models import ConfluenceProject, ProjectCandidate, ProjectCollectionFilter
from .project_collection import filter_projects

PAGE_ALIASES = (
    ("status", re.compile(r"project\s*status\s*report\s*$", re.I)),
    ("test_information", re.compile(r"test\s*information\s*$", re.I)),
    ("test_plan", re.compile(r"test\s*plan\s*$", re.I)),
    ("environment", re.compile(r"test\s*environment\s*setup\s*(?:and|&)\s*precautions\s*$", re.I)),
    ("experience", re.compile(r"summary\s*of\s*experience\s*(?:and|&)\s*typical\s*cases\s*$", re.I)),
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

PROJECT_SPACES = (
    ("DOPL", "https://confluence.amlogic.com/display/DOPL/Project+Space"),
    ("SDPL", "https://confluence.amlogic.com/display/SDPL/Project+Space"),
)
UNIFIED_SOURCE = "DOPL + SDPL Project Spaces"


def discover_project_collection(client, criteria: ProjectCollectionFilter, progress=lambda *_: None):
    projects = []
    errors = Counter()
    progress(0, len(PROJECT_SPACES))
    for index, (space_key, source_url) in enumerate(PROJECT_SPACES, 1):
        try:
            source = client.get_page_by_url(source_url, prefer_export=True)
            rows, table_count, row_errors = _summary_projects(source, space_key)
        except Exception:
            errors[f"space:{space_key}"] += 1
            rows, table_count, row_errors = [], 0, 0
        projects.extend(rows)
        if row_errors:
            errors[f"row:{space_key}"] += row_errors
        smart_log(
            "Confluence project summary catalog read",
            domain="confluence", source="project_collection",
            level="warning" if row_errors else "info",
            extra={
                "space_key": space_key,
                "table_count": table_count,
                "row_count": len(rows),
                "error_count": row_errors,
            },
        )
        progress(index, len(PROJECT_SPACES))
    criteria = replace(
        criteria, source_url=UNIFIED_SOURCE, current_stages=(),
    )
    collection = filter_projects(projects, criteria)
    return replace(
        collection,
        visible_years=tuple(sorted({project.year for project in projects})),
        discovery_errors=dict(sorted(errors.items())),
    )


_SUMMARY_REQUIRED = {
    "page", "date of commercial approval", "support mode", "project status",
}


def _summary_projects(source, space_key):
    projects = {}
    table_count = 0
    errors = 0
    for table in html_tables(source.view_body or source.body):
        header_index = next((
            index for index, row in enumerate(table)
            if _SUMMARY_REQUIRED <= {_summary_header(cell) for cell in row}
        ), None)
        if header_index is None:
            continue
        table_count += 1
        headers = [_summary_header(cell) for cell in table[header_index]]
        for cells in table[header_index + 1:]:
            if len(cells) < len(headers):
                errors += 1
                continue
            values = dict(zip(headers, cells))
            if _SUMMARY_REQUIRED <= {_summary_header(cell) for cell in cells}:
                continue
            page_links = links(values["page"])
            year = _commercial_year(text(values["date of commercial approval"]))
            support_mode = text(values["support mode"]).strip()
            project_status = text(values["project status"]).strip()
            if not page_links or year is None or not support_mode or not project_status:
                errors += 1
                continue
            href, label = page_links[0]
            page_url = urljoin(source.url, href)
            page_id = (parse_qs(urlsplit(page_url).query).get("pageId") or [""])[0]
            root_identity = page_id or page_url
            project_id = text(values.get("project id", "")).strip() or root_identity
            projects.setdefault(root_identity, ConfluenceProject(
                year=year,
                project_id=project_id,
                name=label or text(values["page"]).strip(),
                status_page_id=page_id,
                status_url=page_url,
                home_url=page_url,
                project_status=project_status,
                support_mode=support_mode,
                display_name=label or text(values["page"]).strip(),
                space_key=space_key,
                page_identity=root_identity,
            ))
    if table_count == 0:
        errors += 1
    return list(projects.values()), table_count, errors


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


def discover_project_pages(client, project: ProjectCandidate, *, return_errors=False):
    """Discover audited pages within the owning project's child-page graph."""
    home = client.get_page_by_url(project.home_url)
    candidates = {}
    errors = {}
    error_types = Counter()
    graph_root = home
    if canonical_page_kind(home.title) == "status":
        try:
            graph_root = client.get_parent_page(home.id) or home
        except Exception as exc:
            errors["branch:project_root"] = _issue(
                type(exc).__name__,
                f"pageId={home.id}; title={_safe_title(home.title)}",
            )
            error_types[type(exc).__name__] += 1

    queue = [(graph_root, 0)]
    visited = set()
    while queue and len(visited) < _PROJECT_GRAPH_MAX_NODES:
        page, depth = queue.pop(0)
        page_id = str(page.id)
        if not page_id or page_id in visited:
            continue
        visited.add(page_id)
        kind, prefix = _page_kind_and_prefix(page.title)
        if kind:
            kind_candidates = candidates.setdefault(kind, [])
            if all(existing.id != page.id for existing, _ in kind_candidates):
                kind_candidates.append((page, prefix))

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
            queue.extend((child, depth + 1) for child in children)

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
            "entry_page_id": home.id,
            "root_page_id": graph_root.id,
            "visited_count": len(visited),
            "matched_kinds": sorted(pages),
            "error_kinds": sorted(errors),
            "error_types": dict(sorted(error_types.items())),
            "conflicts": dict(sorted(conflicts.items())),
        },
    )
    return (pages, errors) if return_errors else pages


def _page_identity(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _issue(error_type, response_summary):
    return f"{error_type}|{response_summary}"


def _safe_title(value):
    return re.sub(r"[\x00-\x1f<>]", " ", str(value or "")).strip()[:160]


def _project_identity_tokens(project):
    values = (
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
