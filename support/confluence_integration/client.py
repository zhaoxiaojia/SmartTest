from __future__ import annotations
from dataclasses import replace
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlsplit

try:
    from atlassian import Confluence
except ImportError:
    Confluence = None

from .models import ConfluenceClientConfig, ConfluencePage


class ConfluenceDependencyError(RuntimeError):
    pass


def _date(value: Any) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None

class ConfluenceClient:
    def __init__(self, config: ConfluenceClientConfig, username: str, password: str, *, api=None):
        self.config = config
        if api is not None:
            self._api = api
            return
        try:
            if Confluence is None:
                raise ConfluenceDependencyError(
                    "atlassian-python-api is not installed",
                )
            self._api = Confluence(url=config.base_url.rstrip("/"), username=username, password=password)
        except ConfluenceDependencyError:
            raise
        except Exception as exc:
            raise RuntimeError("Confluence client initialization failed") from exc

    def _url(self, links: dict, key="webui") -> str:
        value = str((links or {}).get(key) or "")
        if value.startswith(("http://", "https://")):
            return value
        return f"{self.config.base_url.rstrip('/')}/{value.lstrip('/')}" if value else ""

    def _page(self, payload: dict, *, prefer_export=False) -> ConfluencePage:
        content = payload.get("content") if isinstance(payload.get("content"), dict) else payload
        version = content.get("version") or {}
        body = content.get("body") or {}
        view_body = str(((body.get("view") or {}).get("value")) or "")
        if prefer_export:
            view_body = str(
                ((body.get("export_view") or {}).get("value")) or view_body
            )
        return ConfluencePage(str(content.get("id") or ""), str(content.get("title") or ""),
            self._url(content.get("_links") or {}),
            str(((body.get("storage") or {}).get("value")) or ""),
            view_body,
            int(version.get("number") or 0), _date(version.get("when")))

    def search_pages(self, cql: str, *, limit: int = 100) -> list[ConfluencePage]:
        pages, start = [], 0
        while True:
            payload = self._api.cql(cql, start=start, limit=limit, expand="body.storage,body.view,version")
            rows = payload.get("results") or []
            pages.extend(self._page(row) for row in rows)
            start += len(rows)
            if not rows or start >= int(payload.get("totalSize") or start):
                return pages

    def get_page(self, page_id: str, *, prefer_export=False) -> ConfluencePage:
        expand = (
            "body.storage,body.view,body.export_view,version"
            if prefer_export else "body.storage,body.view,version"
        )
        return self._page(
            self._api.get_page_by_id(page_id, expand=expand),
            prefer_export=prefer_export,
        )

    def get_page_version(self, page_id: str, version: int) -> ConfluencePage:
        return self._page(self._api.get_page_by_id(
            page_id,
            expand="body.storage,body.view,version",
            status="historical",
            version=int(version),
        ))

    def get_page_by_url(self, url: str, *, prefer_export=False) -> ConfluencePage:
        configured = urlsplit(self.config.base_url)
        parsed = urlsplit(str(url or ""))
        if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold() != configured.netloc.casefold():
            raise ValueError("Confluence page URL must use the configured host")
        page_id = (parse_qs(parsed.query).get("pageId") or [""])[0]
        if page_id:
            return self.get_page(page_id, prefer_export=prefer_export)
        parts = [unquote_plus(item) for item in parsed.path.split("/") if item]
        try:
            marker = parts.index("display")
            space, title = parts[marker + 1], parts[marker + 2]
        except (ValueError, IndexError):
            raise ValueError("Unsupported Confluence page URL") from None
        page_id = self._api.get_page_id(space, title)
        if not page_id:
            raise ValueError("Confluence page could not be resolved")
        return self.get_page(str(page_id), prefer_export=prefer_export)

    def get_parent_page(self, page_id: str) -> ConfluencePage | None:
        ancestors = self._api.get_page_ancestors(page_id) or []
        if not ancestors:
            return None
        parent_id = str((ancestors[-1] or {}).get("id") or "")
        return self.get_page(parent_id) if parent_id else None

    def get_page_children(self, page_id: str, *, limit: int = 100) -> list[ConfluencePage]:
        pages, start, seen_pages = [], 0, set()
        while True:
            payload = self._api.get_page_child_by_type(
                page_id, type="page", start=start, limit=limit,
                expand="version",
            ) or {}
            list_response = isinstance(payload, list)
            rows = payload if list_response else payload.get("results") or []
            if not rows:
                return pages
            signature = tuple(
                (
                    str(row.get("id") or ""),
                    str(row.get("title") or ""),
                    str((row.get("_links") or {}).get("webui") or ""),
                )
                for row in rows
            )
            if signature in seen_pages:
                raise RuntimeError(
                    "Confluence child-page pagination returned a repeated page",
                )
            seen_pages.add(signature)
            pages.extend(
                replace(self._page(row), body="", view_body="")
                for row in rows
            )
            start += len(rows)
            if list_response and len(rows) < limit:
                return pages
            total = None if list_response else payload.get(
                "totalSize", payload.get("total"),
            )
            if (
                total is not None and start >= int(total)
            ) or (
                total is None and len(rows) < limit
            ):
                return pages

    def get_children(self, page_id: str) -> list[ConfluencePage]:
        return self.get_page_children(page_id)
