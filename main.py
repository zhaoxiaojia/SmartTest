from __future__ import annotations


def main() -> int:
    """
    Single entrypoint for SmartTest.

    UI code lives under `ui/` and is executed from source (FluentUI/QML).
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent
    ui_root = root / "ui"
    # Ensure we import the in-repo FluentUI/example packages instead of any
    # similarly-named site-packages installed in the venv.
    sys.path.insert(0, str(ui_root))

    from example.main import main as ui_main

    ui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
