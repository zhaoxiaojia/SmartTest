from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """
    Single entrypoint for SmartTest.

    UI code lives under `ui/` and is executed from source (FluentUI/QML).
    """
    root = Path(__file__).resolve().parent
    ui_root = root / "ui"
    sys.path.insert(0, str(ui_root))

    # Keep the upstream package name `example` for now, but run it from `ui/`.
    from example.main import main as ui_main

    ui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

