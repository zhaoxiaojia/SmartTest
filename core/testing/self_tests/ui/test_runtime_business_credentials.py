from __future__ import annotations

import importlib
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "client" / "app" / "ui"))
tool_module = importlib.import_module("example.bridge.ToolBridge")


def test_common_tool_catalog_excludes_retired_client_tools_and_preserves_others():
    groups = {group["id"]: group for group in tool_module.build_tool_groups()}

    assert groups["common"]["tools"] == []
    assert groups["SmartHome"]["tools"] == [{"id": "redmine"}]
    assert set(groups) == {"common", "STB", "TV", "SmartHome", "IPTV", "Wi-Fi"}
