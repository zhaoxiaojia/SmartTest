from __future__ import annotations

import re
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from support.logging import smart_log
from tool.SmartHome.redmine.models import (
    RedmineAttachment,
    RedmineContext,
    RedmineIssueDetail,
    RedmineIssueListItem,
    RedmineJournal,
    RedmineProject,
)

BASE_URL = "https://support.amlogic.com"
PROJECTS_URL = f"{BASE_URL}/projects"


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _identifier_from_url(url: str) -> str:
    path = urlsplit(str(url or "")).path.strip("/")
    parts = path.split("/")
    return parts[1] if len(parts) >= 2 and parts[0] == "projects" else ""


def _issue_id_from_url(url: str) -> str:
    match = re.search(r"/issues/(\d+)", str(url or ""))
    return match.group(1) if match else ""


def _attachment_id_from_url(url: str) -> str:
    match = re.search(r"/attachments/(?:download/)?(\d+)", str(url or ""))
    return match.group(1) if match else ""


def _parse_project_id(text: str) -> str:
    match = re.search(r"\[Project ID\]:\s*([^\s\[]+)", text or "")
    return match.group(1).strip() if match else ""


def _parse_content_text(raw: dict[str, Any]) -> dict[str, Any]:
    lines = [line for line in (_clean(line) for line in str(raw.get("contentText") or "").splitlines()) if line]
    wanted_attrs = {"Status", "Priority", "Assignee", "Category", "Start date", "Due date", "% Done", "Estimated time"}
    stop_sections = {"Files", "Subtasks", "Related issues", "History Notes Property changes", "History", "Notes", "Property changes"}
    attrs: dict[str, str] = {}
    description: list[str] = []
    journals: list[RedmineJournal] = []
    current: dict[str, Any] | None = None
    in_description = False

    def flush_journal() -> None:
        if current:
            journals.append(
                RedmineJournal(
                    id=str(current["id"]),
                    author=str(current["author"]),
                    header=str(current["header"]),
                    note="\n".join(current["note"]).strip(),
                    details=tuple(current["details"]),
                )
            )

    for line in lines:
        if line == "Description":
            in_description = True
            continue
        if in_description and line in stop_sections:
            in_description = False
        if in_description:
            description.append(line)
            continue

        attr_match = re.match(r"^([^:]+):\s*(.+)$", line)
        if attr_match and attr_match.group(1).strip() in wanted_attrs:
            attrs[attr_match.group(1).strip()] = attr_match.group(2).strip()
            continue

        journal_match = re.match(r"^Updated by\s+(.+?)\s+.+\s+#(\d+)$", line)
        if journal_match:
            flush_journal()
            current = {"id": journal_match.group(2), "author": journal_match.group(1), "header": line, "note": [], "details": []}
            continue
        if current:
            if line.startswith(("•", "-")):
                current["details"].append(line.lstrip("•- ").strip())
            elif line not in {"History Notes Property changes"}:
                current["note"].append(line)

    flush_journal()
    return {
        "attrs": attrs,
        "description": "\n".join(description).strip(),
        "journals": tuple(journal for journal in journals if journal.note or journal.details),
    }


def parse_project_nodes(raw_nodes: list[dict[str, Any]]) -> tuple[RedmineProject, ...]:
    projects: list[RedmineProject] = []
    last_root = ""
    children_by_parent: dict[str, list[str]] = {}
    for node in raw_nodes:
        class_name = str(node.get("className") or "")
        parent_class = str(node.get("parentClass") or "")
        identifier = _identifier_from_url(str(node.get("href") or ""))
        if not identifier:
            continue
        is_child = " child " in f" {class_name} " and parent_class != "root"
        parent_identifier = last_root if is_child else ""
        level = 1 if is_child else 0
        if not is_child:
            last_root = identifier
        if parent_identifier:
            children_by_parent.setdefault(parent_identifier, []).append(identifier)
        container_text = _clean(node.get("containerText") or node.get("text"))
        projects.append(
            RedmineProject(
                name=_clean(node.get("text")),
                identifier=identifier,
                url=str(node.get("href") or "").split("?", 1)[0],
                project_id=str(node.get("projectId") or _parse_project_id(container_text)),
                parent_identifier=parent_identifier,
                level=level,
            )
        )
    return tuple(replace(project, children=tuple(children_by_parent.get(project.identifier, ()))) for project in projects)


