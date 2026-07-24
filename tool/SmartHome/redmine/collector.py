from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from tool.SmartHome.redmine.models import (
    RedmineAttachment,
    RedmineContext,
    RedmineIssueDetail,
    RedmineIssueListItem,
    RedmineJournal,
    RedmineProject,
)
from tool.SmartHome.redmine.query import RedmineQuery, RedmineQueryBranch

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
    wanted_attrs = {"Status", "Priority", "Assignee", "Category", "Start date", "Due date", "% Done", "Estimated time", "Created", "Created on"}
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
    seen: set[str] = set()
    for node in raw_nodes:
        identifier = _identifier_from_url(str(node.get("href") or ""))
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        container_text = _clean(node.get("containerText") or node.get("text"))
        projects.append(
            RedmineProject(
                name=_clean(node.get("text")),
                identifier=identifier,
                url=str(node.get("href") or "").split("?", 1)[0],
                project_id=str(node.get("projectId") or _parse_project_id(container_text)),
            )
        )
    return tuple(projects)


def project_options(projects: tuple[RedmineProject, ...]) -> list[dict[str, str]]:
    return [
        {
            "id": project.identifier,
            "label": project.name or project.identifier,
            "projectId": project.project_id,
        }
        for project in projects
    ]


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
    if _clean(raw.get("created_at")):
        attrs.setdefault("Created", _clean(raw.get("created_at")))

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
        tracker=tracker_match.group(1) if tracker_match else (list_item.tracker if list_item else ""),
        subject=_clean(raw.get("subject") or raw.get("issueHeader")) or (list_item.subject if list_item else ""),
        description=_clean(raw.get("description")) or text_payload["description"],
        attributes=attrs,
        comments=comments,
        attachments=tuple(attachments),
        list_item=list_item,
    )


class RedmineContextCollector:
    def __init__(
        self,
        page,
        *,
        account: str = "",
        base_url: str = BASE_URL,
        max_concurrency: int = 8,
    ):
        self._page = page
        self._account = account
        self._base_url = base_url.rstrip("/")
        self._page_semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _goto_and_wait(self, url: str, selector: str, *, timeout: int = 8000) -> None:
        await self._goto_and_wait_on(self._page, url, selector, timeout=timeout)

    async def collect_projects(self) -> tuple[RedmineProject, ...]:
        await self._goto_and_wait(f"{self._base_url}/projects", "a.project, #projects-index, #content")
        raw_nodes = await self._page.evaluate(_PROJECTS_SCRIPT)
        return parse_project_nodes(raw_nodes)

    async def collect_my_page_assigned(self) -> list[dict[str, Any]]:
        await self._goto_and_wait(f"{self._base_url}/my/page", "#block-issuesassignedtome, #content")
        raw_rows = await self._page.evaluate(_MY_ASSIGNED_SCRIPT)
        issues = parse_issue_list(raw_rows)
        rows = []
        for raw, issue in zip(raw_rows, issues):
            project_url = str(raw.get("projectHref") or "")
            rows.append({
                "issue": issue,
                "project_name": _clean(raw.get("projectName")),
                "project_url": project_url,
                "project_identifier": _identifier_from_url(project_url),
            })
        return rows

    async def collect_filter_metadata(self, *, project: str = "") -> dict[str, str]:
        path = f"/projects/{project}/issues" if project else "/issues"
        await self._goto_and_wait(f"{self._base_url}{path}?set_filter=1", "#add_filter_select, #values_tracker_id, #content")
        if hasattr(self._page, "select_option"):
            try:
                await self._page.select_option("#add_filter_select", "tracker_id")
                await self._page.wait_for_selector("select#values_tracker_id, select[name='v[tracker_id][]']", state="attached", timeout=3000)
            except Exception:
                pass
        options = await self._page.evaluate(_FILTER_METADATA_SCRIPT)
        return {
            _clean(option.get("label")): str(option.get("value") or "").strip()
            for option in options
            if _clean(option.get("label")) and str(option.get("value") or "").strip()
        }

    async def collect_query(self, query: RedmineQuery) -> RedmineContext:
        merged: dict[str, tuple[RedmineIssueListItem, str, str]] = {}
        for branch in query.branches():
            page_number = 1
            while True:
                payload = await self._fetch_query_page(branch, page_number=page_number, per_page=100)
                raw_rows = list(payload.get("rows") or [])
                for raw, issue in zip(raw_rows, parse_issue_list(raw_rows)):
                    identifier, name = self._query_row_project(raw, branch.project)
                    merged.setdefault(issue.id, (issue, identifier, name))
                total = int(payload.get("total") or len(raw_rows))
                if page_number * 100 >= total or not raw_rows:
                    break
                page_number += 1
        grouped: dict[str, list[RedmineIssueListItem]] = {}
        names: dict[str, str] = {}
        for issue, identifier, name in merged.values():
            grouped.setdefault(identifier, []).append(issue)
            names.setdefault(identifier, name)
        projects = tuple(
            RedmineProject(
                name=names.get(identifier) or identifier,
                identifier=identifier,
                url=f"{self._base_url}/projects/{identifier}" if identifier else "",
                project_id="",
                issues=tuple(sorted(issues, key=lambda item: int(item.id), reverse=True)),
            )
            for identifier, issues in grouped.items()
        )
        return RedmineContext(account=self._account, projects=projects)

    async def _fetch_query_page(self, branch: RedmineQueryBranch, *, page_number: int, per_page: int) -> dict[str, Any]:
        url = self._query_url(branch, page_number, per_page)
        async with self._page_semaphore:
            await self._goto_and_wait_on(self._page, url, "table.issues, .nodata, #content")
            return await self._page.evaluate(_ISSUE_PAGE_SCRIPT)

    def _query_url(self, branch: RedmineQueryBranch, page_number: int, per_page: int) -> str:
        path = f"/projects/{branch.project}/issues" if branch.project else "/issues"
        return f"{self._base_url}{path}?{urlencode(branch.params(page_number, per_page))}"

    @staticmethod
    def _query_row_project(raw: dict[str, Any], fallback: str) -> tuple[str, str]:
        for cell in raw.get("cells") or []:
            if str(cell.get("className") or "") == "project":
                link = next(iter(cell.get("links") or []), {})
                identifier = _identifier_from_url(str(link.get("href") or ""))
                return identifier or fallback, _clean(link.get("text") or cell.get("text") or identifier or fallback)
        return fallback, fallback

    async def _goto_and_wait_on(self, page, url: str, selector: str, *, timeout: int = 8000) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        if hasattr(page, "wait_for_selector"):
            try:
                await page.wait_for_selector(selector, state="attached", timeout=timeout)
            except Exception:
                pass

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
        return detail

