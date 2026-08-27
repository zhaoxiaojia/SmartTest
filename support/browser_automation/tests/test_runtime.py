from __future__ import annotations

import asyncio
import sys
from types import ModuleType

import pytest

from support.browser_automation import BrowserRuntime, SupportedBrowserNotInstalledError
from support.browser_automation.errors import BrowserAutomationError


class _PlaywrightError(Exception):
    pass


class _BrowserLauncher:
    def __init__(self, outcomes):
        self._outcomes = dict(outcomes)
        self.channels = []

    async def launch(self, *, headless, channel):
        assert headless is True
        self.channels.append(channel)
        outcome = self._outcomes[channel]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _Driver:
    def __init__(self, launcher):
        self.chromium = launcher
        self.stop_count = 0

    async def stop(self):
        self.stop_count += 1


class _Starter:
    def __init__(self, driver):
        self._driver = driver

    async def start(self):
        return self._driver


def _install_playwright(monkeypatch, driver):
    module = ModuleType("playwright.async_api")
    module.Error = _PlaywrightError
    module.async_playwright = lambda: _Starter(driver)
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)


def test_runtime_falls_back_from_missing_chrome_to_edge(monkeypatch):
    edge_browser = object()
    launcher = _BrowserLauncher(
        {
            "chrome": _PlaywrightError("Chromium distribution 'chrome' is not found"),
            "msedge": edge_browser,
        }
    )
    driver = _Driver(launcher)
    _install_playwright(monkeypatch, driver)
    runtime = BrowserRuntime()

    browser = asyncio.run(runtime._launch_playwright(True, "chromium"))

    assert browser is edge_browser
    assert launcher.channels == ["chrome", "msedge"]
    assert runtime._playwright is driver
    assert driver.stop_count == 0
    asyncio.run(runtime.close())
    assert driver.stop_count == 1


def test_runtime_reports_supported_browser_error_only_when_both_are_missing(monkeypatch):
    launcher = _BrowserLauncher(
        {
            "chrome": _PlaywrightError("Chromium distribution 'chrome' is not found"),
            "msedge": _PlaywrightError("Chromium distribution 'msedge' is not found"),
        }
    )
    driver = _Driver(launcher)
    _install_playwright(monkeypatch, driver)

    with pytest.raises(SupportedBrowserNotInstalledError):
        asyncio.run(BrowserRuntime()._launch_playwright(True, "chromium"))

    assert launcher.channels == ["chrome", "msedge"]
    assert driver.stop_count == 1


def test_runtime_does_not_misclassify_other_chrome_startup_failures(monkeypatch):
    launcher = _BrowserLauncher(
        {"chrome": _PlaywrightError("Browser process closed during startup")}
    )
    driver = _Driver(launcher)
    _install_playwright(monkeypatch, driver)

    with pytest.raises(BrowserAutomationError) as caught:
        asyncio.run(BrowserRuntime()._launch_playwright(True, "chromium"))

    assert not isinstance(caught.value, SupportedBrowserNotInstalledError)
    assert launcher.channels == ["chrome"]
    assert driver.stop_count == 1


def test_runtime_stops_driver_when_browser_launch_is_cancelled(monkeypatch):
    launcher = _BrowserLauncher({"chrome": asyncio.CancelledError()})
    driver = _Driver(launcher)
    _install_playwright(monkeypatch, driver)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(BrowserRuntime()._launch_playwright(True, "chromium"))

    assert launcher.channels == ["chrome"]
    assert driver.stop_count == 1
