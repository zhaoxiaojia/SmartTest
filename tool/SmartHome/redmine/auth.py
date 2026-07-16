from tool.SmartHome.redmine import selectors
from tool.SmartHome.redmine.models import AuthResult, AuthState, Credential


class RedmineAuthService:
    def __init__(self, session): self._session = session; self._page = None; self._username = ""

    async def login(self, credential: Credential) -> AuthResult:
        self._username = credential.username.strip()
        try:
            self._page = self._page or await self._session.new_page()
            await self._page.goto(selectors.LOGIN_URL)
            await self._page.fill(selectors.USERNAME, self._username)
            await self._page.fill(selectors.PASSWORD, credential.password)
            await self._page.click(selectors.LOGIN_SUBMIT)
            await self._wait_for_settled_page()
            return await self._classify()
        except Exception:
            return AuthResult(AuthState.FAILED, username=self._username, reason="login_failed")

    async def submit_verification(self, code: str) -> AuthResult:
        if self._page is None:
            return AuthResult(AuthState.FAILED, reason="verification_not_pending")
        try:
            await self._page.fill(selectors.TWOFA_CODE_INPUT, code)
            await self._page.click(selectors.TWOFA_SUBMIT)
            await self._wait_for_settled_page()
            return await self._classify(verification_submitted=True)
        except Exception:
            return AuthResult(AuthState.FAILED, username=self._username, reason="verification_failed")

    async def _wait_for_settled_page(self):
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            # Classification below uses the settled DOM contract and reports a
            # safe auth state even when the server does not emit a load event.
            pass

    async def _document_url(self):
        try:
            document_url = await self._page.evaluate("window.location.href")
            if isinstance(document_url, str) and document_url.strip():
                return document_url
        except Exception:
            pass
        page_url = getattr(self._page, "url", "")
        return page_url if isinstance(page_url, str) else ""

    async def _classify(self, *, verification_submitted=False):
        document_url = await self._document_url()
        if any([await self._page.is_visible(selector) for selector in selectors.INCORRECT_VERIFICATION_EVIDENCE]):
            return AuthResult(
                AuthState.VERIFICATION_REQUIRED,
                username=self._username,
                reason="incorrect_verification_code",
            )
        twofa_visible = any([await self._page.is_visible(selector) for selector in selectors.VERIFICATION_EVIDENCE])
        if selectors.TWOFA_PATH in document_url or twofa_visible:
            return AuthResult(
                AuthState.VERIFICATION_REQUIRED,
                username=self._username,
                reason="incorrect_verification_code" if verification_submitted else "verification_required",
            )
        if any([await self._page.is_visible(selector) for selector in selectors.CREDENTIAL_ERRORS]):
            return AuthResult(
                AuthState.CREDENTIALS_REQUIRED,
                username=self._username,
                reason="credentials_rejected",
            )
        if any([await self._page.is_visible(selector) for selector in selectors.AUTHENTICATED_EVIDENCE]):
            return AuthResult(AuthState.AUTHENTICATED, username=self._username)
        if document_url.startswith("https://support.amlogic.com/projects/"):
            return AuthResult(AuthState.AUTHENTICATED, username=self._username)
        return AuthResult(AuthState.FAILED, username=self._username, reason="unsupported_auth_state")

    async def close(self): await self._session.close()
