from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


CATALOG_RELATIVE_PATH = Path("testing", "cases", "test_catalog.json")


def is_packaged_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def packaged_catalog_path() -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        return Path(packaged_root) / CATALOG_RELATIVE_PATH
    return Path(__file__).resolve().parent / "test_catalog.json"


def load_packaged_test_catalog() -> list[dict[str, Any]]:
    path = packaged_catalog_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]

