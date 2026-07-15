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
            return await self._classify()
        except Exception:
            return AuthResult(AuthState.FAILED, username=self._username, reason="login_failed")

    async def submit_verification(self, code: str) -> AuthResult:
        if self._page is None:
            return AuthResult(AuthState.FAILED, reason="verification_not_pending")
        try:
            target = selectors.VERIFICATION_INPUT
            for selector in selectors.VERIFICATION_EVIDENCE:
                if await self._page.is_visible(selector):
                    target = selector
                    break
            await self._page.fill(target, code)
            await self._page.click(selectors.VERIFICATION_SUBMIT)
            return await self._classify()
        except Exception:
            return AuthResult(AuthState.FAILED, username=self._username, reason="verification_failed")

    async def _classify(self):
        if any([await self._page.is_visible(selector) for selector in selectors.AUTHENTICATED_EVIDENCE]):
            return AuthResult(AuthState.AUTHENTICATED, username=self._username)
        if any([await self._page.is_visible(selector) for selector in selectors.INCORRECT_VERIFICATION_EVIDENCE]):
            return AuthResult(
                AuthState.VERIFICATION_REQUIRED,
                username=self._username,
                reason="incorrect_verification_code",
            )
        if any([await self._page.is_visible(selector) for selector in selectors.VERIFICATION_EVIDENCE]):
            return AuthResult(
                AuthState.VERIFICATION_REQUIRED,
                username=self._username,
                reason="verification_required",
            )
        if any([await self._page.is_visible(selector) for selector in selectors.CREDENTIAL_ERRORS]):
            return AuthResult(
                AuthState.CREDENTIALS_REQUIRED,
                username=self._username,
                reason="credentials_rejected",
            )
        return AuthResult(AuthState.FAILED, username=self._username, reason="unsupported_auth_state")

    async def close(self): await self._session.close()
