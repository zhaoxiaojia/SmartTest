from __future__ import annotations

import asyncio

from support.browser_automation.errors import BrowserAutomationError
from support.browser_automation.models import ContextKey
from support.browser_automation.session import BrowserSession


class BrowserRuntime:
    def __init__(self, headless: bool = True, browser_type: str = "chromium", *, launcher=None):
        self._headless = headless
        self._browser_type = browser_type
        self._launcher = launcher or self._launch_playwright
        self._browser = None
        self._playwright = None
        self._sessions: dict[ContextKey, BrowserSession] = {}
        self._lock = asyncio.Lock()

    async def _launch_playwright(self, headless, browser_type):
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            return await getattr(self._playwright, browser_type).launch(headless=headless)
        except Exception as exc:
            raise BrowserAutomationError("Unable to start browser automation") from exc

    async def start(self):
        async with self._lock:
            if self._browser is None:
                self._browser = await self._launcher(self._headless, self._browser_type)

    async def context(self, system_id: str, account_id: str) -> BrowserSession:
        key = ContextKey(system_id.strip(), account_id.strip())
        async with self._lock:
            if self._browser is None:
                self._browser = await self._launcher(self._headless, self._browser_type)
            if key not in self._sessions:
                self._sessions[key] = BrowserSession(await self._browser.new_context())
            return self._sessions[key]

    async def close_context(self, system_id: str, account_id: str):
        async with self._lock:
            session = self._sessions.pop(ContextKey(system_id.strip(), account_id.strip()), None)
        if session: await session.close()

    async def close(self):
        async with self._lock:
            sessions, self._sessions = list(self._sessions.values()), {}
            browser, self._browser = self._browser, None
            playwright, self._playwright = self._playwright, None
        for session in sessions: await session.close()
        if browser: await browser.close()
        if playwright: await playwright.stop()
