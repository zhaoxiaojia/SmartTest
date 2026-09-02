"""Build the Web static distribution."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
NPM = BIN_DIR / ("npm.cmd" if sys.platform.startswith("win") else "npm")


def main(*, runner=subprocess.run) -> int:
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(part for part in (str(BIN_DIR), env.get("PATH", "")) if part)
    runner([str(NPM), "run", "build"], cwd=ROOT / "web/frontend", env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
