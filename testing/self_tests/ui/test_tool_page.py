from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from ui.example.bridge.ToolBridge import build_tool_groups, load_tool_access


ROOT = Path(__file__).resolve().parents[3]
PERSONNEL_PATH = ROOT / "config" / "personnel.json"


def test_personnel_declares_product_line_and_technical_center_owners():
    payload = json.loads(PERSONNEL_PATH.read_text(encoding="utf-8"))

    assert {item["id"]: item["owner_account"] for item in payload["product_lines"]} == {
        "STB": "junjie.li",
        "TV": "jianfan.ai",
        "SmartHome": "chen.chen",
        "IPTV": "lingling.yu",
    }
    assert payload["technical_centers"] == [
        {
            "id": "Wi-Fi",
            "name": "Wi-Fi",
            "owner_account": "zijie.chen",
            "active": True,
        }
    ]


def test_tool_groups_keep_fixed_layout_and_filter_child_tools_by_account():
    personnel = load_tool_access(PERSONNEL_PATH)

    expected_product_lines = {
        "junjie.li": "STB",
        "jianfan.ai": "TV",
        "chen.chen": "SmartHome",
        "lingling.yu": "IPTV",
    }
    for account, product_line in expected_product_lines.items():
        account_groups = build_tool_groups(personnel, account)
        assert [group["id"] for group in account_groups] == [
            "common", "STB", "TV", "SmartHome", "IPTV", "Wi-Fi"
        ]
        assert [group["available"] for group in account_groups[1:]] == [
            group["id"] == product_line for group in account_groups[1:]
        ]

    tv_groups = build_tool_groups(personnel, "jianfan.ai")
    assert tv_groups[0]["id"] == "common"
    assert tv_groups[0]["tools"] == []
    assert tv_groups[2]["available"] is True

    wifi_groups = build_tool_groups(personnel, "zijie.chen")
    assert wifi_groups[-1]["available"] is True
    assert wifi_groups[-1]["tools"] == []

    unknown_groups = build_tool_groups(personnel, "unknown.account")
    assert len(unknown_groups) == 6
    assert not any(group["available"] for group in unknown_groups[1:])


def test_tool_navigation_and_page_layout_contract():
    items = (ROOT / "ui/example/imports/example/qml/global/ItemsOriginal.qml").read_text(
        encoding="utf-8"
    )
    page = (ROOT / "ui/example/imports/example/qml/page/T_Tool.qml").read_text(encoding="utf-8")

    assert "id: item_tool" in items
    assert 'title: qsTr("Tool")' in items
    assert "isProtectedRoute(item, item_tool)" in items
    assert 'url: "qrc:/example/qml/page/T_Tool.qml"' in items
    assert "icon: FluentIcons.Repair" in items
    assert "icon: FluentIcons.DeveloperTools" not in items[items.index("id: item_tool"):]
    assert "FluentIcons.Toolbox" not in items
    assert "ListView" not in page
    assert "ToolBridge.groups" in page
    assert 'self.tr("Common Tools")' in (ROOT / "ui/example/bridge/ToolBridge.py").read_text(encoding="utf-8")
    assert 'qsTr("Custom Tools")' in page
    expected_expanders = {
        "common_tools_expander": 'qsTr("Common Tools")',
        "stb_tools_expander": 'qsTr("STB")',
        "tv_tools_expander": 'qsTr("TV")',
        "smart_home_tools_expander": 'qsTr("SmartHome")',
        "iptv_tools_expander": 'qsTr("IPTV")',
        "wifi_tools_expander": 'qsTr("Wi-Fi")',
    }
    for object_id, header_text in expected_expanders.items():
        assert f"id: {object_id}" in page
        assert f"headerText: {header_text}" in page
    expected_group_bindings = {
        "common_tools_expander": "common",
        "stb_tools_expander": "STB",
        "tv_tools_expander": "TV",
        "smart_home_tools_expander": "SmartHome",
        "iptv_tools_expander": "IPTV",
        "wifi_tools_expander": "Wi-Fi",
    }
    for object_id, group_id in expected_group_bindings.items():
        expander = page.split(f"id: {object_id}", 1)[1].split("FluExpander {", 1)[0]
        assert f'property var toolGroup: groupById("{group_id}")' in expander
        assert "sourceComponent: tool_group_content" in expander
    assert "function groupById(groupId)" in page
    assert page.count("Binding {") == 6
    assert 'property var toolGroup: ({"available": false, "tools": []})' in page
    assert "model: toolGroup.available ? toolGroup.tools : []" in page
    assert "visible: toolGroup.available" in page
    assert page.count("FluExpander {") == 6
    assert "AuthBridge.productLines" not in page
    assert "AuthBridge.displayName" not in page
    assert "selectedToolIndex = model.index" not in page


def test_runtime_root_is_created_before_tool_bridge_registration():
    source = (ROOT / "ui/example/main.py").read_text(encoding="utf-8")

    assert source.index("runtime_root = _runtime_root()") < source.index(
        'context.setContextProperty("ToolBridge"'
    )


def test_tool_fixed_text_is_finished_in_both_catalogs():
    required_contexts = {"ItemsOriginal", "T_Tool", "ToolBridge"}
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        root = ET.parse(ROOT / "ui/example" / filename).getroot()
        contexts = {
            context.findtext("name"): context
            for context in root.findall("context")
            if context.findtext("name") in required_contexts
        }
        assert set(contexts) == required_contexts
        for context in contexts.values():
            tool_messages = [
                message
                for message in context.findall("message")
                if "Tool" in (message.findtext("source") or "")
                or context.findtext("name") == "ToolBridge"
            ]
            assert tool_messages
            for message in tool_messages:
                translation = message.find("translation")
                assert translation is not None
                assert translation.get("type") != "unfinished"
                assert (translation.text or "").strip()


def test_tool_classification_strings_are_finished_in_both_catalogs():
    expected = {
        "example_en_US.ts": {
            "STB": "STB", "TV": "TV", "SmartHome": "SmartHome",
            "IPTV": "IPTV", "Wi-Fi": "Wi-Fi",
        },
        "example_zh_CN.ts": {
            "STB": "STB", "TV": "TV", "SmartHome": "智能家居",
            "IPTV": "IPTV", "Wi-Fi": "Wi-Fi",
        },
    }
    for filename, required in expected.items():
        root = ET.parse(ROOT / "ui/example" / filename).getroot()
        context = next(c for c in root.findall("context") if c.findtext("name") == "T_Tool")
        actual = {
            message.findtext("source"): message.findtext("translation")
            for message in context.findall("message")
        }
        for source, translation in required.items():
            assert actual.get(source) == translation
