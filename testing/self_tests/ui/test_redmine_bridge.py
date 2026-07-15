import asyncio

from PySide6.QtCore import QObject, Signal

from tool.SmartHome.redmine.models import AuthResult, AuthState
from ui.example.bridge.RedmineBridge import RedmineBridge
from ui.example.bridge.ToolBridge import build_tool_groups


class FakeAuth(QObject):
    authChanged = Signal()
    username = "alice"
    def transientCredential(self): return ("alice", "ldap-secret")


class FakeService:
    def __init__(self, result): self.result = result; self.credential = None
    async def login(self, credential): self.credential = credential; return self.result


def test_bridge_uses_transient_ldap_and_routes_only_explicit_prompt():
    service = FakeService(AuthResult(AuthState.CREDENTIALS_REQUIRED))
    bridge = RedmineBridge(FakeAuth(), service_factory=lambda _account: service, thread_factory=lambda target: target())
    credentials = []; verification = []
    bridge.credentialsRequired.connect(lambda: credentials.append(1))
    bridge.verificationRequired.connect(lambda: verification.append(1))
    bridge.startLogin()
    assert service.credential.password == "ldap-secret"
    assert credentials == [1] and verification == []


def test_smarthome_catalog_contains_redmine():
    personnel = {"employees": [{"account": "alice", "assignments": [{"product_line_id": "SmartHome"}]}], "product_lines": [{"id": "SmartHome", "active": True}]}
    smart_home = next(group for group in build_tool_groups(personnel, "alice") if group["id"] == "SmartHome")
    assert [tool["id"] for tool in smart_home["tools"]] == ["redmine"]
