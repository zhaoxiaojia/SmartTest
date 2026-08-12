import json
import importlib
import sys
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from threading import Event
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PERSONNEL_PATH = ROOT / "config" / "personnel.json"
ITEMS_FOOTER_PATH = ROOT / "ui" / "example" / "imports" / "example" / "qml" / "global" / "ItemsFooter.qml"
LOGIN_WINDOW_PATH = ROOT / "ui" / "example" / "imports" / "example" / "qml" / "window" / "LoginWindow.qml"
NAVIGATION_VIEW_PATH = ROOT / "ui" / "FluentUI" / "imports" / "FluentUI" / "Controls" / "FluNavigationView.qml"
sys.path.insert(0, str(ROOT / "ui"))

from example.bridge.AuthBridge import (  # noqa: E402
    AuthBridge,
    initials_from_name,
    ldap_identity_from_attributes,
    load_personnel,
    match_employee_profile,
)
from example.bridge.auth_accounts import AuthAccountStore, account_id_for_username  # noqa: E402
from example.context_registry import start_context_services  # noqa: E402
from support.windows_credentials import WindowsCredentialError  # noqa: E402

AUTH_MODULE = importlib.import_module("example.bridge.AuthBridge")
from example.bridge.ToolBridge import amlogic_employees  # noqa: E402


def _employees_by_name():
    payload = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))
    return {employee["display_name"]: employee for employee in amlogic_employees(payload)}


def test_personnel_reporting_relationships_and_required_grades():
    employees = _employees_by_name()
    accounts = [employee["account"] for employee in employees.values()]
    assert all(accounts)
    assert len(accounts) == len(set(accounts))
    for employee in employees.values():
        assert employee["account"] == ".".join(employee["display_name"].lower().split())
        assert "email" not in employee
    assert employees["Chao Li"]["account"] == "chao.li"
    assert employees["Chen Chen"]["employment"]["job_title_override"] == "Product Line Lead"
    chen_reports = {
        "Kang Jiang": "I3",
        "Weiting Feng": "I3",
        "Zhuhui Zhang": "I2",
        "Taoqing Miao": "I2",
        "Nannan Meng": "I3",
    }

    for name, grade in chen_reports.items():
        assert employees[name]["employment"]["grade"] == grade
        assert employees[name]["reports_to"] == "Chen Chen"

    for employee in employees.values():
        assert isinstance(employee["reports_to"], str)
        if employee["employment"]["grade"] in {"M3", "M4"}:
            assert employee["reports_to"] == "Xiuyue Zhang"


def test_profile_matches_trimmed_ldap_display_name_exactly():
    personnel = load_personnel(PERSONNEL_PATH)

    profile = match_employee_profile(personnel, "  Kang Jiang  ")

    assert profile["display_name"] == "Kang Jiang"
    assert profile["grade"] == "I3"
    assert profile["department"] == "FAE-QA"
    assert profile["reports_to"] == "Chen Chen"
    assert match_employee_profile(personnel, "kang jiang") == {}


def test_username_matches_exact_personnel_account_only():
    personnel = load_personnel(PERSONNEL_PATH)

    profile = match_employee_profile(personnel, "", username="chao.li")

    assert profile["display_name"] == "Chao Li"
    ambiguous = {
        "employees": [
            {"display_name": "Chao Li", "account": "chao.li"},
            {"display_name": "Other Person", "account": "chao.li"},
        ]
    }
    assert match_employee_profile(ambiguous, "", username="chao.li") == {}
    assert match_employee_profile(personnel, "", username="CHAO.LI") == {}
    assert match_employee_profile(personnel, "", username="nobody.here") == {}


def test_fred_profile_is_uniquely_resolved_by_account():
    personnel = load_personnel(PERSONNEL_PATH)

    matches = [item for item in amlogic_employees(personnel) if item.get("account") == "fred.chen"]
    assert len(matches) == 1
    profile = match_employee_profile(personnel, "", username="fred.chen")
    assert profile["display_name"] == "Fred Chen"
    assert profile["grade"] == "M5"
    assert profile["department"] == "FAE-SW"
    assert profile["product_lines"] == ["SmartHome"]


def test_legacy_auth_state_migrates_account_without_restoring_session(monkeypatch, tmp_path):
    (tmp_path / "auth_state.json").write_text(
        json.dumps({"username": "chao.li", "authenticated": True}), encoding="utf-8"
    )
    monkeypatch.setattr(AuthBridge, "_load_password_secret", lambda self: "stored-secret")

    class Credentials:
        def write(self, ref, username, password): self.value = (ref, username, password)
        def read(self, ref): raise KeyError(ref)
        def delete(self, ref): pass
    credentials = Credentials()

    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)

    assert bridge.authenticated is False
    assert bridge.accounts[0]["username"] == "chao.li"
    assert bridge.accounts[0]["rememberPassword"] is True
    assert credentials.value[1:] == ("chao.li", "stored-secret")
    assert not (tmp_path / "auth_state.json").exists()


def test_profile_dynamic_values_are_returned_verbatim(tmp_path):
    path = tmp_path / "personnel.json"
    payload = {"amlogic": {
        "career_levels": [{"grade": "GX", "career_track": "轨道 A", "job_title": "原始 职称"}],
        "product_lines": [{"id": "P1", "name": "产品线 α", "active": True}],
        "departments": {"部门 Ω": {"employees": [{
            "display_name": "Élodie Wu",
            "organization": {"team": "Team β", "division": "事业部"},
            "employment": {"grade": "GX", "job_title_override": "", "employee_type": "类型 Z"},
            "assignments": [{"product_line_id": "P1", "primary": True, "responsibilities": ["职责 一"]}],
            "expertise_domains": [],
            "system_roles": ["角色 R"],
            "reports_to": "主管 Ж",
        }]}},
    }}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    profile = match_employee_profile(load_personnel(path), "Élodie Wu")

    assert profile == {
        "display_name": "Élodie Wu",
        "grade": "GX",
        "job_title": "原始 职称",
        "department": "部门 Ω",
        "team": "Team β",
        "division": "事业部",
        "employee_type": "类型 Z",
        "product_lines": ["产品线 α"],
        "roles": ["角色 R"],
        "reports_to": "主管 Ж",
    }


