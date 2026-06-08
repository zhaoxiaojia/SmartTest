from __future__ import annotations

from pathlib import Path

from ui import jsonTool


def app_data_dir() -> Path:
    return jsonTool.app_data_dir()
