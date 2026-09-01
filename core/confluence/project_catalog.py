from __future__ import annotations

from copy import deepcopy
from concurrent.futures import Future, as_completed
from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import parse_qs, urljoin, urlsplit
import re

from .project_discovery import PRODUCT_LINES, ProjectLocation, _commercial_year, discover_project_pages, locate_basic_information
from .html import html_tables, links, text
from .role_parser import extract_project_roles, resolve_role_display_names
from .project_rules import CANONICAL_PROJECT_FIELDS, ROLE_LABELS, normalize_project_field


SCHEMA_VERSION = 2
ROLE_PARSER_VERSION = 2
PRODUCT_SPACE_FACET = "__product_space__"
PROJECT_SPACE_FACET_DEFINITIONS = (
    (PRODUCT_SPACE_FACET, "Product Space"),
    ("page", "Page"),
    ("date of commercial approval", "Date of Commercial approval"),
    ("project id", "Project ID"),
    ("odm", "ODM"),
    ("oem/operator", "OEM/Operator"),
    ("key part number", "Key Part Number"),
    ("project status", "Project Status"),
    ("current stage", "Current Stage"),
    ("major pm", "Major PM"),
    ("project owner", "Project Owner"),
    ("support mode", "Support Mode"),
    ("launch os", "Launch OS"),
    ("date of kick off", "Date of Kick Off"),
    ("planned closure", "planned closure"),
    ("actual closure", "actual closure"),
    ("mp time", "MP Time"),
    ("launch time", "Launch Time"),
    ("next target", "Next Target"),
    ("next target date", "Next Target Date"),
    ("sum", "Sum"),
)
PROJECT_SPACE_FILTER_FIELDS = tuple(key for key, _label in PROJECT_SPACE_FACET_DEFINITIONS)


def refresh_project_catalogs(client, store, product_lines=PRODUCT_LINES, *, now=None, manager=None):
    """Fetch only independent Product Space catalogs and publish them atomically."""
    now = now or datetime.now(timezone.utc)
    previous = store.load() or {"projects": []}
    old_by_id = {row["identity"]: row for row in previous["projects"]}

    def fetch(index_line):
        index, line = index_line
        try:
            source = client.get_page_by_url(line.source_url)
            rows = _catalog_rows(source, line.key)
            return index, line, source, rows, None
        except Exception as exc:
            return index, line, None, [], exc

    fetched = {}

    def build_snapshot(*, phase):
        projects = []
        sources = []
        stage_domains = {}
        discrepancies = set()
        seen = set()
        inaccessible_spaces = set()
        completed_spaces = set()
        for index, line, source, rows, error in sorted(fetched.values()):
            completed_spaces.add(line.key)
            if error:
                if not _is_access_denied(error):
                    raise error
                inaccessible_spaces.add(line.key)
                continue
            evidence = _page_evidence(source, line.key)
            evidence["display_name"] = line.display_name
            sources.append(evidence)
            for source_catalog in rows:
                catalog = deepcopy(source_catalog)
                catalog["catalog_source"] = evidence
                discrepancies.update(catalog.pop("discrepancies", ()))
                seen.add(catalog["identity"])
                stage = catalog.get("fields", {}).get("current stage", "")
                if stage and stage not in stage_domains.setdefault(line.key, []):
                    stage_domains[line.key].append(stage)
                old = old_by_id.get(catalog["identity"])
                if old and old.get("catalog_fingerprint") == catalog["catalog_fingerprint"]:
                    row = deepcopy(old); row.update(catalog); row.update(active=True)
                else:
                    row = {**catalog, "roles": {label: [] for label in ROLE_LABELS},
                           "active": True, "status": "catalog_ready", "error": None,
                           "detail_source": None, "updated_at": now.isoformat()}
                projects.append(row)
        for identity, old in old_by_id.items():
            space_key = old.get("space_key")
            if space_key not in completed_spaces:
                projects.append(deepcopy(old))
            elif identity not in seen and space_key not in inaccessible_spaces:
                row = deepcopy(old); row.update(active=False, status="inactive", updated_at=now.isoformat())
                projects.append(row)
        projects.sort(key=lambda row: (row["project_id"].casefold(), row["identity"].casefold()))
        completed = len(fetched)
        return {"schema_version": SCHEMA_VERSION, "source": "Confluence Product Line Project Spaces",
                "updated_at": now.isoformat(), "sources": sources,
                "complete_spaces": sorted(completed_spaces),
                "field_discrepancies": sorted(discrepancies, key=str.casefold),
                "projects": projects, "stage_domains": stage_domains, "phase": phase,
                "catalog_progress": {"completed": completed,
                                     "pending": len(product_lines) - completed,
                                     "total": len(product_lines)}}

    def submit(item):
        if manager is not None:
            return manager.submit(f"confluence-catalog:{item[1].key}", lambda _token, _progress: fetch(item))
        future = Future()
        try:
            future.set_result(fetch(item))
        except Exception as error:
            future.set_exception(error)
        return future

    futures = [submit(item) for item in enumerate(product_lines, start=1)]
    for future in as_completed(futures):
        result = future.result()
        fetched[result[0]] = result
        snapshot = build_snapshot(
            phase="catalog_ready" if len(fetched) == len(product_lines) else "catalog_loading",
        )
        store.save(snapshot)
    return snapshot


