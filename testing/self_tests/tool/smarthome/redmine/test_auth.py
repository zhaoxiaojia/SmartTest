import asyncio
import pytest

from tool.SmartHome.redmine.auth import RedmineAuthService
from tool.SmartHome.redmine.models import AuthState, Credential


class FakePage:
    def __init__(self, outcome): self.outcome = outcome; self.url = "https://support.amlogic.com/login"; self.values = {}
    async def goto(self, _url): pass
    async def fill(self, selector, value): self.values[selector] = value
    async def click(self, _selector):
        if self.outcome == "success": self.url = "https://support.amlogic.com/projects"
        elif self.outcome == "verify": self.url = "https://support.amlogic.com/verification"
    async def is_visible(self, selector):
        return (self.outcome == "error" and selector == ".flash.error") or (self.outcome == "verify" and selector == "input[name='verification_code']")


class FakeSession:
    def __init__(self, page): self.page = page; self.closed = False
    async def new_page(self): return self.page
    async def close(self): self.closed = True


@pytest.mark.parametrize("outcome,state", [("success", AuthState.AUTHENTICATED), ("error", AuthState.CREDENTIALS_REQUIRED), ("verify", AuthState.VERIFICATION_REQUIRED), ("unknown", AuthState.FAILED)])
def test_login_classifies_only_explicit_evidence(outcome, state):
    async def scenario():
        service = RedmineAuthService(FakeSession(FakePage(outcome)))
        result = await service.login(Credential("alice", "secret"))
        assert result.state is state and "secret" not in result.message
    asyncio.run(scenario())


def test_verification_submission_never_returns_code():
    async def scenario():
        page = FakePage("verify"); service = RedmineAuthService(FakeSession(page))
        await service.login(Credential("alice", "secret"))
        page.outcome = "success"
        result = await service.submit_verification("123456")
        assert result.state is AuthState.AUTHENTICATED and "123456" not in result.message
    asyncio.run(scenario())