_PROJECTS_SCRIPT = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  return Array.from(document.querySelectorAll('#projects-index a.project')).map((a, idx) => {
    const container = a.parentElement || a;
    const containerText = clean(container.innerText || a.innerText || '');
    const match = containerText.match(/\[Project ID\]:\s*([^\s\[]+)/);
    return {
      idx,
      text: clean(a.innerText || a.textContent),
      href: a.href,
      containerText,
      projectId: match ? match[1] : ''
    };
  });
}
"""

_MY_ASSIGNED_SCRIPT = r"""
() => {
  const block = document.querySelector('#block-issuesassignedtome');
  if (!block) return [];
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  return Array.from(block.querySelectorAll('table.list.issues tbody tr.issue, table.issues tbody tr')).map(tr => {
    const project = tr.querySelector('td.project a[href]');
    return {
      id: tr.id,
      projectName: clean(project?.innerText || tr.querySelector('td.project')?.innerText),
      projectHref: project?.href || '',
      cells: Array.from(tr.querySelectorAll('td')).map(td => ({
        className: Array.from(td.classList).find(name => name !== 'hide-when-print') || td.className,
        text: clean(td.innerText),
        links: Array.from(td.querySelectorAll('a[href]')).map(a => ({text: clean(a.innerText || a.textContent), href: a.href}))
      }))
    };
  });
}
"""

_ISSUE_PAGE_SCRIPT = r"""
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const rows = Array.from(document.querySelectorAll('table.issues tbody tr')).map((tr, r) => ({
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
  const pagination = clean(document.querySelector('.pagination')?.innerText || '');
  const text = clean(pagination || document.body?.innerText || '');
  const totalMatch = text.match(/\((?:\d+\s*-\s*)?\d+\s*\/\s*(\d+)\)/) || text.match(/\b(?:\d+\s*-\s*)?\d+\s*\/\s*(\d+)\b/);
  return { rows, total: totalMatch ? Number(totalMatch[1]) : rows.length, pagination };
}
"""

_FILTER_METADATA_SCRIPT = r"""
() => {
  const select = document.querySelector('select#values_tracker_id, select[name="v[tracker_id][]"], #tr_tracker_id select');
  if (!select) return [];
  return Array.from(select.options).map(option => ({label: (option.textContent || '').trim(), value: option.value || ''}));
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
    created_at: document.querySelector('.issue .author a[title], p.author a[title]')?.getAttribute('title') || clean(document.querySelector('.issue .author, p.author')?.innerText || ''),
    h1: clean(document.querySelector('h1')?.innerText),
    issueHeader: clean(document.querySelector('.issue.details .subject h3, .issue.details .subject, div.issue .subject h3, div.issue .subject, div.issue h3')?.innerText || ''),
    description: clean(document.querySelector('.description .wiki, .description, #content .wiki')?.innerText || '').replace(/^Quote Description\s*/, ''),
    attrs: Array.from(document.querySelectorAll('.attributes .attribute, .attribute')).map(attr => ({ label: clean(attr.querySelector('.label')?.innerText || ''), value: clean(attr.querySelector('.value')?.innerText || '') })),
    journals: Array.from(document.querySelectorAll('#history .journal, .journal')).map(j => ({ id: j.id, header: clean(j.querySelector('h4, h5')?.innerText || ''), author: clean(j.querySelector('h4 a.user, h5 a.user, a.user')?.innerText || ''), note: clean(j.querySelector('.wiki, .journal-notes')?.innerText || ''), details: Array.from(j.querySelectorAll('ul.details li, ul.journal-details li')).map(li => clean(li.innerText)), created_at: j.querySelector('a.journal-link[title], h4 a[title], h5 a[title], a[title]')?.getAttribute('title') || '' })),
    attachments: attachmentRows,
    contentText: clean(document.querySelector('#content')?.innerText || '')
  };
}
"""
