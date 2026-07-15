from __future__ import annotations

import asyncio
from concurrent.futures import Future
from threading import Event, Thread

from PySide6.QtCore import QObject, Property, Signal, Slot

from support.browser_automation import BrowserRuntime
from tool.SmartHome.redmine import AuthResult, AuthState, Credential, RedmineAuthService


class _AsyncLoopWorker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._ready = Event()
        self._thread = Thread(target=self._run, name="redmine-browser", daemon=True)
        self._thread.start()
        self._ready.wait()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        self.loop.run_forever()

    def submit(self, coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def stop(self, timeout=5):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            return False
        if not self.loop.is_closed():
            self.loop.close()
        return True


class RedmineBridge(QObject):
    changed = Signal()
    credentialsRequired = Signal()
    verificationRequired = Signal()
    resultReady = Signal(int, object)

    def __init__(self, auth_bridge, *, runtime=None, service_factory=None, worker=None):
        super().__init__()
        self._auth = auth_bridge
        self._runtime = runtime or BrowserRuntime()
        self._service_factory = service_factory
        self._worker = worker or _AsyncLoopWorker()
        self._service = None
        self._future = None
        self._generation = 0
        self._closed = False
        self._state = AuthState.IDLE
        self._status = self.tr("Ready to sign in to Redmine.")
        self._account = ""
        self.resultReady.connect(self._apply)

    state = Property(str, lambda self: self._state.value, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    account = Property(str, lambda self: self._account, notify=changed)
    loading = Property(bool, lambda self: self._state is AuthState.SIGNING_IN, notify=changed)

    async def _service_for(self, account):
        if self._service is None:
            self._service = self._service_factory(account) if self._service_factory else RedmineAuthService(
                await self._runtime.context("amlogic_redmine", account)
            )
        return self._service

    def _launch(self, operation):
        if self._closed or self._state is AuthState.SIGNING_IN:
            return
        self._generation += 1
        generation = self._generation
        self._state = AuthState.SIGNING_IN
        self._status = self.tr("Signing in to Redmine...")
        self.changed.emit()
        self._future = self._worker.submit(operation())

        def finished(future):
            try:
                result = future.result()
            except Exception:
                result = AuthResult(AuthState.FAILED, username=self._account)
            self.resultReady.emit(generation, result)

        self._future.add_done_callback(finished)

    @Slot(int, object)
    def _apply(self, generation, result):
        if self._closed or generation != self._generation:
            return
        self._future = None
        self._state = result.state
        self._account = result.username or self._account
        self._status = {
            AuthState.AUTHENTICATED: self.tr("Redmine sign-in succeeded."),
            AuthState.CREDENTIALS_REQUIRED: self.tr("Redmine needs a different account or password."),
            AuthState.VERIFICATION_REQUIRED: result.message or self.tr("Enter the mobile verification code."),
            AuthState.FAILED: self.tr("Redmine sign-in failed."),
        }.get(result.state, result.message)
        self.changed.emit()
        if result.state is AuthState.CREDENTIALS_REQUIRED:
            self.credentialsRequired.emit()
        elif result.state is AuthState.VERIFICATION_REQUIRED:
            self.verificationRequired.emit()

    @Slot()
    def startLogin(self):
        username, password = self._auth.transientCredential()
        self._account = username

        async def operation():
            return await (await self._service_for(username)).login(Credential(username, password))

        self._launch(operation)

    @Slot(str, str)
    def submitCredentials(self, username, password):
        self._account = username.strip()
        self._service = None

        async def operation():
            return await (await self._service_for(self._account)).login(Credential(self._account, password))

        self._launch(operation)

    @Slot(str)
    def submitVerification(self, code):
        async def operation():
            return await self._service.submit_verification(code)

        self._launch(operation)

    async def _close_flow(self):
        service, self._service = self._service, None
        if service is not None:
            try:
                await service.close()
            except Exception:
                pass
        await self._runtime.close()

    @Slot()
    def cancelLogin(self):
        self._generation += 1
        if self._future is not None:
            self._future.cancel()
            self._future = None
        self._worker.submit(self._close_flow())
        self._state = AuthState.IDLE
        self._status = self.tr("Redmine sign-in cancelled.")
        self.changed.emit()

    @Slot()
    def close(self):
        if self._closed:
            return
        self._closed = True
        self._generation += 1
        if self._future is not None:
            self._future.cancel()
        try:
            self._worker.submit(self._close_flow()).result(timeout=10)
        finally:
            self._worker.stop()
