import time

from support.logging import smart_log
from tool.SmartHome.redmine import selectors
from tool.SmartHome.redmine.models import AuthResult, AuthState, Credential


class RedmineAuthService:
    def __init__(self, session): self._session = session; self._page = None; self._username = ""

    def _trace(self, phase, started_at, *, state=""):
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        smart_log(
            "Redmine auth phase=%s elapsed_ms=%d account=%s state=%s",
            phase,
            elapsed_ms,
            self._username or "<none>",
            state or "pending",
            domain="tool",
            source="RedmineAuthService",
            extra={
                "phase": phase,
                "elapsed_ms": elapsed_ms,
                "account": self._username,
                "state": state or "pending",
            },
        )

    async def _login_form_visible(self):
        for selector in (selectors.USERNAME, selectors.PASSWORD, selectors.LOGIN_SUBMIT):
            if not await self._page.is_visible(selector):
                return False
        return True

    async def login(self, credential: Credential) -> AuthResult:
        self._username = credential.username.strip()
        operation_started = time.monotonic()
        try:
            phase_started = time.monotonic()
            self._page = self._page or await self._session.new_page()
            self._trace("page_acquisition", phase_started)
            phase_started = time.monotonic()
            await self._page.goto(
                selectors.LOGIN_URL,
                wait_until="commit",
                timeout=10000,
            )
            self._trace("goto", phase_started)

            phase_started = time.monotonic()
            initial = await self._classify()
            self._trace("classify", phase_started, state=initial.state.value)
            if initial.state in {
                AuthState.AUTHENTICATED,
                AuthState.VERIFICATION_REQUIRED,
                AuthState.CREDENTIALS_REQUIRED,
            }:
                self._trace("result", operation_started, state=initial.state.value)
                return initial
            if not await self._login_form_visible():
                phase_started = time.monotonic()
                await self._wait_for_settled_page(timeout=3000)
                self._trace("settle", phase_started)
                phase_started = time.monotonic()
                initial = await self._classify()
                self._trace("classify", phase_started, state=initial.state.value)
                if initial.state in {
                    AuthState.AUTHENTICATED,
                    AuthState.VERIFICATION_REQUIRED,
                    AuthState.CREDENTIALS_REQUIRED,
                }:
                    self._trace("result", operation_started, state=initial.state.value)
                    return initial
                if not await self._login_form_visible():
                    self._trace("result", operation_started, state=initial.state.value)
                    return initial

            phase_started = time.monotonic()
            await self._page.fill(selectors.USERNAME, self._username)
            await self._page.fill(selectors.PASSWORD, credential.password)
            await self._page.click(selectors.LOGIN_SUBMIT)
            self._trace("form_submit", phase_started)
            phase_started = time.monotonic()
            await self._wait_for_settled_page()
            self._trace("settle", phase_started)
            phase_started = time.monotonic()
            result = await self._classify()
            self._trace("classify", phase_started, state=result.state.value)
            self._trace("result", operation_started, state=result.state.value)
            return result
        except Exception:
            self._trace("result", operation_started, state=AuthState.FAILED.value)
            smart_log(
                "Redmine auth login failed (account=%s)",
                self._username or "<none>",
                domain="tool",
                source="RedmineAuthService",
                level="warning",
                exc_info=True,
            )
            return AuthResult(AuthState.FAILED, username=self._username, reason="login_failed")

    async def submit_verification(self, code: str) -> AuthResult:
        operation_started = time.monotonic()
        if self._page is None:
            return AuthResult(AuthState.FAILED, reason="verification_not_pending")
        try:
            phase_started = time.monotonic()
            await self._page.fill(selectors.TWOFA_CODE_INPUT, code)
            await self._page.click(selectors.TWOFA_SUBMIT)
            self._trace("verification_submit", phase_started)
            phase_started = time.monotonic()
            await self._wait_for_settled_page()
            self._trace("settle", phase_started)
            phase_started = time.monotonic()
            result = await self._classify(verification_submitted=True)
            self._trace("classify", phase_started, state=result.state.value)
            self._trace("result", operation_started, state=result.state.value)
            return result
        except Exception:
            self._trace("result", operation_started, state=AuthState.FAILED.value)
            return AuthResult(AuthState.FAILED, username=self._username, reason="verification_failed")

    async def _wait_for_settled_page(self, *, timeout=15000):
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=timeout)
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
