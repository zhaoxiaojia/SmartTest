import asyncio
import time
from urllib.parse import urlsplit

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

    @staticmethod
    def _sanitized_url(document_url):
        parsed = urlsplit(document_url or "")
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path

    def _debug_evidence(self, phase, started_at, evidence):
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        smart_log(
            "[REDMINE_DEBUG] phase=%s elapsed_ms=%d account=%s url=%s "
            "login_form=%s twofa=%s auth=%s credential_error=%s verification_error=%s",
            phase,
            elapsed_ms,
            self._username or "<none>",
            self._sanitized_url(evidence["document_url"]),
            evidence["login_form"],
            evidence["twofa"],
            evidence["authenticated"],
            evidence["credential_error"],
            evidence["verification_error"],
            domain="tool",
            source="RedmineAuthService",
            extra={
                "phase": phase,
                "elapsed_ms": elapsed_ms,
                "account": self._username,
                "document_url": self._sanitized_url(evidence["document_url"]),
                **{key: value for key, value in evidence.items() if key != "document_url"},
            },
        )

    async def _inspect(self):
        document_url = await self._document_url()
        visible = {}
        all_selectors = (
            selectors.USERNAME,
            selectors.PASSWORD,
            selectors.LOGIN_SUBMIT,
            *selectors.INCORRECT_VERIFICATION_EVIDENCE,
            *selectors.VERIFICATION_EVIDENCE,
            *selectors.CREDENTIAL_ERRORS,
            *selectors.AUTHENTICATED_EVIDENCE,
        )
        for selector in dict.fromkeys(all_selectors):
            visible[selector] = await self._page.is_visible(selector)
        return {
            "document_url": document_url,
            "login_form": all(visible[item] for item in (
                selectors.USERNAME, selectors.PASSWORD, selectors.LOGIN_SUBMIT,
            )),
            "verification_error": any(visible[item] for item in selectors.INCORRECT_VERIFICATION_EVIDENCE),
            "twofa": selectors.TWOFA_PATH in document_url or any(
                visible[item] for item in selectors.VERIFICATION_EVIDENCE
            ),
            "credential_error": any(visible[item] for item in selectors.CREDENTIAL_ERRORS),
            "authenticated": any(visible[item] for item in selectors.AUTHENTICATED_EVIDENCE)
            or document_url.startswith("https://support.amlogic.com/projects/"),
        }

    async def _wait_for_auth_surface(self, *, timeout_ms=500):
        deadline = time.monotonic() + timeout_ms / 1000
        evidence = await self._inspect()
        while not self._is_explicit(evidence) and not evidence["login_form"] and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
            evidence = await self._inspect()
        return evidence

    @staticmethod
    def _is_explicit(evidence):
        return any(evidence[key] for key in (
            "verification_error", "twofa", "credential_error", "authenticated",
        ))

    async def login(self, credential: Credential) -> AuthResult:
        self._username = credential.username.strip()
        operation_started = time.monotonic()
        try:
            phase_started = time.monotonic()
            self._page = self._page or await self._session.new_page()
            self._trace("page_acquisition", phase_started)
            evidence = None
            initial = None
            for attempt in range(2):
                phase_started = time.monotonic()
                await self._page.goto(
                    selectors.LOGIN_URL,
                    wait_until="commit",
                    timeout=10000,
                )
                self._trace(f"goto_{attempt + 1}", phase_started)

                phase_started = time.monotonic()
                evidence = await self._inspect()
                initial = self._classify_evidence(evidence)
                self._debug_evidence(f"post_goto_{attempt + 1}", phase_started, evidence)
                if initial.state in {
                    AuthState.AUTHENTICATED,
                    AuthState.VERIFICATION_REQUIRED,
                    AuthState.CREDENTIALS_REQUIRED,
                }:
                    self._trace("result", operation_started, state=initial.state.value)
                    return initial
                if evidence["login_form"]:
                    break

                phase_started = time.monotonic()
                evidence = await self._wait_for_auth_surface()
                initial = self._classify_evidence(evidence)
                self._debug_evidence(f"poll_{attempt + 1}", phase_started, evidence)
                if initial.state in {
                    AuthState.AUTHENTICATED,
                    AuthState.VERIFICATION_REQUIRED,
                    AuthState.CREDENTIALS_REQUIRED,
                }:
                    self._trace("result", operation_started, state=initial.state.value)
                    return initial
                if evidence["login_form"]:
                    break
                if attempt == 0:
                    self._trace("retry_navigation", operation_started, state="transitional")

            if not evidence["login_form"]:
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
            result = await self._classify(phase="post_submit")
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
            result = await self._classify(verification_submitted=True, phase="post_verification")
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

    def _classify_evidence(self, evidence, *, verification_submitted=False):
        if evidence["verification_error"]:
            return AuthResult(
                AuthState.VERIFICATION_REQUIRED,
                username=self._username,
                reason="incorrect_verification_code",
            )
        if evidence["twofa"]:
            return AuthResult(
                AuthState.VERIFICATION_REQUIRED,
                username=self._username,
                reason="incorrect_verification_code" if verification_submitted else "verification_required",
            )
        if evidence["credential_error"]:
            return AuthResult(
                AuthState.CREDENTIALS_REQUIRED,
                username=self._username,
                reason="credentials_rejected",
            )
        if evidence["authenticated"]:
            return AuthResult(AuthState.AUTHENTICATED, username=self._username)
        return AuthResult(AuthState.FAILED, username=self._username, reason="unsupported_auth_state")

    async def _classify(self, *, verification_submitted=False, phase="classify"):
        started_at = time.monotonic()
        evidence = await self._inspect()
        self._debug_evidence(phase, started_at, evidence)
        return self._classify_evidence(evidence, verification_submitted=verification_submitted)

    async def close(self): await self._session.close()
