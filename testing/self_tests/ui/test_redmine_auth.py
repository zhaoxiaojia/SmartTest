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
    class TwoFaAfterSubmitPage(FakePage):
        async def goto(self, url, **kwargs):
            await super().goto(url, **kwargs)
            self.visible = {selectors.USERNAME, selectors.PASSWORD, selectors.LOGIN_SUBMIT}

        async def click(self, selector):
            await super().click(selector)
            if selector == selectors.LOGIN_SUBMIT:
                self.document_url = "https://support.amlogic.com/account/twofa/confirm"
                self.visible = {selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT}

    page = TwoFaAfterSubmitPage()
    service = RedmineAuthService(FakeSession(page))

    result = run(service.login(Credential("alice", "secret")))

    assert result.state is AuthState.VERIFICATION_REQUIRED
    assert result.reason == "verification_required"
    assert page.load_waits == 0
    assert page.goto_options == {"wait_until": "commit", "timeout": 10000}


def test_cached_authenticated_redirect_skips_missing_login_form_without_timeout():
    class AuthenticatedRedirectPage(FakePage):
        async def goto(self, url, **kwargs):
            await super().goto(url, **kwargs)
            self.document_url = "https://support.amlogic.com/projects/smarthome/issues"
            self.visible = {selectors.AUTHENTICATED_PROJECT_LINK}

    page = AuthenticatedRedirectPage()

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.AUTHENTICATED
    assert page.fills == []
    assert page.clicks == []
    assert page.load_waits == 0


def test_missing_login_surface_fails_without_filling_credentials():
    page = FakePage(document_url=selectors.LOGIN_URL)

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.FAILED
    assert result.reason == "unsupported_auth_state"
    assert page.fills == []
    assert page.clicks == []


def test_delayed_login_form_on_one_navigation_reaches_twofa_without_failure():
    class TransitionalPage(FakePage):
        def __init__(self):
            super().__init__(document_url=selectors.LOGIN_URL)
            self.goto_count = 0
            self.inspection_count = 0

        async def goto(self, url, **kwargs):
            await super().goto(url, **kwargs)
            self.goto_count += 1

        async def evaluate(self, expression):
            self.inspection_count += 1
            if self.inspection_count == 4:
                self.visible = {selectors.USERNAME, selectors.PASSWORD, selectors.LOGIN_SUBMIT}
            return await super().evaluate(expression)

        async def click(self, selector):
            await super().click(selector)
            if selector == selectors.LOGIN_SUBMIT:
                self.document_url = "https://support.amlogic.com/account/twofa/confirm"
                self.visible = {selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT}

    page = TransitionalPage()

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert page.goto_count == 1
    assert page.fills == [
        (selectors.USERNAME, "alice"),
        (selectors.PASSWORD, "secret"),
    ]
    assert page.clicks == [selectors.LOGIN_SUBMIT]
    assert result.state is AuthState.VERIFICATION_REQUIRED
    assert result.reason == "verification_required"


def test_twofa_evidence_survives_empty_document_url_adapter_result():
    class EmptyDocumentUrlPage(FakePage):
        async def evaluate(self, _expression): return None
        async def goto(self, url, **kwargs):
            await super().goto(url, **kwargs)
            self.visible = {selectors.USERNAME, selectors.PASSWORD, selectors.LOGIN_SUBMIT}
        async def click(self, selector):
            await super().click(selector)
            if selector == selectors.LOGIN_SUBMIT:
                self.visible = {selectors.TWOFA_CODE_INPUT, selectors.TWOFA_SUBMIT}

    page = EmptyDocumentUrlPage()

    result = run(RedmineAuthService(FakeSession(page)).login(Credential("alice", "secret")))

    assert result.state is AuthState.VERIFICATION_REQUIRED


def test_verification_uses_unique_real_twofa_fields_and_same_form_is_rejected_code():
    class RejectedVerificationPage(FakePage):
        async def click(self, selector):
            await super().click(selector)
            if selector == selectors.TWOFA_SUBMIT:
                self.visible = set(selectors.INCORRECT_VERIFICATION_EVIDENCE)

    page = RejectedVerificationPage(url="https://support.amlogic.com/account/twofa/confirm")
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
