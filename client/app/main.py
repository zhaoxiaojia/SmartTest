from __future__ import annotations


def _runtime_root():
    import sys
    from pathlib import Path

    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        return Path(packaged_root)
    return Path(__file__).resolve().parents[2]


def main() -> int:
    """
    Single entrypoint for SmartTest.

    UI code lives under `client/app/ui/` and is executed from source (FluentUI/QML).
    """
    import sys
    from pathlib import Path

    root = _runtime_root()
    sys.path.insert(0, str(root))
    from core.logging import configure_platform

    configure_platform("client")

    ui_root = root / "client" / "app" / "ui"
    # Ensure we import the in-repo FluentUI/example packages instead of any
    # similarly-named site-packages installed in the venv.
    sys.path.insert(0, str(ui_root))

    from example.main import main as ui_main
    from core.testing.build_manifest import load_build_manifest
    from core.logging import smart_log

    manifest = load_build_manifest(root_dir=root)
    if manifest:
        files = manifest.get("files", {}) if isinstance(manifest.get("files", {}), dict) else {}
        test_catalog = files.get("test_catalog", {}) if isinstance(files.get("test_catalog", {}), dict) else {}
        catalog_hash = str(test_catalog.get("sha256", "") or "")
        commit = str(manifest.get("git_commit", "") or "")
        smart_log(
            "build manifest loaded",
            domain="framework",
            source="build_manifest",
            extra={"commit": commit, "test_catalog_sha256": catalog_hash},
        )

    ui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
