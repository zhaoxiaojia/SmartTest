import os
import sys

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
android_catalog = os.path.join(
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
test_catalog = os.path.join(repo_root, "build", "generated", "testing", "cases", "test_catalog.json")
android_apk = os.path.join(repo_root, "android_client", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
android_platform_apk = os.path.join(
    repo_root,
    "android_client",
    "app",
    "build",
    "outputs",
    "apk",
    "debug",
    "app-debug-platform.apk",
)
android_privapp_permissions = os.path.join(
    repo_root,
    "android_client",
    "system_app",
    "privapp-permissions-com.smarttest.mobile.xml",
)

a = Analysis(
    [mainPath],
    pathex=[repo_root, ui_root],
    binaries=[],
    datas=[
        (
            android_catalog,
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
            test_catalog,
            os.path.join("testing", "cases"),
        ),
        (
            android_apk,
            os.path.join("android_client", "app", "build", "outputs", "apk", "debug"),
        ),
        (
            android_platform_apk,
            os.path.join("android_client", "app", "build", "outputs", "apk", "debug"),
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

if sys.platform.startswith("darwin"):
    excludes_binaries = [
        'QtLocation',
        'QtWebChannel',
        'QtWebEngineQuick',
        'QtWebEngineQuickDelegatesQml',
        'QtWebSockets',
        'QtVirtualKeyboard',
        'QtPdfQuick',
        'QtPdf',
        'QtQuickTimeline',
        'QtDataVisualizationQml',
        'QtDataVisualization',
        'QtCharts',
        'QtChartsQml',
        'QtWebEngineCore',
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
        'Qt6WebChannel',
        'Qt6WebEngineQuick',
        'Qt6WebEngineQuickDelegatesQml',
        'Qt6WebSockets',
        'Qt6VirtualKeyboard',
        'Qt6PdfQuick',
        'Qt6Pdf',
        'Qt6QuickTimeline',
        'Qt6DataVisualizationQml',
        'Qt6DataVisualization',
        'Qt6Charts',
        'Qt6ChartsQml',
        'Qt6WebEngineCore',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(repo_root, "tools", "packaging", "assets", "SmartTest.ico"),
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
    icon=os.path.join(repo_root, "tools", "packaging", "assets", "favicon.icns"),
    bundle_identifier=None
)
