import asyncio
import pytest
from pathlib import Path

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
        return ((self.outcome == "success" and selector == "a.logout")
                or (self.outcome == "error" and "Invalid user or password" in selector)
                or (self.outcome == "incorrect_otp" and "verification code" in selector)
                or (self.outcome in {"verify", "incorrect_otp"} and selector == "input[name='verification_code']"))


class FakeSession:
    def __init__(self, page): self.page = page; self.closed = False
    async def new_page(self): return self.page
    async def close(self): self.closed = True


@pytest.mark.parametrize("outcome,state", [("success", AuthState.AUTHENTICATED), ("error", AuthState.CREDENTIALS_REQUIRED), ("verify", AuthState.VERIFICATION_REQUIRED), ("unknown", AuthState.FAILED)])
def test_login_classifies_only_explicit_evidence(outcome, state):
    async def scenario():
        service = RedmineAuthService(FakeSession(FakePage(outcome)))
        result = await service.login(Credential("alice", "secret"))
        assert result.state is state and result.message == "" and "secret" not in repr(result)
    asyncio.run(scenario())


def test_url_change_or_generic_error_is_not_authentication_or_credential_failure():
    async def scenario():
        page = FakePage("unknown"); page.url = "https://support.amlogic.com/projects"
        result = await RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret"))
        assert result.state is AuthState.FAILED
    asyncio.run(scenario())


def test_verification_submission_never_returns_code():
    async def scenario():
        page = FakePage("verify"); service = RedmineAuthService(FakeSession(page))
        await service.login(Credential("alice", "secret"))
        page.outcome = "success"
        result = await service.submit_verification("123456")
        assert result.state is AuthState.AUTHENTICATED and "123456" not in result.message
    asyncio.run(scenario())


def test_incorrect_verification_code_stays_in_verification_without_secret_echo():
    async def scenario():
        page = FakePage("verify"); service = RedmineAuthService(FakeSession(page))
        initial = await service.login(Credential("alice", "secret"))
        page.outcome = "incorrect_otp"
        rejected = await service.submit_verification("654321")
        assert initial.state is AuthState.VERIFICATION_REQUIRED
        assert initial.reason == "verification_required" and initial.message == ""
        assert rejected.state is AuthState.VERIFICATION_REQUIRED
        assert rejected.reason == "incorrect_verification_code"
        assert rejected.message == "" and "654321" not in repr(rejected)
    asyncio.run(scenario())


def test_auth_service_contains_no_smarttest_authored_ui_sentences():
    source = Path("tool/SmartHome/redmine/auth.py").read_text(encoding="utf-8")
    forbidden = {
        "Mobile verification is required.",
        "Redmine rejected the account or password.",
        "Redmine sign-in failed unexpectedly.",
        "Verification failed unexpectedly.",
        "Redmine returned an unsupported sign-in state.",
        "No verification is pending.",
    }
    assert all(text not in source for text in forbidden)
