"""Build and platform-sign the Mobile APK through its existing owner."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main(*, runner=subprocess.run) -> int:
    runner([sys.executable, str(Path(__file__).with_name("build_apk.py"))], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