def parse_issue_list(raw_rows: list[dict[str, Any]]) -> tuple[RedmineIssueListItem, ...]:
    issues: list[RedmineIssueListItem] = []
    for row in raw_rows:
        fields = {str(cell.get("className") or ""): _clean(cell.get("text")) for cell in row.get("cells", [])}
        links = [link for cell in row.get("cells", []) for link in cell.get("links", [])]
        issue_url = next((str(link.get("href") or "") for link in links if _issue_id_from_url(str(link.get("href") or ""))), "")
        issue_id = _issue_id_from_url(issue_url) or _clean(fields.get("id")) or str(row.get("id") or "").replace("issue-", "")
        issues.append(
            RedmineIssueListItem(
                id=issue_id,
                url=issue_url,
                tracker=fields.get("tracker", ""),
                status=fields.get("status", ""),
                priority=fields.get("priority", ""),
                subject=fields.get("subject", ""),
                assignee=fields.get("assigned_to", ""),
                updated_at=fields.get("updated_on", ""),
                category=fields.get("category", ""),
                raw_fields=fields,
            )
        )
    return tuple(issues)


def parse_issue_detail(raw: dict[str, Any], *, list_item: RedmineIssueListItem | None = None) -> RedmineIssueDetail:
    text_payload = _parse_content_text(raw)
    attrs = {
        _clean(item.get("label")).rstrip(":"): _clean(item.get("value"))
        for item in raw.get("attrs", [])
        if _clean(item.get("label"))
    } or text_payload["attrs"]

    attachments = []
    for item in raw.get("attachments", []):
        filename = _clean(item.get("filename"))
        detail_url = str(item.get("detail_url") or "")
        download_url = str(item.get("download_url") or "")
        attachment_id = str(item.get("id") or _attachment_id_from_url(download_url) or _attachment_id_from_url(detail_url))
        if filename and attachment_id:
            attachments.append(
                RedmineAttachment(
                    id=attachment_id,
                    filename=filename,
                    size=_clean(item.get("size")),
                    author=_clean(item.get("author")),
                    created_at=_clean(item.get("created_at")),
                    detail_url=detail_url,
                    download_url=download_url,
                )
            )

    comments = tuple(
        RedmineJournal(
            id=str(item.get("id") or ""),
            author=_clean(item.get("author")),
            header=_clean(item.get("header")),
            note=_clean(item.get("note")),
            details=tuple(_clean(detail) for detail in item.get("details", []) if _clean(detail)),
            created_at=_clean(item.get("created_at") or item.get("created")),
        )
        for item in raw.get("journals", [])
    ) or text_payload["journals"]

    issue_url = str(raw.get("href") or "")
    issue_id = str(raw.get("id") or _issue_id_from_url(issue_url) or (list_item.id if list_item else ""))
    tracker_match = re.search(r"\b(Bug|Support)\s+#\d+", _clean(raw.get("contentText")))
    return RedmineIssueDetail(
        id=issue_id,
        url=issue_url,
        project_identifier=_identifier_from_url(str(raw.get("project_url") or "")),
        project_name=_clean(raw.get("project_name") or raw.get("h1")),
        tracker=tracker_match.group(1) if tracker_match else (list_item.tracker if list_item else ""),
        subject=_clean(raw.get("subject") or raw.get("issueHeader")) or (list_item.subject if list_item else ""),
        description=_clean(raw.get("description")) or text_payload["description"],
        attributes=attrs,
        comments=comments,
        attachments=tuple(attachments),
        list_item=list_item,
    )


class RedmineContextCollector:
    def __init__(self, page, *, account: str = "", base_url: str = BASE_URL):
        self._page = page
        self._account = account
        self._base_url = base_url.rstrip("/")

    async def _goto_and_wait(self, url: str, selector: str, *, timeout: int = 8000) -> None:
        await self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
        if hasattr(self._page, "wait_for_selector"):
            try:
                await self._page.wait_for_selector(selector, state="attached", timeout=timeout)
            except Exception:
                pass

    async def collect_projects(self) -> tuple[RedmineProject, ...]:
        await self._goto_and_wait(f"{self._base_url}/projects", "a.project, #projects-index, #content")
        raw_nodes = await self._page.evaluate(_PROJECTS_SCRIPT)
        return parse_project_nodes(raw_nodes)

    async def collect_issue_list(self, project: RedmineProject) -> tuple[RedmineIssueListItem, ...]:
        url = f"{self._base_url}/projects/{project.identifier}/issues?set_filter=1"
        await self._goto_and_wait(url, "table.issues, .nodata, #content")
        raw_rows = await self._page.evaluate(_ISSUE_LIST_SCRIPT)
        return parse_issue_list(raw_rows)

    async def collect_issue_detail(
        self,
        issue: RedmineIssueListItem | str,
        *,
        project: RedmineProject | None = None,
    ) -> RedmineIssueDetail:
        issue_id = issue.id if isinstance(issue, RedmineIssueListItem) else str(issue)
        url = issue.url if isinstance(issue, RedmineIssueListItem) and issue.url else f"{self._base_url}/issues/{issue_id}"
        await self._goto_and_wait(url, ".issue.details, div.issue, #content")
        raw = await self._page.evaluate(_ISSUE_DETAIL_SCRIPT)
        if project:
            raw["project_url"] = project.url
            raw["project_name"] = project.name
        detail = parse_issue_detail(raw, list_item=issue if isinstance(issue, RedmineIssueListItem) else None)
        if not detail.subject or not detail.attributes:
            smart_log(
                "[redmine-debug] detail parse incomplete issue=%s subject=%s attrs=%d comments=%d attachments=%d content_chars=%d",
                issue_id,
                bool(detail.subject),
                len(detail.attributes),
                len(detail.comments),
                len(detail.attachments),
                len(str(raw.get("contentText") or "")),
                domain="tool",
                source="RedmineContextCollector",
                level="warning",
            )
        return detail

    async def collect_context(self) -> RedmineContext:
        projects = []
        for project in await self.collect_projects():
            enriched = project
            if project.project_id:
                enriched = replace(project, issues=await self.collect_issue_list(project))
            projects.append(enriched)
        return RedmineContext(
            account=self._account,
            source_url=self._base_url,
            projects=tuple(projects),
            raw={"project_count": len(projects)},
            jira={"issues": []},
        )


