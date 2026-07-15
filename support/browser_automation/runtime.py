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
        driver = None
        try:
            from playwright.async_api import async_playwright
            driver = await async_playwright().start()
            browser = await getattr(driver, browser_type).launch(headless=headless)
            self._playwright = driver
            return browser
        except Exception as exc:
            if driver is not None:
                try:
                    await driver.stop()
                except Exception:
                    pass
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
            if key in self._sessions and self._sessions[key].closed:
                self._sessions.pop(key)
            if key not in self._sessions:
                def remove(closed_session):
                    if self._sessions.get(key) is closed_session:
                        self._sessions.pop(key, None)
                self._sessions[key] = BrowserSession(await self._browser.new_context(), on_close=remove)
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
        failures = []
        for session in sessions:
            try: await session.close()
            except Exception: failures.append("context")
        if browser:
            try: await browser.close()
            except Exception: failures.append("browser")
        if playwright:
            try: await playwright.stop()
            except Exception: failures.append("driver")
        if failures:
            raise BrowserAutomationError("Browser automation cleanup failed: " + ", ".join(failures))
