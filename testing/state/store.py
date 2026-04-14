from __future__ import annotations

import json
from pathlib import Path

from .models import TestPageState, from_jsonable, to_jsonable


def load_state(path: Path) -> TestPageState:
    if not path.exists():
        return TestPageState()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return TestPageState()
    return from_jsonable(data)


def save_state(path: Path, state: TestPageState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(state), ensure_ascii=False, indent=2), encoding="utf-8")

