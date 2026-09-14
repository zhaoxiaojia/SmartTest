from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'web' / 'backend'
for value in (str(ROOT), str(BACKEND)):
    if value not in sys.path:
        sys.path.insert(0, value)

from smarttest_web.audit.weekly_command import install_windows_task, run_product_weekly_audit


def main(argv=None):
    parser = argparse.ArgumentParser(description='SmartTest weekly Jira and Confluence audit email')
    parser.add_argument('--install', action='store_true', help='upsert the fixed Monday 15:00 Windows task')
    args = parser.parse_args(argv)
    if args.install:
        install_windows_task(Path(sys.executable), Path(__file__))
        return 0
    return run_product_weekly_audit()


if __name__ == '__main__':
    raise SystemExit(main())