_PROJECTS_SCRIPT = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  return Array.from(document.querySelectorAll('a.project')).map((a, idx) => {
    const parent = a.parentElement;
    const containerText = clean(parent?.innerText || a.closest('li,div')?.innerText || '');
    const match = containerText.match(/\[Project ID\]:\s*([^\s\[]+)/);
    return {
      idx,
      text: clean(a.innerText || a.textContent),
      href: a.href,
      className: a.className,
      parentClass: parent?.className || '',
      containerText,
      projectId: match ? match[1] : ''
    };
  });
}
"""

_ISSUE_LIST_SCRIPT = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  return Array.from(document.querySelectorAll('table.issues tbody tr')).map((tr, r) => ({
    r,
    id: tr.id,
    className: tr.className,
    cells: Array.from(tr.querySelectorAll('td')).map((td, c) => ({
      c,
      className: Array.from(td.classList).find(name => !['hide-when-print'].includes(name)) || td.className,
      text: clean(td.innerText),
      links: Array.from(td.querySelectorAll('a[href]')).map(a => ({ text: clean(a.innerText || a.textContent), href: a.href }))
    }))
  }));
}
"""

_ISSUE_DETAIL_SCRIPT = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const attachmentContainers = Array.from(document.querySelectorAll('.attachments p, .attachments li, .attachments .attachment, #content a[href*="/attachments/"]')).map(el => el.closest('p,li,div,tr') || el);
  const attachmentRows = Array.from(new Set(attachmentContainers)).map(p => {
    const links = Array.from(p.querySelectorAll ? p.querySelectorAll('a[href]') : [p]).map(a => ({ text: clean(a.innerText || a.textContent), href: a.href || '', className: a.className || '', title: a.getAttribute ? (a.getAttribute('title') || '') : '' }));
    const detail = links.find(a => /\/attachments\/\d+$/.test(a.href));
    const download = links.find(a => /\/attachments\/download\/\d+\//.test(a.href));
    const text = clean(p.innerText || p.textContent);
    const meta = text.match(/\(([^)]+)\)\s*(.*?),\s*(\d{2}\/\d{2}\/\d{4}.*)$/);
    return { id: detail ? (detail.href.match(/\/attachments\/(\d+)/) || [])[1] : '', filename: detail?.text || download?.text || '', size: meta ? meta[1] : '', author: meta ? meta[2] : '', created_at: meta ? meta[3] : '', detail_url: detail?.href || '', download_url: download?.href || '' };
  }).filter(item => item.filename);
  return {
    href: location.href,
    h1: clean(document.querySelector('h1')?.innerText),
    issueHeader: clean(document.querySelector('.issue.details .subject h3, .issue.details .subject, div.issue .subject h3, div.issue .subject, div.issue h3')?.innerText || ''),
    description: clean(document.querySelector('.description .wiki, .description, #content .wiki')?.innerText || '').replace(/^Quote Description\s*/, ''),
    attrs: Array.from(document.querySelectorAll('.attributes .attribute, .attribute')).map(attr => ({ label: clean(attr.querySelector('.label')?.innerText || ''), value: clean(attr.querySelector('.value')?.innerText || '') })),
    journals: Array.from(document.querySelectorAll('#history .journal, .journal')).map(j => ({ id: j.id, header: clean(j.querySelector('h4')?.innerText || ''), author: clean(j.querySelector('.user')?.innerText || ''), note: clean(j.querySelector('.wiki, .journal-notes')?.innerText || ''), details: Array.from(j.querySelectorAll('ul.details li')).map(li => clean(li.innerText)), created_at: j.querySelector('a.journal-link')?.getAttribute('title') || '' })),
    attachments: attachmentRows,
    contentText: clean(document.querySelector('#content')?.innerText || '')
  };
}
"""
