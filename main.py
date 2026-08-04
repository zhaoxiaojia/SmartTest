from __future__ import annotations


def _background_command(argv, runner=None, daily_runner=None) -> int | None:
    weekly_switch = "--project-weekly-audit-plan"
    daily_switch = "--daily-report-run"
    arguments = list(argv)
    if daily_switch in arguments[1:]:
        if arguments != [arguments[0], daily_switch]:
            return 2
        if daily_runner is None:
            from tool.common.daily_report.background import run_scheduled_batch
            daily_runner = run_scheduled_batch
        return int(daily_runner())
    switches = {weekly_switch}
    selected = next((value for value in arguments[1:] if value in switches), None)
    if selected is None:
        return None
    if len(arguments) != 3 or arguments[1] != selected or not arguments[2]:
        return 2
    if runner is None:
        from tool.common.project_weekly_audit.command import run_plan as runner
    return int(runner(arguments[2]))


def _runtime_root():
    import sys
    from pathlib import Path

    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        return Path(packaged_root)
    return Path(__file__).resolve().parent


def main() -> int:
    """
    Single entrypoint for SmartTest.

    UI code lives under `ui/` and is executed from source (FluentUI/QML).
    """
    import sys
    from pathlib import Path

    background_result = _background_command(sys.argv)
    if background_result is not None:
        return background_result

    root = _runtime_root()
    ui_root = root / "ui"
    # Ensure we import the in-repo FluentUI/example packages instead of any
    # similarly-named site-packages installed in the venv.
    sys.path.insert(0, str(ui_root))

    from example.main import main as ui_main
    from testing.build_manifest import load_build_manifest
    from support.logging import smart_log

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
