from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def test_shared_async_feedback_components_load_with_public_contract() -> None:
    script = r"""
import os
import sys
sys.path.insert(0, os.path.join(os.environ["SMARTTEST_ROOT"], "ui"))
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from FluentUI import FluentUI
from example.imports import resource_rc  # noqa: F401

app = QGuiApplication([])
engine = QQmlApplicationEngine()
FluentUI.registerTypes(engine)
warnings = []
engine.warnings.connect(lambda rows: warnings.extend(str(row) for row in rows))
engine.loadData(b'''import QtQuick 2.15
import QtQuick.Window 2.15
import "qrc:/example/qml/component"
Window {
    visible: false
    AppLoadingIndicator { objectName: "loading"; running: true; text: "Scan"; detail: "ADB"; blocking: true; compact: false }
    AppTaskProgress { objectName: "task"; running: true; indeterminate: false; from: 0; to: 10; value: 4; text: "Prepare"; status: "Running"; detail: "push"; phase: "push"; error: "" }
}''')
if not engine.rootObjects():
    raise SystemExit("QML root was not created: " + " | ".join(warnings))
root = engine.rootObjects()[0]
loading = root.findChild(type(root), "missing")
objects = {item.objectName(): item for item in root.children() if item.objectName()}
if objects["loading"].property("text") != "Scan" or not objects["loading"].property("blocking"):
    raise SystemExit("loading public contract not applied")
if objects["task"].property("phase") != "push" or objects["task"].property("value") != 4:
    raise SystemExit("task public contract not applied")
if warnings:
    raise SystemExit(" | ".join(warnings))
"""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SMARTTEST_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_production_qml_uses_shared_feedback_owners() -> None:
    qml_root = ROOT / "ui/example/imports/example/qml"
    excluded = {"T_Progress.qml", "T_Buttons.qml", "T_Dialog.qml", "CodeExpander.qml", "AppLoadingIndicator.qml", "AppTaskProgress.qml"}
    offenders = []
    for path in qml_root.rglob("*.qml"):
        if path.name in excluded:
            continue
        text = path.read_text(encoding="utf-8")
        if "FluProgressRing" in text or "FluProgressBar" in text:
            offenders.append(path.relative_to(qml_root).as_posix())
    assert offenders == []


def test_test_config_binds_visible_scan_stage_progress_error_and_duplicate_guard() -> None:
    source = (ROOT / "ui/example/imports/example/qml/page/T_TestConfig.qml").read_text(encoding="utf-8")
    required_bindings = (
        'enabled: !TestPageBridge.dutRefreshRunning',
        'text: qsTr("Scanning ADB devices")',
        'detail: qsTr("The DUT list will be updated before Android Client preparation starts.")',
        'running: TestPageBridge.dutRefreshRunning',
        'phase: TestPageBridge.dutRefreshPhase',
        'detail: qsTr("Progress: %1%").arg(TestPageBridge.dutRefreshProgress)',
        'error: TestPageBridge.dutRefreshError',
    )
    for binding in required_bindings:
        assert binding in source