def extract_project_detail(client, original, *, now=None, resolved_names=None):
    """Fetch and map one catalog project into one complete current-state payload."""
    now = now or datetime.now(timezone.utc)
    row = deepcopy(original)
    names = resolved_names if resolved_names is not None else {}
    if row.get("detail_source") and row.get("status") == "current" and _current_role_parser(row):
        resolve_role_display_names(client, row.get("roles", {}), names)
        return row
    project = ProjectLocation(
        status_page_id=row.get("page_id", ""), project_id=row["project_id"],
        name=" ".join(filter(None, (row["name"], row.get("page_id", "")))),
        status_url=row["page_url"], home_url=row["page_url"],
        space_key=row["space_key"], page_identity=row["project_id"],
    )
    discovered = discover_project_pages(
        client, project,
        return_errors=True, return_context=True,
        resolved_entry_page_id=row.get("entry_page_id", "") if not row.get("page_id") else "",
        resolved_root_page_id=row.get("root_page_id", "") if not row.get("page_id") else "",
    )
    metadata, error, context = locate_basic_information(client, project, discovered=discovered)
    if metadata is None:
        raise LookupError(error)
    detail = client.get_page(metadata.id)
    pages, _errors, _context = discovered
    pages["basic"] = detail
    roles = extract_project_roles(detail.body or detail.view_body)
    resolve_role_display_names(client, roles, names)
    row.update(entry_page_id=context["entry_page_id"], root_page_id=context["root_page_id"],
               detail_path=context.get("page_paths", {}).get("basic", []), roles=roles,
               status="current", error=None,
               evidence=[{"source": kind, **_page_evidence(page, row["space_key"])}
                         for kind, page in pages.items()],
               detail_source=_detail_evidence(detail, row["space_key"]), updated_at=now.isoformat())
    return row


def query_project_facts(snapshot, *, filters=None, search="", include_inactive=False):
    filters = {
        _normalize(key): tuple(dict.fromkeys(
            _normalize(item) for item in (value if isinstance(value, (list, tuple, set)) else (value,))
            if _normalize(item)
        ))
        for key, value in (filters or {}).items()
    }
    filters = {key: values for key, values in filters.items() if values}
    needle = _normalize(search)
    candidates = [row for row in (snapshot or {}).get("projects", []) if include_inactive or row.get("active", True)]
    rows = []
    for row in candidates:
        fields = dict(row.get("fields", {}))
        if not _matches_filters(row, fields, filters):
            continue
        people = " ".join(
            f"{person.get('name', '')} {person.get('identity', '')}"
            for role in row.get("roles", {}).values() for person in role
        )
        haystack = " ".join((row.get("project_id", ""), row.get("name", ""), row.get("space_key", ""), people, *fields.values()))
        if needle and needle not in _normalize(haystack):
            continue
        visible = deepcopy(row)
        visible["fields"] = fields
        visible["responsibility_unavailable"] = not any(
            visible.get("roles", {}).get(role) for role in ROLE_LABELS
        )
        rows.append(visible)
    facet_keys = sorted({key for row in rows for key in row.get("fields", {})})
    facets = {key: sorted({row["fields"][key] for row in rows if row.get("fields", {}).get(key)}, key=str.casefold)
              for key in facet_keys}
    for key in PROJECT_SPACE_FILTER_FIELDS:
        facets.setdefault(key, [])
    facets["date of commercial approval"] = sorted({
        year for row in rows
        if (year := _commercial_year(row.get("fields", {}).get("date of commercial approval", "")))
    })
    selected_spaces = filters.get(PRODUCT_SPACE_FACET, ())
    stage_domains = dict((snapshot or {}).get("stage_domains", {}))
    if not stage_domains:
        for row in candidates:
            stage = row.get("fields", {}).get("current stage", "")
            if stage and stage not in stage_domains.setdefault(row.get("space_key", ""), []):
                stage_domains[row.get("space_key", "")].append(stage)
    domain_spaces = selected_spaces or tuple(stage_domains)
    facets["current stage"] = sorted({
        stage for space in domain_spaces
        for stage in stage_domains.get(space.upper(), ())
        if stage
    }, key=str.casefold)
    labels = {line.key: line.display_name for line in PRODUCT_LINES}
    labels.update({source.get("space_key"): source.get("display_name")
                   for source in (snapshot or {}).get("sources", [])
                   if source.get("space_key") and source.get("display_name")})
    facets[PRODUCT_SPACE_FACET] = [
        {"value": value, "label": labels.get(value) or value}
        for value in sorted({row.get("space_key", "") for row in rows if row.get("space_key")}, key=str.casefold)
    ]
    hierarchy = _owner_hierarchy(rows)
    return {"projects": rows, "facets": facets, "ownerHierarchy": hierarchy}


