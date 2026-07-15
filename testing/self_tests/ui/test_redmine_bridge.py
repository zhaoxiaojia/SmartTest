import asyncio
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Signal

from tool.SmartHome.redmine.models import AuthResult, AuthState
from ui.example.bridge.RedmineBridge import RedmineBridge, _AsyncLoopWorker
from ui.example.bridge.ToolBridge import build_tool_groups


class FakeAuth(QObject):
    authChanged = Signal()
    username = "alice"
    def transientCredential(self): return ("alice", "ldap-secret")


class FakeService:
    def __init__(self, result): self.result = result; self.credential = None
    async def login(self, credential): self.credential = credential; return self.result
    async def close(self): pass


class LoopRecordingService(FakeService):
    def __init__(self): super().__init__(AuthResult(AuthState.VERIFICATION_REQUIRED)); self.loops = []; self.closed = False
    async def login(self, credential): self.loops.append(asyncio.get_running_loop()); return await super().login(credential)
    async def submit_verification(self, _code): self.loops.append(asyncio.get_running_loop()); return AuthResult(AuthState.AUTHENTICATED)
    async def close(self): self.loops.append(asyncio.get_running_loop()); self.closed = True


def wait_for(predicate):
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert predicate()


def test_bridge_uses_transient_ldap_and_routes_only_explicit_prompt():
    service = FakeService(AuthResult(AuthState.CREDENTIALS_REQUIRED))
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service)
    credentials = []; verification = []
    bridge.credentialsRequired.connect(lambda: credentials.append(1))
    bridge.verificationRequired.connect(lambda: verification.append(1))
    bridge.startLogin()
    wait_for(lambda: bool(credentials))
    assert service.credential.password == "ldap-secret"
    assert credentials == [1] and verification == []
    bridge.close()


def test_smarthome_catalog_contains_redmine():
    personnel = {"employees": [{"account": "alice", "assignments": [{"product_line_id": "SmartHome"}]}], "product_lines": [{"id": "SmartHome", "active": True}]}
    smart_home = next(group for group in build_tool_groups(personnel, "alice") if group["id"] == "SmartHome")
    assert [tool["id"] for tool in smart_home["tools"]] == ["redmine"]


def test_all_operations_and_shutdown_use_one_owned_loop():
    service = LoopRecordingService(); bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service)
    verification = []; bridge.verificationRequired.connect(lambda: verification.append(1))
    bridge.startLogin(); wait_for(lambda: bool(verification))
    bridge.submitVerification("123456"); wait_for(lambda: bridge.state == "authenticated")
    bridge.close()
    assert service.closed and len({id(loop) for loop in service.loops}) == 1


def test_cancel_invalidates_late_completion_and_prompts():
    class SlowService(FakeService):
        async def login(self, credential):
            self.credential = credential
            await asyncio.sleep(10)
            return AuthResult(AuthState.CREDENTIALS_REQUIRED)
    service = SlowService(AuthResult(AuthState.CREDENTIALS_REQUIRED)); bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service)
    prompts = []; bridge.credentialsRequired.connect(lambda: prompts.append(1))
    bridge.startLogin(); bridge.cancelLogin(); time.sleep(0.05); (QCoreApplication.instance() or QCoreApplication([])).processEvents()
    assert bridge.state == "idle" and prompts == []
    bridge.close()


def test_qml_clears_transient_password_and_verification_inputs():
    source = Path("ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")
    assert source.count("clearSecret()") >= 6
    assert "RedmineBridge.password" not in source and "RedmineBridge.code" not in source


def test_worker_does_not_close_loop_while_thread_is_still_alive():
    class ThreadStillRunning:
        def join(self, timeout): self.timeout = timeout
        def is_alive(self): return True
    class RecordingLoop:
        def __init__(self): self.closed = False
        def call_soon_threadsafe(self, callback): self.callback = callback
        def stop(self): pass
        def is_closed(self): return False
        def close(self): self.closed = True
    worker = _AsyncLoopWorker.__new__(_AsyncLoopWorker)
    worker.loop = RecordingLoop(); worker._thread = ThreadStillRunning()
    assert worker.stop(timeout=0.01) is False
    assert worker.loop.closed is False
