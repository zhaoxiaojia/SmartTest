import json
import sys
import os
import subprocess
import xml.etree.ElementTree as ET
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


def test_legacy_auth_state_recovers_profile_from_username(monkeypatch, tmp_path):
    (tmp_path / "auth_state.json").write_text(
        json.dumps({"username": "chao.li", "authenticated": True}), encoding="utf-8"
    )
    monkeypatch.setattr(AuthBridge, "_load_password_secret", lambda self: "stored-secret")

    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path)

    assert bridge.authenticated is True
    assert bridge.username == "chao.li"
    assert bridge.displayName == "Chao Li"
    assert bridge.department == "FAE-QA"


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
    assert "id: accountCloseButton" in account
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
    assert "var targetHeight = nextAccountMode ? 560 : 320" in account
    assert "width: footer_items.compact ? 32 : 34" in footer


def test_account_window_runtime_size_after_authenticated_init():
    probe = r'''
import sys
sys.path.insert(0, r"D:\SmartTest\ui")
from PySide6.QtCore import QUrl
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
