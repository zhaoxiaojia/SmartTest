from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .models import MISSING_QA
from .rules import AuditAttentionPoint
from .html import html_tables, text


_HEADING = re.compile(
    r"<h(?P<level>[1-6])\b[^>]*>(?P<title>.*?)</h(?P=level)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_PLAIN_LABEL = re.compile(
    r"<(?P<tag>p|span)\b[^>]*>(?P<value>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_OWNER_POINT = AuditAttentionPoint(
    stable_key="owner.qa",
    source_page="status",
    source_field="QA",
    output_key="QA",
    owner="extract_project_owner",
    failure_semantic="missing_qa",
    label="",
    table_fields=("Window",),
)


@dataclass(frozen=True)
class RegionExtraction:
    found: bool
    content: str = ""
    locator_type: str = ""
    element_type: str = ""
    locator: str = ""
    boundary: str = ""
    source: str = ""


def extract_project_owner(page):
    region = extract_page_region(page, _OWNER_POINT)
    if not region.found:
        return MISSING_QA
    owner = _normalize_content(region.content.replace("@", ""))
    return owner or MISSING_QA


def extract_page_region(page, point):
    view = extract_region(page.view_body, point)
    if view.found and page.view_body:
        return replace(view, source="view")
    storage = extract_region(page.body, point)
    if storage.found:
        return replace(storage, source="storage")
    if view.found:
        return replace(view, source="view")
    return replace(storage, source="none")


def extract_region(body, point):
    source = str(body or "")
    heading_names = tuple(_heading_label(value) for value in point.heading_names)
    headings = list(_HEADING.finditer(source))
    for index, heading in enumerate(headings):
        title = text(heading.group("title"))
        label, inline_value = _structural_label(title)
        if not _matches_label(label, heading_names):
            continue
        end = len(source)
        boundary = "page_end"
        if point.heading_boundary == "sibling":
            level = int(heading.group("level"))
            for following in headings[index + 1:]:
                if int(following.group("level")) <= level:
                    end = following.start()
                    break
            boundary = "heading_sibling"
        content = _join_content(inline_value, source[heading.end():end])
        return RegionExtraction(
            True, content, "heading", "heading", label, boundary,
        )

    for macro in re.findall(
        r"<ac:structured-macro\b[^>]*>(.*?)</ac:structured-macro>",
        source,
        re.IGNORECASE | re.DOTALL,
    ):
        titles = re.findall(
            r'<ac:parameter\b[^>]*ac:name=["\']title["\'][^>]*>'
            r"(.*?)</ac:parameter>",
            macro,
            re.IGNORECASE | re.DOTALL,
        )
        if not titles or not _matches_label(
            _heading_label(text(titles[0])), heading_names,
        ):
            continue
        rich_body = re.search(
            r"<ac:rich-text-body\b[^>]*>(.*?)</ac:rich-text-body>",
            macro,
            re.IGNORECASE | re.DOTALL,
        )
        content = _normalize_content(
            rich_body.group(1) if rich_body else macro,
        )
        return RegionExtraction(
            True, content, "macro_title", "macro",
            _heading_label(text(titles[0])), "macro_body",
        )

    for plain in _PLAIN_LABEL.finditer(source):
        label, inline_value = _structural_label(text(plain.group("value")))
        if not _matches_label(label, heading_names):
            continue
        following_heading = next(
            (heading for heading in headings if heading.start() >= plain.end()),
            None,
        )
        end = following_heading.start() if following_heading else len(source)
        content = _join_content(inline_value, source[plain.end():end])
        element_type = plain.group("tag").casefold()
        return RegionExtraction(
            True, content, "plain_label", element_type, label,
            "next_heading",
        )

    table_fields = tuple(_label(value) for value in point.table_fields)
    table_region_fields = tuple(
        _label(value) for value in point.table_region_fields
    )
    tables = html_tables(source)
    for table_index, table in enumerate(tables):
        for row_index, cells in enumerate(table):
            for cell_index, cell in enumerate(cells):
                label, inline_value = _table_field(cell)
                if _matches_label(label, table_region_fields):
                    content = _normalize_content(" ".join(
                        item
                        for row in table[row_index + 1:]
                        for item in row
                    ))
                    return RegionExtraction(
                        True, content, "table_region", "table", label,
                        "table_data_rows",
                    )
                if not _matches_label(label, table_fields):
                    continue
                if inline_value:
                    content = _normalize_content(inline_value)
                    boundary = "inline_value"
                elif cell_index + 1 < len(cells):
                    content = _normalize_content(cells[cell_index + 1])
                    boundary = "adjacent_cell"
                elif table_index + 1 < len(tables):
                    content = _normalize_content(" ".join(
                        item
                        for row in tables[table_index + 1]
                        for item in row
                    ))
                    boundary = "following_table"
                else:
                    content = ""
                    boundary = "field_only"
                return RegionExtraction(
                    True, content, "table_field", "table", label, boundary,
                )
    if point.use_page_body:
        content = _normalize_content(_HEADING.sub("", source))
        return RegionExtraction(
            True, content, "page", "page", point.standard_name,
            "page_body",
        )
    return RegionExtraction(False)


def _content(value):
    return re.sub(r"\s+", " ", text(value)).strip()


def _normalize_content(value):
    content = _content(value)
    if re.fullmatch(r"-+", content) or re.fullmatch(
        r"(?:title\s+)?no content found\.?|(?:标题\s+)?未找到内容。?",
        content,
        re.IGNORECASE,
    ):
        return ""
    return content


def _join_content(inline_value, region):
    inline = _normalize_content(inline_value)
    if inline.startswith("---"):
        inline = ""
    body = _normalize_content(region)
    return " ".join(value for value in (inline, body) if value).strip()


def _label(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _matches_label(label, keywords):
    return any(keyword and keyword in label for keyword in keywords)


def _heading_label(value):
    normalized = _label(value)
    normalized = re.sub(
        r"^(?:[•●▪·]\s*|(?:[ivxlcdm]+|\d+)[.)、．]\s*)+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return re.split(r"\s*[:：]\s*", normalized, maxsplit=1)[0].strip()


def _structural_label(value):
    raw = re.sub(r"\s+", " ", str(value or "")).strip()
    parts = re.split(r"\s*[:：]\s*", raw, maxsplit=1)
    return _heading_label(parts[0]), parts[1].strip() if len(parts) == 2 else ""


def _table_field(value):
    raw = re.sub(r"\s+", " ", text(value)).strip()
    parts = re.split(r"\s*[:：]\s*", raw, maxsplit=1)
    return _label(parts[0]), parts[1].strip() if len(parts) == 2 else ""
