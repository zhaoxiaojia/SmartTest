import asyncio

from tool.SmartHome.redmine.auth import RedmineAuthService
from tool.SmartHome.redmine.models import AuthState, Credential
from tool.SmartHome.redmine import selectors


class FakeSession:
    def __init__(self, page): self.page = page
    async def new_page(self): return self.page
    async def close(self): pass


class FakePage:
    def __init__(self, *, url=selectors.LOGIN_URL, document_url=None, visible=(), post_login_url=None):
        self.url = url
        self.document_url = document_url
        self.post_login_url = post_login_url
        self.visible = set(visible)
        self.fills = []
        self.clicks = []
        self.load_waits = 0
        self.goto_options = {}

    async def goto(self, url, **kwargs): self.url = url; self.goto_options = kwargs
    async def fill(self, selector, value): self.fills.append((selector, value))
    async def click(self, selector):
        self.clicks.append(selector)
        if selector == selectors.LOGIN_SUBMIT and self.post_login_url:
            self.url = self.post_login_url
    async def is_visible(self, selector): return selector in self.visible
    async def wait_for_load_state(self, _state, timeout=None): self.load_waits += 1
    async def evaluate(self, _expression): return self.document_url or self.url


def run(coroutine): return asyncio.run(coroutine)


def test_login_maps_real_twofa_contract_to_verification_required():
    page = FakePage(
        post_login_url="https://support.amlogic.com/account/twofa/confirm",
        visible=(selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT),
    )
    service = RedmineAuthService(FakeSession(page))

    result = run(service.login(Credential("alice", "secret")))

    assert result.state is AuthState.VERIFICATION_REQUIRED
    assert result.reason == "verification_required"
    assert page.load_waits == 0
    assert page.goto_options == {"wait_until": "commit", "timeout": 10000}


def test_cached_authenticated_redirect_skips_missing_login_form_without_timeout():
    page = FakePage(
        document_url="https://support.amlogic.com/projects/smarthome/issues",
        visible=(selectors.AUTHENTICATED_PROJECT_LINK,),
    )

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.AUTHENTICATED
    assert page.fills == []
    assert page.clicks == []
    assert page.load_waits == 0


def test_explicit_login_form_is_required_before_credentials_are_filled():
    page = FakePage(document_url=selectors.LOGIN_URL)

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.FAILED
    assert result.reason == "unsupported_auth_state"
    assert page.fills == []
    assert page.clicks == []


def test_transitional_first_navigation_retries_internally_and_reaches_twofa():
    class TransitionalPage(FakePage):
        def __init__(self):
            super().__init__(document_url=selectors.LOGIN_URL)
            self.goto_count = 0

        async def goto(self, url, **kwargs):
            await super().goto(url, **kwargs)
            self.goto_count += 1
            if self.goto_count == 2:
                self.visible = {selectors.USERNAME, selectors.PASSWORD, selectors.LOGIN_SUBMIT}

        async def click(self, selector):
            await super().click(selector)
            if selector == selectors.LOGIN_SUBMIT:
                self.document_url = "https://support.amlogic.com/account/twofa/confirm"
                self.visible = {selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT}

    page = TransitionalPage()

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert page.goto_count == 2
    assert page.fills == [
        (selectors.USERNAME, "alice"),
        (selectors.PASSWORD, "secret"),
    ]
    assert page.clicks == [selectors.LOGIN_SUBMIT]
    assert result.state is AuthState.VERIFICATION_REQUIRED
    assert result.reason == "verification_required"


def test_auth_timing_logs_contain_phases_and_account_but_not_secrets(monkeypatch):
    messages = []
    monkeypatch.setattr(
        "tool.SmartHome.redmine.auth.smart_log",
        lambda message, *args, **kwargs: messages.append(message % args if args else message),
    )
    page = FakePage(
        document_url="https://support.amlogic.com/projects/smarthome/issues?token=private-value",
        visible=(selectors.AUTHENTICATED_PROJECT_LINK,),
    )

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.AUTHENTICATED
    assert any("phase=goto" in message and "account=alice" in message for message in messages)
    assert any("phase=post_goto_1" in message and "auth=True" in message for message in messages)
    assert any("phase=result" in message and "elapsed_ms=" in message for message in messages)
    assert not any("secret" in message for message in messages)
    assert not any("private-value" in message for message in messages)
    assert any("[REDMINE_DEBUG]" in message for message in messages)


def test_twofa_evidence_survives_empty_document_url_adapter_result():
    class EmptyDocumentUrlPage(FakePage):
        async def evaluate(self, _expression): return None

    page = EmptyDocumentUrlPage(
        post_login_url="https://support.amlogic.com/account/twofa/confirm",
        visible=(selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT),
    )

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.VERIFICATION_REQUIRED


def test_verification_uses_unique_real_twofa_fields_and_same_form_is_rejected_code():
    page = FakePage(
        url="https://support.amlogic.com/account/twofa/confirm",
        visible=(selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT),
    )
    service = RedmineAuthService(FakeSession(page))
    service._page = page
    service._username = "alice"

    result = run(service.submit_verification("123456"))

    assert page.fills == [(selectors.TWOFA_CODE_INPUT, "123456")]
    assert page.clicks == [selectors.TWOFA_SUBMIT]
    assert result.state is AuthState.VERIFICATION_REQUIRED
    assert result.reason == "incorrect_verification_code"


def test_verification_maps_settled_project_landing_to_authenticated():
    page = FakePage(
        url="https://support.amlogic.com/account/twofa/confirm",
        document_url="https://support.amlogic.com/projects/example",
        visible=(selectors.AUTHENTICATED_PROJECT_LINK,),
    )
    service = RedmineAuthService(FakeSession(page))
    service._page = page
    service._username = "alice"

    result = run(service.submit_verification("123456"))

    assert result.state is AuthState.AUTHENTICATED
