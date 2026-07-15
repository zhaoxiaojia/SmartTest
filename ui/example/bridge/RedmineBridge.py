from __future__ import annotations

import asyncio
from threading import Thread
from PySide6.QtCore import QObject, Property, Signal, Slot
from support.browser_automation import BrowserRuntime
from tool.SmartHome.redmine import AuthResult, AuthState, Credential, RedmineAuthService


class RedmineBridge(QObject):
    changed = Signal()
    credentialsRequired = Signal()
    verificationRequired = Signal()
    resultReady = Signal(object)

    def __init__(self, auth_bridge, *, runtime=None, service_factory=None, thread_factory=None):
        super().__init__(); self._auth = auth_bridge; self._runtime = runtime or BrowserRuntime()
        self._service_factory = service_factory; self._thread_factory = thread_factory or (lambda target: Thread(target=target, daemon=True).start())
        self._service = None; self._state = AuthState.IDLE; self._status = self.tr("Ready to sign in to Redmine."); self._account = ""
        self.resultReady.connect(self._apply)

    state = Property(str, lambda self: self._state.value, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    account = Property(str, lambda self: self._account, notify=changed)
    loading = Property(bool, lambda self: self._state is AuthState.SIGNING_IN, notify=changed)

    async def _service_for(self, account):
        if self._service is None:
            self._service = self._service_factory(account) if self._service_factory else RedmineAuthService(await self._runtime.context("amlogic_redmine", account))
        return self._service

    def _launch(self, operation):
        self._state = AuthState.SIGNING_IN; self._status = self.tr("Signing in to Redmine..."); self.changed.emit()
        def worker():
            try: result = asyncio.run(operation())
            except Exception: result = AuthResult(AuthState.FAILED, username=self._account)
            self.resultReady.emit(result)
        self._thread_factory(worker)

    def _apply(self, result):
        self._state = result.state; self._account = result.username or self._account
        self._status = {AuthState.AUTHENTICATED: self.tr("Redmine sign-in succeeded."), AuthState.CREDENTIALS_REQUIRED: self.tr("Redmine needs a different account or password."), AuthState.VERIFICATION_REQUIRED: self.tr("Enter the mobile verification code."), AuthState.FAILED: self.tr("Redmine sign-in failed.")}.get(result.state, result.message)
        self.changed.emit()
        if result.state is AuthState.CREDENTIALS_REQUIRED: self.credentialsRequired.emit()
        elif result.state is AuthState.VERIFICATION_REQUIRED: self.verificationRequired.emit()

    @Slot()
    def startLogin(self):
        username, password = self._auth.transientCredential(); self._account = username
        async def operation(): return await (await self._service_for(username)).login(Credential(username, password))
        self._launch(operation)

    @Slot(str, str)
    def submitCredentials(self, username, password):
        self._account = username.strip(); self._service = None
        async def operation(): return await (await self._service_for(self._account)).login(Credential(self._account, password))
        self._launch(operation)

    @Slot(str)
    def submitVerification(self, code):
        async def operation(): return await self._service.submit_verification(code)
        self._launch(operation)

    @Slot()
    def cancelLogin(self): self._state = AuthState.IDLE; self._status = self.tr("Redmine sign-in cancelled."); self.changed.emit()
