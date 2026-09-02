"""Start the Web API and frontend development servers together."""

import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
PYTHON = BIN_DIR / ("python.exe" if sys.platform.startswith("win") else "python")
NPM = BIN_DIR / ("npm.cmd" if sys.platform.startswith("win") else "npm")


def main() -> int:
    npm_env = os.environ.copy()
    npm_env["PATH"] = os.pathsep.join(part for part in (str(BIN_DIR), npm_env.get("PATH", "")) if part)
    processes = [
        subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", "smarttest_web.app:app", "--app-dir", "web/backend", "--reload", "--port", "8000", "--no-access-log"],
            cwd=ROOT,
        ),
        subprocess.Popen(
            [str(NPM), "run", "dev", "--", "--host", "0.0.0.0"],
            cwd=ROOT / "web/frontend",
            env=npm_env,
        ),
    ]
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        return next((process.returncode for process in processes if process.returncode), 0)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
