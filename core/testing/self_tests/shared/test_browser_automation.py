import asyncio
import os
import sys

from core.browser_automation import BrowserRuntime
from core.browser_automation.errors import BrowserAutomationError
from playwright.async_api import Error as PlaywrightError


class FakeContext:
    def __init__(self): self.closed = False
    async def new_page(self): return object()
    async def close(self): self.closed = True


class FakeBrowser:
    def __init__(self): self.contexts = []; self.closed = False
    async def new_context(self):
        context = FakeContext(); self.contexts.append(context); return context
    async def close(self): self.closed = True


def test_runtime_reuses_browser_and_isolates_context_keys():
  async def scenario():
    browser = FakeBrowser(); launches = []
    async def launcher(_headless, _browser_type): launches.append(1); return browser
    runtime = BrowserRuntime(launcher=launcher)
    first = await runtime.context("redmine", "alice")
    assert await runtime.context("redmine", "alice") is first
    second = await runtime.context("redmine", "bob")
    assert second is not first and len(browser.contexts) == 2 and launches == [1]
    await runtime.close_context("redmine", "alice")
    assert browser.contexts[0].closed
    recreated = await runtime.context("redmine", "alice")
    assert recreated is not first and len(browser.contexts) == 3
    await runtime.close()
    assert browser.closed and browser.contexts[1].closed
  asyncio.run(scenario())


def test_cleanup_attempts_browser_after_context_failure():
  class BadContext(FakeContext):
    async def close(self): self.closed = True; raise RuntimeError("secret detail")
  class RecordingBrowser(FakeBrowser):
    async def new_context(self):
      context = BadContext(); self.contexts.append(context); return context
  async def scenario():
    browser = RecordingBrowser()
    runtime = BrowserRuntime(launcher=lambda *_: async_value(browser))
    await runtime.context("redmine", "alice")
    try: await runtime.close()
    except BrowserAutomationError as exc:
      assert "secret detail" not in str(exc)
    else: raise AssertionError("cleanup failure must be reported")
    assert browser.closed
  asyncio.run(scenario())


async def async_value(value): return value


def test_system_browser_launch_prefers_chrome_without_trying_edge(monkeypatch):
  launches = []
  browser = FakeBrowser()
  class BrowserType:
    async def launch(self, **options):
      launches.append(options)
      return browser
  class Driver:
    chromium = BrowserType()
    async def stop(self): pass
  class Starter:
    async def start(self): return Driver()
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())

  runtime = BrowserRuntime()
  asyncio.run(runtime.start())

  assert launches == [{"headless": True, "channel": "chrome"}]
  asyncio.run(runtime.close())


def test_system_browser_launch_tries_edge_only_when_chrome_is_not_installed(monkeypatch):
  launches = []
  browser = FakeBrowser()
  class BrowserType:
    async def launch(self, **options):
      launches.append(options)
      if options["channel"] == "chrome":
        raise PlaywrightError("Chromium distribution 'chrome' is not found at C:/Chrome")
      return browser
  class Driver:
    chromium = BrowserType()
    async def stop(self): pass
  class Starter:
    async def start(self): return Driver()
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())

  runtime = BrowserRuntime()
  asyncio.run(runtime.start())

  assert [item["channel"] for item in launches] == ["chrome", "msedge"]
  asyncio.run(runtime.close())


def test_system_browser_launch_reports_when_chrome_and_edge_are_not_installed(monkeypatch):
  from core.browser_automation import errors
  class BrowserType:
    async def launch(self, **options):
      raise PlaywrightError(
        f"Chromium distribution '{options['channel']}' is not found at a private path"
      )
  class Driver:
    chromium = BrowserType()
    async def stop(self): pass
  class Starter:
    async def start(self): return Driver()
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())

  runtime = BrowserRuntime()
  try: asyncio.run(runtime.start())
  except Exception as exc:
    assert isinstance(exc, errors.SupportedBrowserNotInstalledError)
  else: raise AssertionError("missing supported browsers must have a dedicated error")


def test_system_browser_launch_does_not_misreport_other_chrome_failure(monkeypatch):
  launches = []
  class BrowserType:
    async def launch(self, **options):
      launches.append(options)
      raise PlaywrightError("Browser process exited because access was denied")
  class Driver:
    chromium = BrowserType()
    async def stop(self): pass
  class Starter:
    async def start(self): return Driver()
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())

  runtime = BrowserRuntime()
  try: asyncio.run(runtime.start())
  except BrowserAutomationError as exc:
    assert type(exc) is BrowserAutomationError
  else: raise AssertionError("startup failure must be wrapped")
  assert [item["channel"] for item in launches] == ["chrome"]


def test_frozen_runtime_uses_existing_user_browser_cache_during_launch(tmp_path, monkeypatch):
  cache = tmp_path / "ms-playwright"; cache.mkdir()
  observed = []
  class BrowserType:
    async def launch(self, *, headless, channel):
      observed.append(("launch", os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), headless, channel))
      return FakeBrowser()
  class Driver:
    chromium = BrowserType()
    async def stop(self): pass
  class Starter:
    async def start(self):
      observed.append(("start", os.environ.get("PLAYWRIGHT_BROWSERS_PATH")))
      return Driver()
  monkeypatch.setattr(sys, "frozen", True, raising=False)
  monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
  monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())

  runtime = BrowserRuntime()
  asyncio.run(runtime.start())

  assert observed == [("start", str(cache)), ("launch", str(cache), True, "chrome")]
  assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ
  asyncio.run(runtime.close())


def test_frozen_runtime_preserves_explicit_browser_path(tmp_path, monkeypatch):
  explicit = tmp_path / "managed-browsers"
  observed = []
  class BrowserType:
    async def launch(self, *, headless, channel):
      observed.append((os.environ["PLAYWRIGHT_BROWSERS_PATH"], channel))
      return FakeBrowser()
  class Driver:
    chromium = BrowserType()
    async def stop(self): pass
  class Starter:
    async def start(self): return Driver()
  monkeypatch.setattr(sys, "frozen", True, raising=False)
  monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
  monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(explicit))
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())

  runtime = BrowserRuntime()
  asyncio.run(runtime.start())

  assert observed == [(str(explicit), "chrome")]
  assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(explicit)
  asyncio.run(runtime.close())


def test_startup_failure_logs_safe_frozen_runtime_facts(tmp_path, monkeypatch):
  cache = tmp_path / "ms-playwright"; cache.mkdir()
  logs = []
  class Starter:
    async def start(self): raise RuntimeError("private filesystem detail")
  monkeypatch.setattr(sys, "frozen", True, raising=False)
  monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
  monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
  monkeypatch.setattr("playwright.async_api.async_playwright", lambda: Starter())
  monkeypatch.setattr(
    "core.browser_automation.runtime.smart_log",
    lambda message, *args, **kwargs: logs.append((message, kwargs)),
  )

  runtime = BrowserRuntime()
  try: asyncio.run(runtime.start())
  except BrowserAutomationError: pass
  else: raise AssertionError("startup failure must be wrapped")

  assert logs == [("Browser automation startup failed", {
    "domain": "support", "source": "BrowserRuntime", "level": "warning",
    "extra": {
      "frozen": True, "browser_type": "chromium", "browser_cache_configured": True,
      "browser_cache_exists": True, "error_type": "RuntimeError",
    },
  })]
  assert "private filesystem detail" not in repr(logs)
  assert str(tmp_path) not in repr(logs)
