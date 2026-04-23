from __future__ import annotations

import os


def env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))
