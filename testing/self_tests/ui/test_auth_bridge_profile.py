import json
import sys
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtGui import QImage


ROOT = Path(__file__).resolve().parents[3]
PERSONNEL_PATH = ROOT / "config" / "personnel.json"
ITEMS_FOOTER_PATH = ROOT / "ui" / "example" / "imports" / "example" / "qml" / "global" / "ItemsFooter.qml"
LOGIN_WINDOW_PATH = ROOT / "ui" / "example" / "imports" / "example" / "qml" / "window" / "LoginWindow.qml"
CROP_DIALOG_PATH = ROOT / "ui" / "example" / "imports" / "example" / "qml" / "component" / "AvatarCropDialog.qml"
NAVIGATION_VIEW_PATH = ROOT / "ui" / "FluentUI" / "imports" / "FluentUI" / "Controls" / "FluNavigationView.qml"
sys.path.insert(0, str(ROOT / "ui"))

from example.bridge.AuthBridge import (  # noqa: E402
    AuthBridge,
    initials_from_name,
    ldap_identity_from_attributes,
    load_personnel,
    match_employee_profile,
)


def _employees_by_name():
    payload = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))
    return {employee["display_name"]: employee for employee in payload["employees"]}


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
    payload = {
        "career_levels": [{"grade": "GX", "career_track": "轨道 A", "job_title": "原始 职称"}],
        "product_lines": [{"id": "P1", "name": "产品线 α", "active": True}],
        "employees": [{
            "display_name": "Élodie Wu",
            "organization": {"department": "部门 Ω", "team": "Team β", "division": "事业部"},
            "employment": {"grade": "GX", "job_title_override": "", "employee_type": "类型 Z"},
            "assignments": [{"product_line_id": "P1", "primary": True, "responsibilities": ["职责 一"]}],
            "expertise_domains": [],
            "system_roles": ["角色 R"],
            "reports_to": "主管 Ж",
        }],
    }
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


def _write_image(path: Path, image_format: str, color: int = 0xFF336699):
    image = QImage(2, 2, QImage.Format_ARGB32)
    image.fill(color)
    assert image.save(str(path), image_format)


def test_save_cropped_avatar_outputs_square_selected_region_and_replaces(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "config").mkdir(parents=True)
    (project_root / "config" / "personnel.json").write_text(
        PERSONNEL_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    source = tmp_path / "split.png"
    image = QImage(100, 50, QImage.Format_ARGB32)
    image.fill(0xFFFF0000)
    for x in range(50, 100):
        for y in range(50):
            image.setPixel(x, y, 0xFF0000FF)
    assert image.save(str(source), "PNG")
    bridge = AuthBridge(project_root=project_root, state_root=tmp_path / "state")
    bridge._apply_authenticated_identity("chao.li", "Chao Li")

    first = bridge.saveCroppedAvatar(source.as_uri(), 0.0, 0.0, 1.0)
    second = bridge.saveCroppedAvatar(source.as_uri(), 1.0, 0.0, 1.0)

    assert first["success"] is True
    assert second["success"] is True
    assert second["path"] == first["path"]
    output = QImage(second["path"])
    assert output.width() == 256
    assert output.height() == 256
    center = output.pixelColor(128, 128)
    assert center.blue() > 240
    assert center.red() < 15


def test_save_cropped_avatar_rejects_invalid_source_and_parameters(tmp_path):
    bridge = AuthBridge(project_root=ROOT, state_root=tmp_path / "state")
    bridge._apply_authenticated_identity("chao.li", "Chao Li")
    source = tmp_path / "portrait.png"
    _write_image(source, "PNG")

    assert bridge.saveCroppedAvatar((tmp_path / "missing.png").as_uri(), 0, 0, 1)["success"] is False
    assert bridge.saveCroppedAvatar(source.as_uri(), float("nan"), 0, 1)["success"] is False
    assert bridge.saveCroppedAvatar(source.as_uri(), 0, 0, 0)["success"] is False


def test_save_cropped_avatar_clamps_crop_bounds(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "config").mkdir(parents=True)
    (project_root / "config" / "personnel.json").write_text(
        PERSONNEL_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    source = tmp_path / "portrait.png"
    _write_image(source, "PNG")
    bridge = AuthBridge(project_root=project_root, state_root=tmp_path / "state")
    bridge._apply_authenticated_identity("chao.li", "Chao Li")

    result = bridge.saveCroppedAvatar(source.as_uri(), 9, -4, 3)

    assert result["success"] is True
    output = QImage(result["path"])
    assert output.size() == QImage(256, 256, QImage.Format_ARGB32).size()


def test_uploaded_avatar_precedes_ldap_cache_and_updates_in_place(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "config").mkdir(parents=True)
    (project_root / "config" / "personnel.json").write_text(
        PERSONNEL_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    _write_image(first, "JPG")
    _write_image(second, "JPG", 0xFFCC5500)
    bridge = AuthBridge(project_root=project_root, state_root=tmp_path / "state")
    bridge._apply_authenticated_identity("ldap-user", "Kang Jiang")
    ldap_path = bridge._avatar_path_for_username("ldap-user")
    ldap_path.parent.mkdir(parents=True)
    ldap_path.write_bytes(b"ldap")

    first_result = bridge.saveCroppedAvatar(first.as_uri(), 0, 0, 1)
    second_result = bridge.saveCroppedAvatar(second.as_uri(), 0, 0, 1)

    assert first_result["success"] is True
    assert second_result["success"] is True
    assert second_result["path"] == first_result["path"]
    destination = Path(first_result["path"])
    assert QImage(str(destination)).pixelColor(128, 128).red() > 190
    assert bridge.avatarUrl == destination.as_uri()


def test_product_line_lead_title_resolves_verbatim():
    profile = match_employee_profile(load_personnel(PERSONNEL_PATH), "Chen Chen")

    assert profile["job_title"] == "Product Line Lead"


def test_account_qml_binds_dynamic_profile_and_avatar_upload_without_translation():
    footer = ITEMS_FOOTER_PATH.read_text(encoding="utf-8")
    account = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")

    assert "AuthBridge.displayName" in footer
    assert "AuthBridge.roleText" in footer
    assert "AuthBridge.initials" in footer
    assert "compactItemHeight:" in footer
    assert "32" in footer
    assert "FileDialog" in account
    assert "AuthBridge.saveCroppedAvatar" in account
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


def test_account_identity_and_avatar_crop_flow_bindings():
    account = LOGIN_WINDOW_PATH.read_text(encoding="utf-8")
    crop_dialog = CROP_DIALOG_PATH.read_text(encoding="utf-8")

    assert 'text: AuthBridge.displayName || AuthBridge.username' in account
    assert "text: AuthBridge.jobTitle" in account
    assert 'AuthBridge.username + " · LDAP"' not in account
    assert 'qsTr("Authenticated")' not in account
    assert "onSelectedFileChanged:" in account
    assert "selectedAvatarSource = selectedFile" in account
    assert "queueAvatarCrop(selectedAvatarSource.toString())" in account
    assert "id: cropOpenTimer" in account
    assert "interval: 50" in account
    assert "if(avatarFileDialog.visible)" in account
    assert 'objectName: "avatarFileDialog"' in account
    assert "AuthBridge.saveCroppedAvatar" in account
    assert "id: cropViewport" in crop_dialog
    assert "drag.target: cropImage" in crop_dialog
    assert "FluSlider" in crop_dialog
    assert "cropAccepted" in crop_dialog
    assert "onClicked: cropDialog.cancelCrop()" in crop_dialog
    assert "FluPopup {" in crop_dialog
    assert 'objectName: "avatarCropDialog"' in crop_dialog
    assert "anchors.centerIn: Overlay.overlay" in crop_dialog
    assert "bottomPadding: 28" in crop_dialog


def test_avatar_file_dialog_acceptance_opens_crop_popup_visible_and_centered_at_runtime(tmp_path):
    source = tmp_path / "portrait.png"
    _write_image(source, "PNG")
    probe = rf'''
import sys
sys.path.insert(0, r"D:\SmartTest\ui")
from PySide6.QtCore import QObject, QMetaObject, QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
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
app.processEvents()
window = engine.rootObjects()[0]
window.show()
app.processEvents()
popup = window.findChild(QObject, "avatarCropDialog")
file_dialog = window.findChild(QObject, "avatarFileDialog")
if popup is None or file_dialog is None:
    raise SystemExit(3)
from PySide6.QtCore import QEventLoop, QTimer
QMetaObject.invokeMethod(file_dialog, "open", Qt.ConnectionType.DirectConnection)
app.processEvents()
if not file_dialog.property("visible"):
    raise SystemExit(4)
selected_file = QUrl.fromLocalFile(r"{source}")
file_dialog.setProperty("currentFile", selected_file)
file_dialog.setProperty("selectedFile", selected_file)
QMetaObject.invokeMethod(file_dialog, "accept", Qt.ConnectionType.DirectConnection)
loop = QEventLoop()
QTimer.singleShot(150, loop.quit)
loop.exec()
viewport = window.findChild(QObject, "avatarCropViewport")
crop_image = window.findChild(QObject, "avatarCropImage")
slider = window.findChild(QObject, "avatarCropZoomSlider")
cancel_button = window.findChild(QObject, "avatarCropCancelButton")
apply_button = window.findChild(QObject, "avatarCropApplyButton")
if any(item is None for item in (viewport, crop_image, slider, cancel_button, apply_button)):
    raise SystemExit(5)
controls_visible = all(item.property("visible") for item in (slider, cancel_button, apply_button))
initial_avatar = bridge.property("avatarUrl")
slider_point = slider.mapToScene(QPointF(slider.property("width") * 0.7, slider.property("height") / 2))
QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(round(slider_point.x()), round(slider_point.y())))
app.processEvents()
slider_changed = slider.property("value") > 1
cancel_point = cancel_button.mapToScene(
    QPointF(cancel_button.property("width") / 2, cancel_button.property("height") / 2)
)
QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(round(cancel_point.x()), round(cancel_point.y())))
app.processEvents()
cancel_loop = QEventLoop()
QTimer.singleShot(250, cancel_loop.quit)
cancel_loop.exec()
print(f"POPUP={{int(not popup.property('visible'))}},{{popup.property('x')}},{{popup.property('y')}},{{popup.property('width')}},{{popup.property('height')}},{{window.width()}},{{window.height()}},{{int(file_dialog.property('visible'))}},{{viewport.property('width')}},{{viewport.property('height')}},{{int(viewport.property('clip'))}},{{int(controls_visible)}},{{int(slider_changed)}},{{int(bridge.property('avatarUrl') == initial_avatar)}}")
'''
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True, timeout=15, check=False
    )
    assert result.returncode == 0, result.stderr
    marker = next(line for line in result.stdout.splitlines() if line.startswith("POPUP="))
    (
        cancelled,
        x,
        y,
        width,
        height,
        window_width,
        window_height,
        file_dialog_visible,
        viewport_width,
        viewport_height,
        viewport_clips,
        controls_visible,
        slider_changed,
        avatar_unchanged,
    ) = (
        float(value) for value in marker.removeprefix("POPUP=").split(",")
    )
    assert cancelled == 1, marker
    assert file_dialog_visible == 0
    assert (viewport_width, viewport_height, viewport_clips) == (300, 300, 1)
    assert controls_visible == 1
    assert (slider_changed, avatar_unchanged) == (1, 1)
    assert x >= 0 and y >= 0
    assert x + width <= window_width
    assert y + height <= window_height
    assert abs((x + width / 2) - window_width / 2) <= 2
    assert abs((y + height / 2) - window_height / 2) <= 2


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
        "Upload Avatar",
        "Image files (*.png *.jpg *.jpeg)",
        "Avatar upload failed",
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


def test_avatar_crop_fixed_labels_exist_in_both_translation_catalogs():
    expected = {"Crop Avatar", "Cancel", "Apply"}
    for catalog_name in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(ROOT / "ui" / "example" / catalog_name).getroot()
        crop_context = next(
            (context for context in root.findall("context") if context.findtext("name") == "AvatarCropDialog"),
            None,
        )
        assert crop_context is not None
        messages = {message.findtext("source"): message.find("translation") for message in crop_context.findall("message")}
        assert expected <= messages.keys()
        for source in expected:
            translation = messages[source]
            assert translation is not None
            assert translation.get("type") not in {"unfinished", "vanished"}
            assert (translation.text or "").strip()
