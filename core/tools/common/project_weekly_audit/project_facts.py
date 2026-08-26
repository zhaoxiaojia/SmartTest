from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
import re

from core.config.jsonTool import read_json, resolve_json_path, write_json
from core.logging import smart_log
from .discovery import PRODUCT_LINES, _commercial_year
from .html import html_tables, links, text
from .models import ConfluenceProject, ProjectCollectionFilter
from .project_collection import filter_projects, summarize_project_fact_filters


SCHEMA_VERSION = 1
DEFAULT_STORE_PATH = Path("confluence_audit") / "project_responsibility_facts.json"
ROLE_LABELS = ("Major FAE QA", "FAE QA", "QA Reviewer")
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
CANONICAL_HEADERS = {
    "page", "project id", "date of commercial approval", "support mode",
    "project status", "current stage",
}


class ProjectFactsSchemaError(ValueError):
    pass


class ProjectFactStore:
    def __init__(self, path: str | Path = DEFAULT_STORE_PATH):
        self.path = Path(path)
        self.resolved_path = resolve_json_path(self.path)

    def load(self):
        try:
            payload = read_json(self.resolved_path, None)
        except (ValueError, OSError) as exc:
            raise ProjectFactsSchemaError(f"Project facts are unreadable: {type(exc).__name__}") from exc
        if payload in ({}, None):
            return None
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("projects"), list):
            raise ProjectFactsSchemaError("Unsupported project facts schema")
        return payload

    def save(self, snapshot):
        write_json(self.resolved_path, snapshot)


