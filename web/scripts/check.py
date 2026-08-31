"""Run Web backend and frontend checks."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main(*, runner=subprocess.run) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(part for part in (str(ROOT), env.get("PYTHONPATH", "").strip()) if part)
    runner([sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT / "web/backend", env=env, check=True)
    npm = shutil.which("npm.cmd" if sys.platform.startswith("win") else "npm") or "npm"
    for script in ("test", "lint", "build"):
        runner([npm, "run", script], cwd=ROOT / "web/frontend", check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
