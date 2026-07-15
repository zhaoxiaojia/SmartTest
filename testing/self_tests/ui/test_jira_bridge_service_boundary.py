import ast
from pathlib import Path


def test_jira_bridge_only_imports_jira_application_boundary():
    path = Path("ui/example/bridge/JiraBridge.py")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("jira_tool")
    }

    assert imported <= {"jira_tool.services"}


def test_workspace_facade_keeps_explicit_bridge_entry_points():
    path = Path("jira_tool/services/workspace.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    workspace = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "JiraWorkspaceService"
    )

    methods = {node.name for node in workspace.body if isinstance(node, ast.FunctionDef)}

    assert {"fetch_saved_filters", "browse", "fetch_issue_detail", "analyze"} <= methods
