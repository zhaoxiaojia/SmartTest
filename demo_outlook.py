"""Send one PNG through the signed-in new Outlook personal mailbox."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from support.personal_outlook import send_email

RECIPIENT = "chao.li@amlogic.com"
SUBJECT_PREFIX = "SmartTest Outlook closed-loop test"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="PNG image pasted into the message body")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    subject = f"{SUBJECT_PREFIX} {datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    try:
        send_email(
            subject=subject,
            image_path=args.image,
            to=(RECIPIENT,),
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    print(f"Submitted through new Outlook; verify the sent message: {subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