def test_initials_and_unmatched_profile_fallbacks():
    assert initials_from_name("Xiaojia Zhao") == "XZ"
    assert initials_from_name(" xiaojia   zhao ") == "XZ"
    assert initials_from_name("prince") == "P"
    assert initials_from_name("") == ""
    assert match_employee_profile(load_personnel(PERSONNEL_PATH), "Not An Employee") == {}


def test_bridge_exposes_matched_profile_and_keeps_unmatched_identity(tmp_path):
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path)

    bridge._apply_authenticated_identity("ldap-user", " Kang Jiang ")

    assert bridge.displayName == "Kang Jiang"
    assert bridge.initials == "KJ"
    assert bridge.grade == "I3"
    assert bridge.department == "FAE-QA"
    assert bridge.reportsTo == "Chen Chen"

    bridge._apply_authenticated_identity("unknown-user", "External Person")

    assert bridge.displayName == "External Person"
    assert bridge.initials == "EP"
    assert bridge.grade == ""
    assert bridge.productLines == []


def test_ldap_identity_extracts_trimmed_display_name_and_photo():
    identity = ldap_identity_from_attributes(
        {"displayName": "  Kang Jiang  ", "thumbnailPhoto": b"photo", "jpegPhoto": b"other"}
    )

    assert identity == {"display_name": "Kang Jiang", "avatar_bytes": b"photo"}


def test_product_line_lead_title_resolves_verbatim():
    profile = match_employee_profile(load_personnel(PERSONNEL_PATH), "Chen Chen")

    assert profile["job_title"] == "Product Line Lead"


def test_account_qml_binds_dynamic_profile_without_translation():
    footer = ITEMS_FOOTER_PATH.read_text(encoding="utf-8")
    account = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")

    assert "AuthBridge.displayName" in footer
    assert "AuthBridge.roleText" in footer
    assert "AuthBridge.initials" in footer
    assert "compactItemHeight:" in footer
    assert "32" in footer
    assert "source: AuthBridge.avatarUrl" in account


def test_account_avatar_is_ldap_only_without_manual_upload_ui():
    account = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    assert "saveCroppedAvatar" not in account
    assert "avatarFileDialog" not in account
    assert "AvatarCropDialog" not in account
    assert "Upload Avatar" not in account
    assert not hasattr(AuthBridge, "saveCroppedAvatar")
    for dynamic_property in (
        "displayName",
        "grade",
        "jobTitle",
        "department",
        "team",
        "productLines",
        "reportsTo",
    ):
        assert f"qsTr(AuthBridge.{dynamic_property}" not in account


def test_account_qml_follows_a_card_hierarchy_without_clipping():
    footer = ITEMS_FOOTER_PATH.read_text(encoding="utf-8")
    account = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")

    assert "id: accountHeader" in account
    assert 'objectName: "loginCloseButton"' in account
    assert "id: accountIdentityRow" in account
    assert "Layout.preferredWidth: 66" in account
    assert "id: gradeCard" in account
    assert "id: departmentCard" in account
    assert "id: productLineCard" in account
    assert "id: productLineTags" in account
    assert "model: AuthBridge.productLines" in account
    assert "text: AuthBridge.jobTitle" in account
    assert "visible: AuthBridge.team !== \"\"" in account
    assert "visible: AuthBridge.reportsTo !== \"\"" in account
    assert "Layout.topMargin: 18" in account
    assert "var targetHeight = nextAccountMode ? 600 : 400" in account
    assert "width: footer_items.compact ? 32 : 34" in footer


