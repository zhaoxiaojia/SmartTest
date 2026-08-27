"""Build the desktop installer and portable Tool distributions."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main(*, runner=subprocess.run) -> int:
    for script in ("build_installer.py", "build_tool_portable.py"):
        runner([sys.executable, str(Path(__file__).with_name(script))], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