def refresh_project_facts(client, store: ProjectFactStore, product_lines=PRODUCT_LINES, *, now=None):
    now = now or datetime.now(timezone.utc)
    previous = store.load() or {"projects": []}
    old_by_id = {row["identity"]: row for row in previous["projects"]}
    seen = set()
    projects = []
    discrepancies = set()
    sources = []

    for line in product_lines:
        source = client.get_page_by_url(line.source_url)
        source_evidence = _page_evidence(source, line.key)
        source_evidence["display_name"] = line.display_name
        sources.append(source_evidence)
        for catalog in _catalog_rows(source, line.key):
            catalog["catalog_source"] = source_evidence
            identity = catalog["identity"]
            seen.add(identity)
            discrepancies.update(catalog.pop("discrepancies"))
            old = old_by_id.get(identity)
            try:
                catalog_unchanged = bool(
                    old and old.get("catalog_fingerprint") == catalog["catalog_fingerprint"]
                )
                if old:
                    detail_metadata, detail_path = _basic_information_metadata(
                        client, catalog["page_id"],
                    )
                    detail_unchanged = _same_page_evidence(
                        old.get("detail_source"), detail_metadata,
                    )
                    if catalog_unchanged and detail_unchanged:
                        row = deepcopy(old)
                        row.update(catalog)
                        row.update(active=True, status="current", error=None)
                        projects.append(row)
                        continue
                    detail = client.get_page(detail_metadata.id)
                else:
                    detail, detail_path = _basic_information_page(client, catalog["page_url"])
                roles = _extract_roles(detail.body or detail.view_body)
                row = {
                    **catalog, "roles": roles, "active": True, "status": "current",
                    "error": None, "detail_source": _page_evidence(detail, line.key),
                    "detail_path": detail_path,
                    "updated_at": now.isoformat(),
                }
            except Exception as exc:
                if old:
                    row = deepcopy(old)
                    row.update(catalog)
                    row.update(active=True, status="stale", error={"type": type(exc).__name__, "message": str(exc)},
                               updated_at=now.isoformat())
                else:
                    row = {
                        **catalog, "roles": {label: [] for label in ROLE_LABELS},
                        "active": True, "status": "failed",
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                        "detail_source": None, "updated_at": now.isoformat(),
                    }
            projects.append(row)

    for identity, old in old_by_id.items():
        if identity not in seen:
            row = deepcopy(old)
            row.update(active=False, status="inactive", updated_at=now.isoformat())
            projects.append(row)
            discrepancies.update(row.get("field_discrepancies", ()))
    projects.sort(key=lambda row: (row["project_id"].casefold(), row["identity"].casefold()))
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "source": "Confluence Product Line Project Spaces",
        "updated_at": now.isoformat(), "sources": sources,
        "field_discrepancies": sorted(discrepancies, key=str.casefold),
        "projects": projects,
    }
    store.save(snapshot)
    return snapshot


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
    product_spaces = filters.get(PRODUCT_SPACE_FACET, ())
    criteria = ProjectCollectionFilter(
        source_url=str((snapshot or {}).get("source") or ""),
        product_line_keys=product_spaces,
        support_modes=filters.get("support mode", ()),
        project_statuses=filters.get("project status", ()),
        current_stages=filters.get("current stage", ()),
        project_space_fields=tuple(
            (key, values) for key, values in filters.items()
            if key not in {PRODUCT_SPACE_FACET, "date of commercial approval", "support mode", "project status", "current stage"}
        ),
        years=tuple(
            int(value) for value in filters.get("date of commercial approval", ())
            if str(value).isdigit()
        ),
        exclude_late_stages=False,
    )
    project_models = [ConfluenceProject(
        year=_commercial_year(row.get("fields", {}).get("date of commercial approval", "")) or 0,
        project_id=row.get("project_id", ""), name=row.get("name", ""),
        status_page_id=row.get("page_id", ""), status_url=row.get("page_url", ""),
        home_url=row.get("page_url", ""), space_key=row.get("space_key", ""),
        page_identity=row.get("project_id", ""), attributes=_fact_fields(row),
        support_mode=_fact_fields(row).get("support mode", ""),
        project_status=_fact_fields(row).get("project status", ""),
        current_stage=_fact_fields(row).get("current stage", ""),
    ) for row in candidates]
    visible_ids = {project.project_identity for project in filter_projects(project_models, criteria).projects}
    rows = []
    for row in candidates:
        identity = f"{row.get('space_key', '')}:{row.get('project_id', '')}" if row.get("space_key") else row.get("project_id", "")
        if identity not in visible_ids:
            continue
        fields = _fact_fields(row)
        people = " ".join(
            f"{person.get('name', '')} {person.get('identity', '')}"
            for role in row.get("roles", {}).values() for person in role
        )
        haystack = " ".join((row.get("project_id", ""), row.get("name", ""), row.get("space_key", ""), people, *fields.values()))
        if needle and needle not in _normalize(haystack):
            continue
        visible = deepcopy(row)
        visible["fields"] = fields
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
    labels = {line.key: line.display_name for line in PRODUCT_LINES}
    labels.update({source.get("space_key"): source.get("display_name")
                   for source in (snapshot or {}).get("sources", []) if source.get("space_key")})
    facets[PRODUCT_SPACE_FACET] = [
        {"value": value, "label": labels.get(value) or value}
        for value in sorted({row.get("space_key", "") for row in rows if row.get("space_key")}, key=str.casefold)
    ]
    hierarchy = _owner_hierarchy(rows)
    safe_filters = summarize_project_fact_filters(filters)
    smart_log(
        "Confluence project facts filtered: input=%s matched=%s excluded=%s",
        len(candidates), len(rows), len(candidates) - len(rows),
        domain="confluence", source="project_facts",
        extra={"input_count": len(candidates), "matched_count": len(rows),
               "excluded_count": len(candidates) - len(rows), "filters": safe_filters,
               "search_enabled": bool(needle)},
    )
    return {"projects": rows, "facets": facets, "ownerHierarchy": hierarchy}


