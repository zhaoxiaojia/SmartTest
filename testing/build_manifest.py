from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_build_manifest(*, root_dir: Path) -> dict[str, Any]:
    path = root_dir / "build" / "generated" / "build_manifest.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload
