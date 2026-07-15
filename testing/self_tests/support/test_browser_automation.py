import asyncio

from support.browser_automation import BrowserRuntime


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
    await runtime.close()
    assert browser.closed and browser.contexts[1].closed
  asyncio.run(scenario())