def _fact_fields(row):
    fields = dict(row.get("fields", {}))
    return fields


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
    for table in html_tables(source.view_body or source.body):
        header_index = next((index for index, cells in enumerate(table)
                             if {"page", "project id"} <= {_header(cell) for cell in cells}), None)
        if header_index is None:
            continue
        raw_headers = [text(cell).strip() for cell in table[header_index]]
        normalized_headers = [_header(cell) for cell in table[header_index]]
        for cells in table[header_index + 1:]:
            if len(cells) < len(raw_headers):
                continue
            values = dict(zip(normalized_headers, cells))
            page_links = links(values.get("page", ""))
            project_id = text(values.get("project id", "")).strip()
            if not page_links or not project_id:
                continue
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
    result = []
    for row in merged.values():
        row["raw_headers"] = list(dict.fromkeys(row["raw_headers"]))
        row["discrepancies"] = [header for header in row["raw_headers"] if _normalize(header) not in CANONICAL_HEADERS]
        row["field_discrepancies"] = list(row["discrepancies"])
        row["catalog_fingerprint"] = hashlib.sha256(json.dumps(
            {"identity": row["identity"], "raw_fields": row["raw_fields"]},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        result.append(row)
    return result


def _extract_roles(body):
    roles = {label: [] for label in ROLE_LABELS}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body or "", re.I | re.S):
        cells = re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", row, re.I | re.S)
        if len(cells) < 2:
            continue
        label = text(cells[0]).strip()
        if label not in roles:
            continue
        roles[label] = _people(cells[1])
    return roles


def _basic_information_page(client, page_url):
    entry = client.get_page_by_url(page_url)
    if _is_basic_information(entry.title):
        return entry, [str(entry.id)]
    metadata, path = _basic_information_metadata(client, entry.id)
    return client.get_page(metadata.id), path


def _basic_information_metadata(client, root_page_id):
    queue = [(str(root_page_id), 0, [str(root_page_id)])]
    visited = set()
    while queue:
        page_id, depth, path = queue.pop(0)
        if not page_id or page_id in visited or depth >= 4:
            continue
        visited.add(page_id)
        for child in client.get_page_children(page_id):
            if _is_basic_information(child.title):
                return child, [*path, str(child.id)]
            queue.append((str(child.id), depth + 1, [*path, str(child.id)]))
    raise LookupError("Basic Information page was not found")


def _same_page_evidence(previous, current):
    if not previous or str(previous.get("page_id") or "") != str(current.id or ""):
        return False
    previous_updated = previous.get("updated_at")
    current_updated = current.updated_at.isoformat() if current.updated_at else None
    return int(previous.get("version") or 0) == int(current.version or 0) and previous_updated == current_updated


def _is_basic_information(title):
    clean = re.sub(r"^[\d\s.★☆*#_-]+", "", str(title or "").strip())
    return bool(re.search(r"(?:^|[-–—:])\s*Basic\s+Information\s*$", clean, re.I))


def _people(cell):
    people = []
    covered_names = set()
    user_tags = re.findall(r"<ri:user\b[^>]*/?>", cell, re.I)
    for tag in user_tags:
        identity = _attribute(tag, "ri:account-id") or _attribute(tag, "ri:userkey") or _attribute(tag, "ri:username")
        name = _attribute(tag, "ri:display-name") or identity
        if identity or name:
            people.append({"name": name, "identity": identity})
            covered_names.add(_normalize(name))
    for attrs, body in re.findall(r"<a\b([^>]*)>(.*?)</a>", cell, re.I | re.S):
        name = text(body).strip()
        href = _attribute(attrs, "href")
        query = parse_qs(urlsplit(href).query)
        identity = (_attribute(attrs, "data-account-id") or _attribute(attrs, "data-username")
                    or (query.get("accountId") or query.get("userKey") or query.get("username") or [""])[0])
        if name or identity:
            people.append({"name": name or identity, "identity": identity})
            covered_names.add(_normalize(name))
    plain = re.sub(r"<ri:user\b[^>]*/?>", " ", cell, flags=re.I)
    plain = re.sub(r"<a\b[^>]*>.*?</a>", " ", plain, flags=re.I | re.S)
    plain_names = [name.strip() for name in re.split(r"[,;、，\n]+", text(plain)) if name.strip()]
    if user_tags and len(plain_names) == 1 and len(user_tags) == 1:
        people[0]["name"] = plain_names[0]
        covered_names.add(_normalize(plain_names[0]))
    for name in plain_names:
        name = name.strip()
        if name and _normalize(name) not in covered_names:
            people.append({"name": name, "identity": ""})
    unique = []
    seen = set()
    for person in people:
        key = (person["identity"], _normalize(person["name"]))
        if key not in seen:
            seen.add(key)
            unique.append(person)
    return unique


def _attribute(value, name):
    match = re.search(rf"\b{re.escape(name)}\s*=\s*(['\"])(.*?)\1", value or "", re.I | re.S)
    return match.group(2).strip() if match else ""


def _page_evidence(page, space_key):
    return {"space_key": space_key, "page_id": str(page.id), "url": page.url,
            "version": int(page.version or 0),
            "updated_at": page.updated_at.isoformat() if page.updated_at else None}


def _header(value):
    normalized = _normalize(text(value))
    return "page" if normalized in {"页面", "page"} else normalized


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()
