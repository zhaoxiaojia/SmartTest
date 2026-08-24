from __future__ import annotations

from pathlib import Path

from client.app.ui import jsonTool


def app_data_dir() -> Path:
    return jsonTool.app_data_dir()