def _matches_filters(row, fields, filters):
    for key, values in filters.items():
        if key == PRODUCT_SPACE_FACET:
            actual = _normalize(row.get("space_key", ""))
        elif key == "date of commercial approval":
            year = _commercial_year(fields.get(key, ""))
            actual = str(year or "")
        else:
            actual = _normalize(fields.get(key, ""))
        if actual not in values:
            return False
    return True


def _owner_hierarchy(projects):
    hierarchy = []
    for role in ROLE_LABELS:
        people = {}
        for project in projects:
            for person in project.get("roles", {}).get(role, ()):
                identity = str(person.get("identity") or "").strip()
                name = str(person.get("name") or "").strip()
                key = identity or name.casefold()
                if not key:
                    continue
                owner = people.setdefault(key, {"name": name, "identity": identity, "projects": []})
                if all(row.get("identity") != project.get("identity") for row in owner["projects"]):
                    owner["projects"].append(deepcopy(project))
        hierarchy.append({
            "role": role,
            "people": sorted(people.values(), key=lambda row: (row["name"].casefold(), row["identity"].casefold())),
        })
    return hierarchy


def _catalog_rows(source, space_key):
    merged = {}
    found_catalog = False
    for table in html_tables(source.view_body or source.body):
        header_index = next((index for index, cells in enumerate(table)
                             if {"page", "project id"} <= {_header(cell) for cell in cells}), None)
        if header_index is None:
            continue
        found_catalog = True
        raw_headers = [text(cell).strip() for cell in table[header_index]]
        normalized_headers = [_header(cell) for cell in table[header_index]]
        for cells in table[header_index + 1:]:
            if not any(text(cell).strip() for cell in cells):
                continue
            if len(cells) < len(raw_headers):
                raise RuntimeError("remote_unavailable")
            values = dict(zip(normalized_headers, cells))
            page_links = links(values.get("page", ""))
            project_id = text(values.get("project id", "")).strip()
            if not page_links or not project_id:
                raise RuntimeError("remote_unavailable")
            href, label = page_links[0]
            identity = f"{space_key}:{project_id}"
            row = merged.setdefault(identity, {
                "raw_fields": {}, "raw_field_html": {}, "fields": {}, "raw_headers": [],
            })
            for raw_header, normalized, cell in zip(raw_headers, normalized_headers, cells):
                value = text(cell).strip()
                row["raw_headers"].append(raw_header)
                if value and raw_header not in row["raw_fields"]:
                    row["raw_fields"][raw_header] = value
                    row["raw_field_html"][raw_header] = cell
                if value and normalized not in row["fields"]:
                    row["fields"][normalized] = value
            page_url = urljoin(source.url, href)
            row.update(identity=identity, project_id=project_id, name=label or project_id,
                       space_key=space_key, page_url=page_url,
                       page_id=(parse_qs(urlsplit(page_url).query).get("pageId") or [""])[0])
    if not found_catalog:
        raise RuntimeError("remote_unavailable")
    result = []
    for row in merged.values():
        row["raw_headers"] = list(dict.fromkeys(row["raw_headers"]))
        row["discrepancies"] = [header for header in row["raw_headers"] if normalize_project_field(header) not in CANONICAL_PROJECT_FIELDS]
        row["field_discrepancies"] = list(row["discrepancies"])
        row["catalog_fingerprint"] = hashlib.sha256(json.dumps(
            {"identity": row["identity"], "raw_fields": row["raw_fields"]},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        result.append(row)
    return result


def _is_access_denied(exc):
    return getattr(getattr(exc, "response", None), "status_code", None) == 403


def _page_evidence(page, space_key):
    return {"space_key": space_key, "page_id": str(page.id), "title": page.title, "url": page.url,
            "version": int(page.version or 0),
            "updated_at": page.updated_at.isoformat() if page.updated_at else None}


def _detail_evidence(page, space_key):
    evidence = _page_evidence(page, space_key)
    evidence["role_parser_version"] = ROLE_PARSER_VERSION
    return evidence


def _current_role_parser(project):
    return project.get("detail_source", {}).get("role_parser_version") == ROLE_PARSER_VERSION


def _header(value):
    return normalize_project_field(text(value))


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()
