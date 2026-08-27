"""Start the Web API and frontend development servers together."""

from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    npm = shutil.which("npm.cmd" if sys.platform.startswith("win") else "npm") or "npm"
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "smarttest_web.app:app", "--app-dir", "web/backend", "--reload", "--port", "8000", "--no-access-log"],
            cwd=ROOT,
        ),
        subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "web/frontend"),
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