def test_account_window_runtime_size_after_authenticated_init():
    probe = r'''
import sys
sys.path.insert(0, r"D:\SmartTest\ui")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.AuthBridge import AuthBridge
app = QGuiApplication([])
engine = QQmlApplicationEngine()
bridge = AuthBridge(project_root=r"D:\SmartTest")
bridge._apply_authenticated_identity("chao.li", "Chao Li")
engine.rootContext().setContextProperty("AuthBridge", bridge)
FluentUI.registerTypes(engine)
engine.load(QUrl("qrc:/example/qml/window/LoginWindow.qml"))
if not engine.rootObjects():
    raise SystemExit(2)
app.processEvents()
window = engine.rootObjects()[0]
if window.findChild(QObject, "accountSelector") is None:
    raise SystemExit(3)
if window.findChild(QObject, "rememberPasswordCheck") is None:
    raise SystemExit(4)
print(f"ACCOUNT_SIZE={window.width()}x{window.height()}")
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    marker = next(line for line in result.stdout.splitlines() if line.startswith("ACCOUNT_SIZE="))
    width, height = (int(value) for value in marker.removeprefix("ACCOUNT_SIZE=").split("x"))
    assert width >= 450
    assert height >= 550


def test_account_height_contract_preserves_standard_navigation_row():
    pane_item = (ROOT / "ui" / "FluentUI" / "imports" / "FluentUI" / "Controls" / "FluPaneItem.qml").read_text(
        encoding="utf-8"
    )
    navigation = NAVIGATION_VIEW_PATH.read_text(encoding="utf-8")

    assert "property int compactItemHeight" in pane_item
    assert "model.compactItemHeight" in navigation
    assert "return control.cellHeight" in navigation
    assert "visible: height > 0" in navigation


def test_account_fixed_labels_exist_in_both_translation_catalogs():
    expected = {
        "Grade",
        "Department",
        "Team",
        "Product Line",
        "Reports To",
    }
    for catalog_name in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(ROOT / "ui" / "example" / catalog_name).getroot()
        login_context = next(
            context for context in root.findall("context") if context.findtext("name") == "LoginWindow"
        )
        translations = {
            message.findtext("source"): message.find("translation")
            for message in login_context.findall("message")
        }
        assert expected <= translations.keys()
        for source in expected:
            translation = translations[source]
            assert translation is not None
            assert translation.get("type") not in {"unfinished", "vanished"}
            assert (translation.text or "").strip()


class _MemoryCredentials:
    def __init__(self):
        self.values = {}

    def write(self, ref, username, password):
        self.values[ref] = (username, password)

    def read(self, ref):
        if ref not in self.values:
            raise KeyError(ref)
        return self.values[ref]

    def delete(self, ref):
        self.values.pop(ref, None)


def _successful_auth(username, _password):
    return {"success": True, "username": username, "display_name": username.title(), "avatar_bytes": b"", "detail": ""}


def _sync_auth(work):
    work()


def test_account_store_normalizes_deduplicates_and_sorts_recent_login(tmp_path):
    store = AuthAccountStore(tmp_path)
    first = store.record_login("AMLOGIC\\Alice", "Alice", False, "2026-08-12T08:00:00+08:00")
    second = store.record_login("alice@amlogic.com", "Alice New", True, "2026-08-12T09:00:00+08:00")
    store.record_login("bob", "Bob", False, "2026-08-12T10:00:00+08:00")
    assert first == second
    assert [item["username"] for item in store.accounts()] == ["bob", "alice@amlogic.com"]
    assert store.accounts()[1]["display_name"] == "Alice New"


def test_account_store_contains_only_non_secret_fields_and_recovers_corruption(tmp_path):
    store = AuthAccountStore(tmp_path)
    store.record_login("alice", "Alice", True, "2026-08-12T09:00:00+08:00")
    payload = json.loads((tmp_path / "auth_accounts.json").read_text(encoding="utf-8"))
    assert set(payload["accounts"][0]) == {
        "account_id", "username", "display_name", "remember_password", "auto_login", "last_login_at"
    }
    (tmp_path / "auth_accounts.json").write_text("{broken", encoding="utf-8")
    recovered = AuthAccountStore(tmp_path)
    assert recovered.accounts() == []
    assert len(list(tmp_path.glob("auth_accounts.json.*.corrupt"))) == 1


def test_manual_login_persists_only_selected_account_credential(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    result = bridge.login("alice", "secret", True)
    account_id = account_id_for_username("alice")
    assert result["success"] is True
    assert bridge.accounts[0]["rememberPassword"] is True
    assert bridge.accounts[0]["label"] == "Alice (alice)  🔒"
    assert credentials.values == {account_id: ("alice", "secret")}
    assert "secret" not in (tmp_path / "auth_accounts.json").read_text(encoding="utf-8")


def test_saved_account_switch_failure_stays_signed_out(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", True)
    bridge.login("bob", "b", True)
    alice_id = account_id_for_username("alice")
    bridge._ldap_authenticate = lambda *_: {"success": False, "username": "", "detail": "bad"}
    result = bridge.selectAccount(alice_id)
    assert result["success"] is False
    assert bridge.authenticated is False
    assert bridge.selectedAccountId == alice_id
    assert bridge.authState == "auth_failed"


def test_saved_credential_unavailable_keeps_secret_and_preferences_for_auto_login(tmp_path):
    credentials = _MemoryCredentials()
    seed = AuthAccountStore(tmp_path)
    account_id = seed.record_login("alice", "Alice", True, auto_login=True)
    credentials.values[account_id] = ("alice", "saved-secret")
    jobs = []
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=jobs.append)
    bridge._ldap_authenticate = lambda *_: {"success": False, "code": "ldap_unavailable", "detail": "dns"}
    bridge.startAutoLogin()
    jobs.pop()()
    account = bridge._account_store.get(account_id)
    assert credentials.values[account_id] == ("alice", "saved-secret")
    assert account["remember_password"] is True
    assert account["auto_login"] is True
    assert bridge.authenticated is False
    assert bridge.authBusy is False


def test_saved_credential_unavailable_keeps_secret_and_preferences_for_switch(tmp_path):
    credentials = _MemoryCredentials()
    seed = AuthAccountStore(tmp_path)
    account_id = seed.record_login("alice", "Alice", True, auto_login=True)
    credentials.values[account_id] = ("alice", "saved-secret")
    jobs = []
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=jobs.append)
    bridge._ldap_authenticate = lambda *_: {"success": False, "code": "ldap_unavailable", "detail": "network"}
    bridge.selectAccount(account_id)
    jobs.pop()()
    account = bridge._account_store.get(account_id)
    assert credentials.values[account_id] == ("alice", "saved-secret")
    assert account["remember_password"] is True
    assert account["auto_login"] is True
    assert bridge.authenticated is False
    assert bridge.selectedAccountId == account_id


def test_logout_and_auto_login_follow_per_account_remember_choice(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", True)
    bridge.setAutoLogin(True)
    alice_id = account_id_for_username("alice")
    bridge.logout()
    calls = []
    bridge._ldap_authenticate = lambda user, password: calls.append((user, password)) or _successful_auth(user, password)
    bridge.startAutoLogin()
    bridge.logout()
    bridge.startAutoLogin()
    assert calls == [("alice", "a")]
    bridge.login("alice", "new", False)
    bridge.logout()
    assert alice_id not in credentials.values


def test_remove_account_deletes_only_target_credential(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", True)
    bridge.login("bob", "b", True)
    bridge.removeAccount(account_id_for_username("alice"))
    assert account_id_for_username("alice") not in credentials.values
    assert account_id_for_username("bob") in credentials.values
    assert [item["username"] for item in bridge.accounts] == ["bob"]


def test_use_other_account_ends_session_without_deleting_saved_history(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", True)
    bridge.useOtherAccount()
    assert bridge.authenticated is False
    assert bridge.selectedAccountId == ""
    assert bridge.rememberPassword is False
    assert account_id_for_username("alice") in credentials.values
    assert [item["username"] for item in bridge.accounts] == ["alice"]


def test_legacy_migration_keeps_files_when_credential_write_fails(monkeypatch, tmp_path):
    (tmp_path / "auth_state.json").write_text('{"username":"alice","authenticated":true}', encoding="utf-8")
    (tmp_path / "auth_secret.json").write_text('{"encrypted_password":"legacy"}', encoding="utf-8")
    monkeypatch.setattr(AuthBridge, "_load_password_secret", lambda self: "secret")

    class FailingCredentials(_MemoryCredentials):
        def write(self, ref, username, password):
            raise RuntimeError("unavailable")

    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=FailingCredentials())
    assert bridge.accounts == []
    assert (tmp_path / "auth_state.json").exists()
    assert (tmp_path / "auth_secret.json").exists()


def test_legacy_migration_rolls_back_new_credential_when_index_write_fails(monkeypatch, tmp_path):
    (tmp_path / "auth_state.json").write_text('{"username":"alice","authenticated":true}', encoding="utf-8")
    (tmp_path / "auth_secret.json").write_text('{"encrypted_password":"legacy"}', encoding="utf-8")
    monkeypatch.setattr(AuthBridge, "_load_password_secret", lambda self: "secret")
    monkeypatch.setattr(AuthAccountStore, "record_login", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    credentials = _MemoryCredentials()

    AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials)

    assert credentials.values == {}
    assert (tmp_path / "auth_state.json").exists()
    assert (tmp_path / "auth_secret.json").exists()


def test_legacy_migration_does_not_overwrite_or_delete_preexisting_credential(monkeypatch, tmp_path):
    (tmp_path / "auth_state.json").write_text('{"username":"alice","authenticated":true}', encoding="utf-8")
    (tmp_path / "auth_secret.json").write_text('{"encrypted_password":"legacy"}', encoding="utf-8")
    monkeypatch.setattr(AuthBridge, "_load_password_secret", lambda self: "legacy-secret")
    monkeypatch.setattr(AuthAccountStore, "record_login", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    credentials = _MemoryCredentials()
    account_id = account_id_for_username("alice")
    credentials.values[account_id] = ("alice", "existing-secret")

    AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials)

    assert credentials.values[account_id] == ("alice", "existing-secret")
    assert (tmp_path / "auth_state.json").exists()


def test_remove_account_credential_failure_is_retryable_and_not_reported_as_success(tmp_path):
    class FailingDeleteCredentials(_MemoryCredentials):
        fail_delete = True
        def delete(self, ref):
            if self.fail_delete:
                raise WindowsCredentialError("denied")
            super().delete(ref)

    credentials = FailingDeleteCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", True)
    account_id = account_id_for_username("alice")

    result = bridge.removeAccount(account_id)

    assert result["success"] is False
    assert result["code"] == "credential_cleanup_failed"
    assert result["message"]
    assert bridge.accounts == []
    assert account_id in bridge._account_store.pending_credential_cleanup()
    credentials.fail_delete = False
    retry = bridge.removeAccount(account_id)
    assert retry["success"] is True
    assert bridge._account_store.pending_credential_cleanup() == []


def test_authentication_runs_off_caller_and_returns_before_slow_ldap(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials)
    release = Event()
    started = Event()

    def slow_auth(username, password):
        started.set()
        release.wait(2)
        return _successful_auth(username, password)

    bridge._ldap_authenticate = slow_auth
    before = time.perf_counter()
    result = bridge.login("alice", "a", True)
    elapsed = time.perf_counter() - before

    assert result["code"] == "authenticating"
    assert elapsed < 0.2
    assert started.wait(1)
    assert bridge.authBusy is True
    release.set()


def test_stale_authentication_result_cannot_replace_newer_account_selection(tmp_path):
    jobs = []
    credentials = _MemoryCredentials()
    seed = AuthBridge(
        project_root=ROOT,
        state_root=tmp_path,
        credential_store=credentials,
        authentication_runner=_sync_auth,
    )
    seed._ldap_authenticate = _successful_auth
    seed.login("alice", "a", True)
    seed.login("bob", "b", True)
    bridge = AuthBridge(
        project_root=ROOT,
        state_root=tmp_path,
        credential_store=credentials,
        authentication_runner=jobs.append,
    )
    bridge._ldap_authenticate = _successful_auth

    bridge.selectAccount(account_id_for_username("alice"))
    bridge.selectAccount(account_id_for_username("bob"))
    jobs[1]()
    jobs[0]()

    assert bridge.authenticated is True
    assert bridge.username == "bob"
    assert bridge.selectedAccountId == account_id_for_username("bob")


def test_context_startup_triggers_auth_once_after_root_object_exists():
    class Auth:
        calls = 0
        def startAutoLogin(self): self.calls += 1

    class Engine:
        def __init__(self, auth): self._context_objects = {"AuthBridge": auth}
        def rootObjects(self): return [object()]

    auth = Auth()
    engine = Engine(auth)
    assert start_context_services(engine) is True
    assert start_context_services(engine) is False
    assert auth.calls == 1


def test_authentication_completed_signal_exposes_safe_password_save_warning(tmp_path):
    class WriteFailCredentials(_MemoryCredentials):
        def write(self, ref, username, password):
            raise WindowsCredentialError("denied")

    bridge = AuthBridge(
        project_root=ROOT,
        state_root=tmp_path,
        credential_store=WriteFailCredentials(),
        authentication_runner=_sync_auth,
    )
    bridge._ldap_authenticate = _successful_auth
    events = []
    bridge.authenticationCompleted.connect(events.append)

    bridge.login("alice", "top-secret", True)

    assert events == [{
        "success": True,
        "code": "signed_in_password_not_saved",
        "message": "Signed in, but the password could not be saved.",
        "requiresPassword": False,
        "source": "manual",
    }]
    assert "top-secret" not in repr(events)
    assert account_id_for_username("alice") not in repr(events)


def test_authentication_failure_codes_distinguish_credentials_from_ldap_unavailable(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(
        project_root=ROOT,
        state_root=tmp_path,
        credential_store=credentials,
        authentication_runner=_sync_auth,
    )
    events = []
    bridge.authenticationCompleted.connect(events.append)
    bridge._ldap_authenticate = lambda *_: {
        "success": False, "username": "", "code": "invalid_credentials", "detail": "raw bind detail"
    }
    bridge.login("alice", "bad", False)
    bridge._ldap_authenticate = lambda *_: {
        "success": False, "username": "", "code": "ldap_unavailable", "detail": "socket payload"
    }
    bridge.login("alice", "bad", False)

    assert [event["code"] for event in events] == ["invalid_credentials", "ldap_unavailable"]
    assert events[0]["message"] == "Account or password is incorrect."
    assert events[1]["message"] == "Unable to connect to LDAP. Please try again later."
    assert "raw bind detail" not in repr(events)
    assert "socket payload" not in repr(events)


def test_busy_login_rejects_duplicate_manual_submission(tmp_path):
    jobs = []
    bridge = AuthBridge(
        project_root=ROOT,
        state_root=tmp_path,
        credential_store=_MemoryCredentials(),
        authentication_runner=jobs.append,
    )
    bridge._ldap_authenticate = _successful_auth

    first = bridge.login("alice", "a", False)
    second = bridge.login("alice", "b", False)

    assert first["code"] == "authenticating"
    assert second["success"] is False
    assert second["code"] == "busy"
    assert len(jobs) == 1


def test_ldap_bind_rejection_is_classified_as_invalid_credentials(monkeypatch, tmp_path):
    class Connection:
        result = {"description": "invalidCredentials", "message": "raw server detail"}
        def __init__(self, *_args, **_kwargs): pass
        def bind(self): return False
        def unbind(self): pass

    monkeypatch.setattr(AUTH_MODULE, "Connection", Connection)
    monkeypatch.setattr(AUTH_MODULE, "Server", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(AUTH_MODULE, "NTLM", object())
    monkeypatch.setattr(AUTH_MODULE, "ALL", object())
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=_MemoryCredentials())

    result = bridge._ldap_authenticate("alice", "bad")

    assert result["code"] == "invalid_credentials"
    assert "raw server detail" in result["detail"]


def test_ldap_exception_is_classified_as_unavailable(monkeypatch, tmp_path):
    def unavailable(*_args, **_kwargs):
        raise AUTH_MODULE.LDAPException("network down")

    monkeypatch.setattr(AUTH_MODULE, "Connection", unavailable)
    monkeypatch.setattr(AUTH_MODULE, "Server", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(AUTH_MODULE, "NTLM", object())
    monkeypatch.setattr(AUTH_MODULE, "ALL", object())
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=_MemoryCredentials())

    result = bridge._ldap_authenticate("alice", "bad")

    assert result["code"] == "ldap_unavailable"


def test_runtime_login_window_keeps_password_save_warning_visible():
    probe = r'''
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, r"D:\SmartTest\ui")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.AuthBridge import AuthBridge
class Credentials:
    def write(self, *_):
        from support.windows_credentials import WindowsCredentialError
        raise WindowsCredentialError("denied")
    def read(self, ref): raise KeyError(ref)
    def delete(self, ref): pass
