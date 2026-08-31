"""Build the Web static distribution."""

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main(*, runner=subprocess.run) -> int:
    npm = shutil.which("npm.cmd" if sys.platform.startswith("win") else "npm") or "npm"
    runner([npm, "run", "build"], cwd=ROOT / "web/frontend", check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
