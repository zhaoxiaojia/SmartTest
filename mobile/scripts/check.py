"""Run Mobile unit checks."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main(*, runner=subprocess.run) -> int:
    gradle = ROOT / "mobile/android" / ("gradlew.bat" if sys.platform.startswith("win") else "gradlew")
    runner([str(gradle), ":app:testDebugUnitTest"], cwd=ROOT / "mobile/android", check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
