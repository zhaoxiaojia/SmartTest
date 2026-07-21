import os
import sys
import json

APP_NAME = "SmartTest"


def _find_repo_root(start_dir: str) -> str:
    cur = os.path.abspath(start_dir)
    for _ in range(8):
        if os.path.isfile(os.path.join(cur, "main.py")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start_dir)


repo_root = os.environ.get("SMARTTEST_REPO_ROOT") or _find_repo_root(os.getcwd())
mainPath = os.path.join(repo_root, "main.py")
ui_root = os.path.join(repo_root, "ui")
test_catalog = os.path.join(repo_root, "build", "generated", "testing", "cases", "test_catalog.json")
testing_root = os.path.join(repo_root, "testing")
support_root = os.path.join(repo_root, "support")
ai_root = os.path.join(repo_root, "AI")
jira_root = os.path.join(repo_root, "jira")
hooks_root = os.path.join(repo_root, "support", "packaging", "pyinstaller", "hooks")
build_manifest = os.path.join(repo_root, "build", "generated", "build_manifest.json")
personnel_config = os.path.join(repo_root, "config", "personnel.json")
app_version = "0.0.0"
try:
    with open(build_manifest, "r", encoding="utf-8") as fh:
        app_version = str(json.load(fh).get("version") or app_version)
except Exception:
    pass
android_privapp_permissions = os.path.join(
    repo_root,
    "android_client",
    "system_app",
    "privapp-permissions-com.smarttest.mobile.xml",
)
android_client_init = os.path.join(repo_root, "android_client", "__init__.py")
android_smarttest_catalog = os.path.join(
    repo_root,
    "android_client",
    "app",
    "src",
    "main",
    "java",
    "com",
    "smarttest",
    "mobile",
    "runner",
    "SmartTestCatalog.kt",
)

a = Analysis(
    [mainPath],
    pathex=[repo_root, ui_root],
    binaries=[],
    datas=[
        (
            ui_root,
            "ui",
        ),
        (
            testing_root,
            "testing",
        ),
        (
            support_root,
            "support",
        ),
        (
            ai_root,
            "AI",
        ),
        (
            jira_root,
            "jira",
        ),
        (
            test_catalog,
            os.path.join("testing", "cases"),
        ),
        (
            build_manifest,
            os.path.join("build", "generated"),
        ),
        (
            personnel_config,
            "config",
        ),
        (
            android_client_init,
            "android_client",
        ),
        (
            android_smarttest_catalog,
            os.path.join(
                "android_client",
                "app",
                "src",
                "main",
                "java",
                "com",
                "smarttest",
                "mobile",
                "runner",
            ),
        ),
        (
            android_privapp_permissions,
            os.path.join("android_client", "system_app"),
        ),
    ],
    hiddenimports=[
        # Ensure UI packages are discoverable even if imports are indirect.
        "example.main",
        "FluentUI.FluentUI",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "Crypto.Hash.MD4",
        "ldap3",
        "ldap3.core",
        "ldap3.protocol",
        "pyasn1",
        "serial",
        "serial.tools.list_ports",
        "cv2",
        "numpy",
        "ui.example.bridge.BootVideoBridge",
        "testing.tool.boot_video",
        "testing.tool.boot_video.analyzer",
        "testing.tool.boot_video.camera",
        "testing.tool.boot_video.power",
        "testing.tool.boot_video.recorder",
        "testing.tool.boot_video.results",
        "testing.tool.boot_video.roi",
        "testing.tool.boot_video.service",
        "testing.tool.boot_video.state_machine",
        "testing.tool.boot_video.templates",
    ],
    hookspath=[hooks_root],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

if sys.platform.startswith("darwin"):
    excludes_binaries = [
        'QtLocation',
        'QtVirtualKeyboard',
        'QtPdfQuick',
        'QtPdf',
        'QtQuickTimeline',
        'QtDataVisualizationQml',
        'QtDataVisualization',
        'QtCharts',
        'QtChartsQml',
        'QtQuick3D',
        'QtQuick3DAssetImport',
        'QtQuick3D',
        'QtQuick3DAssetUtils',
        'QtQuick3DEffects',
        'QtQuick3DHelpers',
        'QtQuick3DParticleEffects',
        'QtQuick3DParticles',
        'QtQuick3DRuntimeRender',
        'QtQuick3D',
        'QtQuick3DUtils'
    ]
else:
    excludes_binaries = [
        'Qt6Location',
        'Qt6VirtualKeyboard',
        'Qt6PdfQuick',
        'Qt6Pdf',
        'Qt6QuickTimeline',
        'Qt6DataVisualizationQml',
        'Qt6DataVisualization',
        'Qt6Charts',
        'Qt6ChartsQml',
        'Qt6Quick3D',
        'Qt6Quick3DAssetImport',
        'Qt6Quick3D',
        'Qt6Quick3DAssetUtils',
        'Qt6Quick3DEffects',
        'Qt6Quick3DHelpers',
        'Qt6Quick3DParticleEffects',
        'Qt6Quick3DParticles',
        'Qt6Quick3DRuntimeRender',
        'Qt6Quick3D',
        'Qt6Quick3DUtils'
    ]

a.binaries = [x for x in a.binaries if not any(item in os.path.basename(x[0]) for item in excludes_binaries)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=bool(os.environ.get("SMARTTEST_CONSOLE")),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(
        repo_root,
        "support",
        "packaging",
        "assets",
        "favicon.icns" if sys.platform.startswith("darwin") else "SmartTest.ico",
    ),
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='',
)

app = BUNDLE(
    coll,
    name=APP_NAME + '.app',
    icon=os.path.join(repo_root, "support", "packaging", "assets", "favicon.icns"),
    bundle_identifier="com.amlogic.smarttest",
    version=app_version,
    info_plist={
        "CFBundleDisplayName": APP_NAME,
        "CFBundleName": APP_NAME,
        "CFBundleShortVersionString": app_version,
        "CFBundleVersion": app_version,
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)
