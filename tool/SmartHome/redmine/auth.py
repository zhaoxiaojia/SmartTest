import asyncio
import time
from contextlib import asynccontextmanager

from support.logging import smart_log
from tool.SmartHome.redmine import selectors
from tool.SmartHome.redmine.models import AuthResult, AuthState, Credential


class RedmineAuthService:
    def __init__(self, session):
        self._session = session
        self._page = None
        self._username = ""
        self._fast_auth_route_installed = False

    def _current_url(self):
        page_url = getattr(self._page, "url", "") if self._page is not None else ""
        return page_url if isinstance(page_url, str) else ""

    @property
    def page(self):
        return self._page

    @asynccontextmanager
    async def operation_page(self):
        page = await self._session.new_page()
        try:
            yield page
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def _document_url(self):
        try:
            document_url = await self._page.evaluate("window.location.href")
            if isinstance(document_url, str) and document_url.strip():
                return document_url
        except Exception:
            pass
        return self._current_url()

    async def _install_fast_auth_route(self):
        if self._fast_auth_route_installed or not hasattr(self._page, "route"):
            return

        async def route_handler(route):
            try:
                await route.abort()
            except Exception:
                pass

        try:
            await self._page.route("https://support.amlogic.com/assets/**", route_handler)
            self._fast_auth_route_installed = True
        except Exception:
            pass

    async def _remove_fast_auth_route(self):
        if not self._fast_auth_route_installed or not hasattr(self._page, "unroute"):
            return
        try:
            await self._page.unroute("https://support.amlogic.com/assets/**")
        except Exception:
            pass
        self._fast_auth_route_installed = False

    async def _visible(self, selector):
        try:
            return await self._page.is_visible(selector)
        except Exception:
            return False

    async def _any_visible(self, selectors_):
        for selector in selectors_:
            if await self._visible(selector):
                return True
        return False

    async def _login_form_visible(self):
        return all([
            await self._visible(selectors.USERNAME),
            await self._visible(selectors.PASSWORD),
            await self._visible(selectors.LOGIN_SUBMIT),
        ])

    async def _page_state(self):
        document_url = await self._document_url()
        if await self._any_visible(selectors.INCORRECT_VERIFICATION_EVIDENCE):
            return "verification_error"
        if selectors.TWOFA_PATH in document_url or await self._any_visible(selectors.VERIFICATION_EVIDENCE):
            return "twofa"
        if await self._any_visible(selectors.CREDENTIAL_ERRORS):
            return "credential_error"
        if (
            document_url.startswith("https://support.amlogic.com/projects/")
            or await self._any_visible(selectors.AUTHENTICATED_EVIDENCE)
        ):
            return "authenticated"
        if await self._login_form_visible():
            return "login_form"
        return "pending"

    async def _wait_for_state(self, states, *, timeout_ms, poll_interval=0.05):
        deadline = time.monotonic() + timeout_ms / 1000
        state = await self._page_state()
        while state not in states and time.monotonic() < deadline:
            await asyncio.sleep(poll_interval)
            state = await self._page_state()
        return state

    def _result_for_state(self, state, *, verification_submitted=False):
        if state == "authenticated":
            return AuthResult(AuthState.AUTHENTICATED, username=self._username)
        reasons = {
            "verification_error": (AuthState.VERIFICATION_REQUIRED, "incorrect_verification_code"),
            "twofa": (AuthState.VERIFICATION_REQUIRED, "incorrect_verification_code" if verification_submitted else "verification_required"),
            "credential_error": (AuthState.CREDENTIALS_REQUIRED, "credentials_rejected"),
        }
        auth_state, reason = reasons.get(state, (AuthState.FAILED, "unsupported_auth_state"))
        return AuthResult(auth_state, username=self._username, reason=reason)

    async def login(self, credential: Credential) -> AuthResult:
        self._username = credential.username.strip()
        try:
            self._page = self._page or await self._session.new_page()
            await self._install_fast_auth_route()

            await self._page.goto(selectors.LOGIN_URL, wait_until="commit", timeout=10000)

            state = await self._wait_for_state(
                {"login_form", "twofa", "authenticated"},
                timeout_ms=15000,
            )
            if state in {"twofa", "authenticated"}:
                result = self._result_for_state(state)
                if result.state is AuthState.AUTHENTICATED:
                    await self._remove_fast_auth_route()
                return result
            if state != "login_form":
                result = self._result_for_state(state)
                return result

            await self._page.fill(selectors.USERNAME, self._username)
            await self._page.fill(selectors.PASSWORD, credential.password)
            await self._page.click(selectors.LOGIN_SUBMIT)

            state = await self._wait_for_state(
                {"twofa", "authenticated", "credential_error"},
                timeout_ms=10000,
            )
            result = self._result_for_state(state)
            if result.state is AuthState.AUTHENTICATED:
                await self._remove_fast_auth_route()
            return result
        except Exception:
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
        if self._page is None:
            return AuthResult(AuthState.FAILED, reason="verification_not_pending")
        try:
            await self._page.fill(selectors.TWOFA_CODE_INPUT, code)
            await self._page.click(selectors.TWOFA_SUBMIT)

            state = await self._wait_for_state(
                {"authenticated", "verification_error"},
                timeout_ms=10000,
            )
            result = self._result_for_state(state, verification_submitted=True)
            if result.state is AuthState.AUTHENTICATED:
                await self._remove_fast_auth_route()
            return result
        except Exception:
            return AuthResult(AuthState.FAILED, username=self._username, reason="verification_failed")

    async def close(self):
        await self._remove_fast_auth_route()
        await self._session.close()
