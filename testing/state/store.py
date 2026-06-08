from __future__ import annotations

from pathlib import Path

from ui import jsonTool

from .models import TestPageState, from_jsonable, to_jsonable


def load_state(path: Path) -> TestPageState:
    data = jsonTool.read_json(path, {})
    if not isinstance(data, dict):
        return TestPageState()
    return from_jsonable(data)


def save_state(path: Path, state: TestPageState) -> None:
    jsonTool.write_json(path, to_jsonable(state))
