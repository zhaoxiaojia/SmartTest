import asyncio

from support.browser_automation import BrowserRuntime
from support.browser_automation.errors import BrowserAutomationError


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
