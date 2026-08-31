"""Run desktop Client static and focused repository checks."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main(*, runner=subprocess.run) -> int:
    runner([sys.executable, "-m", "compileall", "-q", "client", "core"], cwd=ROOT, check=True)
    runner(
        [sys.executable, "-m", "pytest", "core/devtools/ci/test_smarttest_cli.py", "core/devtools/ci/test_check_product_boundaries.py", "-q"],
        cwd=ROOT,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