def sync(work): work()
app = QGuiApplication([])
engine = QQmlApplicationEngine()
state = tempfile.TemporaryDirectory()
bridge = AuthBridge(project_root=Path(r"D:\SmartTest"), state_root=Path(state.name), credential_store=Credentials(), authentication_runner=sync)
bridge._ldap_authenticate = lambda user, password: {"success": True, "username": user, "display_name": "Alice", "avatar_bytes": b"", "detail": ""}
engine.rootContext().setContextProperty("AuthBridge", bridge)
FluentUI.registerTypes(engine)
engine.load(QUrl("qrc:/example/qml/window/LoginWindow.qml"))
window = engine.rootObjects()[0]
window.setProperty("closeAfterAuthentication", True)
window.show()
bridge.login("alice", "secret", True)
app.processEvents()
print(f"VISIBLE={int(window.isVisible())};STATE={bridge.authState}")
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True,
        timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "VISIBLE=1;STATE=authenticated" in result.stdout


def test_account_auto_login_is_independent_from_remember_password(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", True)
    account_id = account_id_for_username("alice")

    bridge.setAutoLogin(False)

    assert credentials.values[account_id] == ("alice", "a")
    assert bridge.accounts[0]["rememberPassword"] is True
    assert bridge.accounts[0]["autoLogin"] is False
    restarted = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    restarted._ldap_authenticate = lambda *_: (_ for _ in ()).throw(AssertionError("must not authenticate"))
    restarted.startAutoLogin()
    assert restarted.authenticated is False


def test_select_account_restores_cached_avatar_and_model_avatar(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "a", False)
    account_id = account_id_for_username("alice")
    avatar = bridge._avatar_path_for_username("alice")
    avatar.parent.mkdir(parents=True, exist_ok=True)
    avatar.write_bytes(b"avatar")
    bridge.logout()

    bridge.selectAccount(account_id)

    assert bridge.avatarUrl == avatar.as_uri()
    assert bridge.accounts[0]["avatarUrl"] == avatar.as_uri()


def test_compact_login_runtime_exposes_identity_centered_controls():
    qml = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    assert 'objectName: "loginHeroAvatar"' in qml
    assert 'objectName: "accountPopup"' in qml
    assert 'objectName: "addAccountAction"' in qml
    assert 'objectName: "autoLoginCheck"' in qml
    assert 'objectName: "loginPrimaryButton"' in qml
    assert "LDAP Server:" not in qml
    assert 'text: qsTr("Use another account")' not in qml


def test_compact_login_controls_have_approved_visual_contract():
    qml = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    assert 'objectName: "loginOptionsRow"' in qml
    assert 'objectName: "accountSelectorArrow"' in qml
    assert "enabled: !AuthBridge.authBusy" in qml.split('objectName: "loginPrimaryButton"', 1)[1].split("}", 1)[0]
    assert "Layout.preferredWidth: 320" in qml
    assert "spacing: 8" in qml


def test_cancel_authentication_clears_pending_secret_and_ignores_worker_result(tmp_path):
    jobs = []
    bridge = AuthBridge(
        project_root=ROOT,
        state_root=tmp_path,
        credential_store=_MemoryCredentials(),
        authentication_runner=jobs.append,
    )
    bridge._ldap_authenticate = _successful_auth
    events = []
    bridge.authenticationCompleted.connect(events.append)
    bridge.login("alice", "secret", True)

    bridge.cancelAuthentication()
    jobs[0]()

    assert bridge.authBusy is False
    assert bridge.authenticated is False
    assert bridge.authState == "signed_out"
    assert bridge._pending_authentications == {}
    assert events == []


def test_login_window_has_one_close_owner_and_clears_password_on_close():
    qml = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    assert qml.count('objectName: "loginCloseButton"') == 1
    assert 'objectName: "loginPasswordInput"' in qml
    assert "AuthBridge.cancelAuthentication()" in qml
    assert "textbox_password.text = \"\"" in qml
    assert "id: accountCloseButton" not in qml


def test_runtime_close_button_closes_window_and_cancels_busy_authentication():
    probe = r'''
import sys, tempfile
from pathlib import Path
sys.path.insert(0, r"D:\SmartTest\ui")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.AuthBridge import AuthBridge
class Credentials:
    def read(self, ref): raise KeyError(ref)
    def write(self, *args): pass
    def delete(self, ref): pass
jobs=[]
app=QGuiApplication([]); engine=QQmlApplicationEngine()
bridge=AuthBridge(project_root=Path(r"D:\SmartTest"), state_root=Path(tempfile.mkdtemp()), credential_store=Credentials(), authentication_runner=jobs.append)
bridge._ldap_authenticate=lambda user,password: {"success":True,"username":user,"display_name":"Alice","avatar_bytes":b"","detail":""}
engine.rootContext().setContextProperty("AuthBridge",bridge); FluentUI.registerTypes(engine)
engine.load(QUrl("qrc:/example/qml/window/LoginWindow.qml")); window=engine.rootObjects()[0]; window.show(); app.processEvents()
password=window.findChild(QObject,"loginPasswordInput"); password.setProperty("text","not-exported")
bridge.login("alice","not-exported",True)
button=window.findChild(QObject,"loginCloseButton"); button.clicked.emit(); app.processEvents()
assert not bridge.authBusy and not bridge._pending_authentications
try: closed=not window.isVisible()
except RuntimeError: closed=True
assert closed
print("close_runtime=pass")
'''
    result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert "close_runtime=pass" in result.stdout
    assert "not-exported" not in result.stdout + result.stderr


def test_saved_credential_login_uses_store_without_exposing_password(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "stored-secret", True)
    bridge.logout()
    events = []
    bridge.authenticationCompleted.connect(events.append)

    result = bridge.loginWithSavedCredential()

    assert result["code"] in {"authenticating", "signed_in"}
    assert bridge.authenticated is True
    assert bridge.hasSavedCredential is True
    assert "stored-secret" not in repr(events)


def test_manual_password_overwrites_saved_credential(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "old-secret", True)
    bridge.logout()

    bridge.login("alice", "new-secret", True)

    assert credentials.values[account_id_for_username("alice")] == ("alice", "new-secret")


def test_login_qml_uses_one_primary_action_and_safe_mask_contract():
    qml = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    assert "Component.onCompleted: refreshMode({})" in qml
    assert 'objectName: "accountLogoutButton"' in qml
    assert "AuthBridge.loginWithSavedCredential()" in qml
    assert 'property string savedCredentialMask: "••••••••"' in qml
    assert qml.index('objectName: "accountSelector"') < qml.index('objectName: "loginPasswordInput"')
    assert qml.index('objectName: "loginPasswordInput"') < qml.index('objectName: "loginOptionsRow"')
    assert qml.index('objectName: "loginOptionsRow"') < qml.index('objectName: "loginPrimaryButton"')


def test_runtime_authenticated_primary_logout_and_saved_mask_flow():
    probe = r'''
import sys,tempfile
from pathlib import Path
sys.path.insert(0,r"D:\SmartTest\ui")
from PySide6.QtCore import QObject,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.AuthBridge import AuthBridge
class Credentials:
 def __init__(self): self.values={}
 def read(self,r): return self.values[r]
 def write(self,r,u,p): self.values[r]=(u,p)
 def delete(self,r): self.values.pop(r,None)
def sync(work): work()
app=QGuiApplication([]); engine=QQmlApplicationEngine(); credentials=Credentials()
bridge=AuthBridge(project_root=Path(r"D:\SmartTest"),state_root=Path(tempfile.mkdtemp()),credential_store=credentials,authentication_runner=sync)
bridge._ldap_authenticate=lambda user,password:{"success":True,"username":user,"display_name":"Alice","avatar_bytes":b"","detail":""}
bridge.login("alice","private-value",True)
engine.rootContext().setContextProperty("AuthBridge",bridge); FluentUI.registerTypes(engine); engine.load(QUrl("qrc:/example/qml/window/LoginWindow.qml")); app.processEvents()
window=engine.rootObjects()[0]; logout=window.findChild(QObject,"accountLogoutButton"); primary=window.findChild(QObject,"loginPrimaryButton"); password=window.findChild(QObject,"loginPasswordInput")
assert logout.property("text")=="Logout" and logout.property("visible")
assert not primary.property("visible")
logout.clicked.emit(); app.processEvents()
assert primary.property("text")=="Login" and primary.property("visible")
assert password.property("text")=="••••••••"
assert password.property("text")!="private-value"
print("authenticated_logout_mask=pass")
'''
    result = subprocess.run([sys.executable,"-c",probe],cwd=ROOT,capture_output=True,text=True,timeout=15,check=False)
    assert result.returncode == 0, result.stderr
    assert "authenticated_logout_mask=pass" in result.stdout
    assert "private-value" not in result.stdout + result.stderr


def test_production_context_router_keeps_footer_and_login_window_session_in_sync():
    global_dir = (ROOT / "ui/example/imports/example/qml/global").as_uri()
    probe = rf'''
import base64,sys,tempfile
from pathlib import Path
sys.path.insert(0,r"{ROOT / 'ui'}"); sys.path.insert(0,r"{ROOT}")
from PySide6.QtCore import QObject,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression,qmlContext
from FluentUI import FluentUI
from example.imports import resource_rc
from example.bridge.AuthBridge import AuthBridge
from example.context_registry import register_context_objects
class Credentials:
 def __init__(self): self.values={{}}
 def read(self,r): return self.values[r]
 def write(self,r,u,p): self.values[r]=(u,p)
 def delete(self,r): self.values.pop(r,None)
def sync(work): work()
app=QGuiApplication([]); engine=QQmlApplicationEngine(); credentials=Credentials(); warnings=[]
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
bridge=AuthBridge(project_root=Path(r"{ROOT}"),state_root=Path(tempfile.mkdtemp()),credential_store=credentials,authentication_runner=sync)
avatar=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
bridge._ldap_authenticate=lambda user,password:{{"success":True,"username":user,"display_name":"Alice","avatar_bytes":avatar,"detail":""}}
remove_id=bridge._account_store.record_login("remove.me","Remove Me",False)
register_context_objects(engine, {{"AuthBridge": bridge}}); FluentUI.registerTypes(engine)
engine.loadData(b"""import QtQuick 2.15
import FluentUI 1.0
import "{global_dir}" as Global
QtObject {{
 property string footerTitle: Global.ItemsFooter.accountTitle
 property string footerAvatar: Global.ItemsFooter.accountAvatarUrl.toString()
 Component.onCompleted: FluRouter.routes={{"/login":"qrc:/example/qml/window/LoginWindow.qml"}}
 function launchLogin() {{ FluRouter.navigate("/login") }}
}}""")
root=engine.rootObjects()[0]
light=QQmlExpression(qmlContext(root),root,"FluTheme.darkMode = 1"); light.evaluate(); assert not light.hasError(); app.processEvents()
bridge.login("alice","route-secret",True); app.processEvents()
assert root.property("footerTitle")=="Alice"
assert root.property("footerAvatar")!=""
QQmlExpression(qmlContext(root),root,"launchLogin()").evaluate(); app.processEvents()
window=next(item for item in app.allWindows() if item.objectName()=="toolLoginWindow")
primary=window.findChild(QObject,"loginPrimaryButton"); logout=window.findChild(QObject,"accountLogoutButton")
assert logout.property("text")=="Logout" and logout.property("visible") and not primary.property("visible")
selected_before=bridge.selectedAccountId
QQmlExpression(qmlContext(window),window,'requestRemoveAccount("'+remove_id+'")').evaluate(); app.processEvents()
assert window.property("pendingRemoveAccountId")==remove_id and bridge.selectedAccountId==selected_before
assert bridge.removeAccount(remove_id)["success"] and bridge.selectedAccountId==selected_before
QQmlExpression(qmlContext(window),window,"removeAccountDialog.close()").evaluate(); app.processEvents()
dark=QQmlExpression(qmlContext(root),root,"FluTheme.darkMode = 2"); dark.evaluate(); assert not dark.hasError(); app.processEvents()
logout.clicked.emit(); app.processEvents()
assert not bridge.authenticated
assert root.property("footerTitle")=="Account"
assert root.property("footerAvatar")!=""
assert primary.property("text")=="Login"
primary.clicked.emit(); app.processEvents()
try: successful_login_closed=not window.isVisible()
except RuntimeError: successful_login_closed=True
assert successful_login_closed and bridge.authenticated, (successful_login_closed, bridge.authenticated, warnings)
assert "route-secret" not in root.property("footerTitle")
assert warnings==[], warnings
print("production_context_route_sync=pass", flush=True)
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True,
        timeout=20, check=False, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "production_context_route_sync=pass" in result.stdout
    assert "route-secret" not in result.stdout + result.stderr


def test_login_popup_uses_username_only_and_footer_keeps_cached_avatar_when_signed_out():
    login_qml = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    footer_qml = ITEMS_FOOTER_PATH.read_text(encoding="utf-8")
    popup = login_qml.split('objectName: "accountPopup"', 1)[1].split("FluButton { id: addAccountAction", 1)[0]
    assert "modelData.username" in popup
    assert "modelData.displayName" not in popup
    selector = login_qml.split('objectName: "accountSelector"', 1)[1].split("onClicked", 1)[0]
    assert "AuthBridge.currentUsername()" in selector
    assert "AuthBridge.displayName" not in selector
    assert "readonly property url accountAvatarUrl: AuthBridge.avatarUrl" in footer_qml
    assert 'readonly property string accountTitle: AuthBridge.authenticated' in footer_qml


def test_pending_remember_and_auto_login_persist_only_after_success(tmp_path):
    credentials = _MemoryCredentials()
    jobs = []
    bridge = AuthBridge(
        project_root=ROOT, state_root=tmp_path, credential_store=credentials,
        authentication_runner=jobs.append,
    )
    bridge._account_store.record_login("alice", "Alice", False, auto_login=False)
    bridge.selectAccount(account_id_for_username("alice"))
    bridge.setRememberPassword(True)
    bridge.setAutoLogin(True)
    before = bridge._account_store.get(account_id_for_username("alice"))
    assert before["remember_password"] is False
    assert before["auto_login"] is False
    bridge.login("alice", "pending-secret", True)
    bridge._ldap_authenticate = lambda *_: {"success": False, "code": "invalid_credentials", "detail": "raw bind detail"}
    jobs.pop()()
    failed = bridge._account_store.get(account_id_for_username("alice"))
    assert failed["remember_password"] is False
    assert failed["auto_login"] is False
    assert account_id_for_username("alice") not in credentials.values

    bridge.setRememberPassword(True)
    bridge.setAutoLogin(True)
    bridge.login("alice", "pending-secret", True)
    bridge._ldap_authenticate = lambda *_: {"success": True, "username": "alice", "display_name": "Alice", "avatar_bytes": b"", "detail": ""}
    jobs.pop()()
    saved = bridge._account_store.get(account_id_for_username("alice"))
    assert saved["remember_password"] is True
    assert saved["auto_login"] is True
    assert credentials.values[account_id_for_username("alice")][1] == "pending-secret"


def test_auth_transition_logs_are_structured_and_secret_safe(tmp_path, monkeypatch):
    rows = []
    monkeypatch.setattr(AUTH_MODULE, "smart_log", lambda message, *args, **kwargs: rows.append((message, args, kwargs)))
    credentials = _MemoryCredentials()
    jobs = []
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=jobs.append)
    bridge.setRememberPassword(True)
    bridge.setAutoLogin(True)
    bridge.login("alice", "never-log-this", True)
    bridge._ldap_authenticate = lambda *_: {"success": False, "code": "ldap_unavailable", "detail": "raw ldap private detail"}
    jobs.pop()()
    bridge.startAutoLogin()
    bridge.cancelAuthentication()
    bridge.logout()
    combined = repr(rows)
    assert "never-log-this" not in combined
    assert "raw ldap private detail" not in combined
    assert "SmartTest/LDAP/" not in combined
    assert all(row[2].get("domain") == "ui" and row[2].get("source") == "AuthBridge" for row in rows)
    events = [row[2].get("extra", {}).get("event") for row in rows]
    assert "state_restored" in events
    assert "remember_password_updated" in events
    assert "auto_login_updated" in events
    assert "authentication_completed" in events
    assert "auto_login_skipped" in events
    assert "logout" in events


def test_account_management_actions_have_single_responsibility():
    qml = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    popup = qml.split('objectName: "accountPopup"', 1)[1].split("FluButton { id: addAccountAction", 1)[0]
    assert 'objectName: "accountRemoveButton"' in popup
    assert "window.requestRemoveAccount(modelData.accountId)" in popup
    assert "window.pendingRemoveAccountId = accountId" in qml
    assert "mouse.accepted = true" in popup
    profile = qml.split("visible: accountMode", 1)[1]
    assert 'text: qsTr("Remove account")' not in profile
    assert 'objectName: "accountLogoutButton"' in profile
    assert 'objectName: "loginPrimaryButton"' in qml
    assert "visible: !accountMode" in qml.split('objectName: "loginPrimaryButton"', 1)[1].split("onClicked", 1)[0]


def test_auto_failure_then_manual_success_finishes_without_infobar_loader_error(tmp_path):
    credentials = _MemoryCredentials()
    jobs = []
    bridge = AuthBridge(
        project_root=ROOT, state_root=tmp_path,
        credential_store=credentials, authentication_runner=jobs.append,
    )
    bridge._ldap_authenticate = lambda *_: {"success": False, "code": "ldap_unavailable", "detail": "unavailable"}
    bridge.login("alice", "first-secret", True)
    jobs.pop()()
    assert bridge.authBusy is False
    bridge._ldap_authenticate = _successful_auth
    bridge.login("alice", "second-secret", True)
    jobs.pop()()
    assert bridge.authenticated is True
    assert bridge.authBusy is False
    assert bridge._pending_authentications == {}


def test_authentication_completed_is_qvariantmap_readable_from_qml_runtime(tmp_path):
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=_MemoryCredentials(), authentication_runner=_sync_auth)
    bridge._ldap_authenticate = _successful_auth
    captured = []
    bridge.authenticationCompleted.connect(lambda result: captured.append({
        "success": result["success"], "code": result["code"],
        "source": result["source"], "message": result["message"],
    }))
    bridge.login("alice", "secret", True)
    assert captured == [{
        "success": True, "code": "signed_in", "source": "manual",
        "message": "Sign-in successful. Welcome, alice",
    }]


def test_store_allows_only_one_auto_login_account(tmp_path):
    store = AuthAccountStore(tmp_path)
    alice = store.record_login("alice", "Alice", True, auto_login=True)
    bob = store.record_login("bob", "Bob", True, auto_login=True)
    assert store.get(alice)["auto_login"] is False
    assert store.get(bob)["auto_login"] is True
    store.set_auto_login(alice, True)
    assert store.get(alice)["auto_login"] is True
    assert store.get(bob)["auto_login"] is False


def test_start_auto_login_prefers_enabled_recent_account_over_last_account(tmp_path):
    credentials = _MemoryCredentials()
    seed = AuthAccountStore(tmp_path)
    auto_id = seed.record_login("auto.user", "Auto", True, "2026-08-12T08:00:00+08:00", auto_login=True)
    seed.record_login("last.user", "Last", False, "2026-08-12T09:00:00+08:00")
    credentials.values[auto_id] = ("auto.user", "saved-secret")
    jobs = []
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=jobs.append)
    bridge.startAutoLogin()
    assert bridge.selectedAccountId == auto_id
    assert bridge.authBusy is True
    assert len(jobs) == 1


def test_remove_selected_account_loads_recent_history_without_authenticating(tmp_path):
    credentials = _MemoryCredentials()
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path, credential_store=credentials, authentication_runner=lambda _: None)
    older = bridge._account_store.record_login("older", "Older", False, "2026-08-12T08:00:00+08:00")
    current = bridge._account_store.record_login("current", "Current", False, "2026-08-12T09:00:00+08:00")
    bridge.selectAccount(current)
    result = bridge.removeAccount(current)
    assert result["success"] is True
    assert bridge.selectedAccountId == older
    assert bridge.currentUsername() == "older"
    assert bridge.authenticated is False

    bridge.removeAccount(older)
    assert bridge.selectedAccountId == ""
    assert bridge.currentUsername() == ""
