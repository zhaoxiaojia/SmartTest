from client.app.ui.example.bridge.TestPageBridge import TestPageBridge as PageBridge


def bridge_with_cases(tmp_path):
    bridge = PageBridge(tmp_path)
    bridge._state.selected = []
    bridge._state.selected_files = []
    bridge._cases = [
        {"nodeid": "a", "file": "testing/tests/android/iptv/a.py", "name": "alpha", "case_type": "default"},
        {"nodeid": "b", "file": "testing/tests/android/iptv/b.py", "name": "beta", "case_type": "default"},
        {"nodeid": "c", "file": "testing/tests/android/system/c.py", "name": "gamma", "case_type": "default"},
    ]
    bridge._rebuild_case_indexes()
    return bridge


def find(nodes, key):
    for node in nodes:
        if node.get("_key") == key:
            return node
        found = find(node.get("children", []), key)
        if found: return found


def test_tree_directory_reports_three_state_and_selects_in_discovery_order(tmp_path):
    bridge = bridge_with_cases(tmp_path)
    bridge.setCaseSelected("a", True)
    iptv = find(bridge.caseTree("", []), "folder:android/iptv")
    assert (iptv["selectionState"], iptv["selectedCount"], iptv["selectableCount"]) == ("partial", 1, 2)
    assert iptv["checked"] is False
    bridge.setTreeNodeSelected("folder:android", True, "")
    assert bridge._selected_nodeids() == ["a", "b", "c"]
    android = find(bridge.caseTree("", []), "folder:android")
    assert android["selectionState"] == "checked" and android["checked"] is True
    root = bridge.caseTree("", [])[0]
    assert root["selectionState"] == "checked" and root["checked"] is True


def test_filtered_directory_selection_only_changes_visible_descendants(tmp_path):
    bridge = bridge_with_cases(tmp_path)
    bridge.setTreeNodeSelected("root:tests", True, "alpha")
    assert bridge._selected_nodeids() == ["a"]
    bridge.setTreeNodeSelected("root:tests", True, "gamma")
    assert bridge._selected_nodeids() == ["a", "c"]
    bridge.setTreeNodeSelected("folder:android", False, "alpha")
    assert bridge._selected_nodeids() == ["c"]
