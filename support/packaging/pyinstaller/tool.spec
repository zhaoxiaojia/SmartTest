import os
import sys

APP_NAME = "SmartTestTool"
repo_root = os.environ.get("SMARTTEST_REPO_ROOT") or os.path.abspath(SPECPATH)
entry = os.path.join(repo_root, "ui", "example", "tool_main.py")
hooks_root = os.path.join(repo_root, "support", "packaging", "pyinstaller", "hooks")

a = Analysis(
    [entry],
    pathex=[repo_root, os.path.join(repo_root, "ui")],
    binaries=[],
    datas=[
        (os.path.join(repo_root, "build", "generated", "build_manifest.json"),
         os.path.join("build", "generated")),
        (os.path.join(repo_root, "config", "personnel.json"), "config"),
    ],
    hiddenimports=[
        "atlassian", "atlassian.confluence", "pythoncom", "pywintypes",
        "win32com", "win32com.client", "win32cred", "ldap3",
        "FluentUI.FluentUI", "Crypto.Hash.MD4",
        "tool.common.project_weekly_audit.command",
        "tool.common.project_weekly_audit.scheduler",
    ],
    hookspath=[hooks_root],
    excludes=[
        "cv2", "testing", "android_client",
        "example.main", "example.bridge.HomeBridge", "example.bridge.RunBridge",
        "example.bridge.ReportBridge", "example.bridge.TestPageBridge",
        "example.bridge.DebugBridge", "example.bridge.BootVideoBridge",
    ],
    noarchive=False,
)

excluded_qt = (
    "Qt6Location", "Qt6VirtualKeyboard", "Qt6Pdf", "Qt6QuickTimeline",
    "Qt6DataVisualization", "Qt6Charts", "Qt6Quick3D",
)
a.binaries = [
    item for item in a.binaries
    if not any(name in os.path.basename(item[0]) for name in excluded_qt)
]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME, debug=False,
    strip=False, upx=True, console=bool(os.environ.get("SMARTTEST_CONSOLE")),
    icon=os.path.join(repo_root, "support", "packaging", "assets", "SmartTest.ico"),
    contents_directory=".",
)
COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name=APP_NAME)
