import ast
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_only_repository_entry_files_are_tracked_at_root():
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()

    assert sorted(path for path in tracked if "/" not in path) == [
        ".gitignore",
        "AGENTS.md",
        "LICENSE",
        "README.md",
        "main.py",
    ]


def test_jira_bridge_and_page_have_no_personal_format_audit_contract():
    bridge_path = ROOT / "ui/example/bridge/JiraBridge.py"
    tree = ast.parse(bridge_path.read_text(encoding="utf-8-sig"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    bridge_methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    qml = (ROOT / "ui/example/imports/example/qml/page/T_Jira.qml").read_text(encoding="utf-8")

    assert "jira_handler" not in imports
    assert not {"isAuditManager", "runFormatAudit", "exportFormatAudit", "auditStatusText"} & bridge_methods
    assert "Format Audit" not in qml
    assert "auditSummaryRows" not in qml
    assert "auditDetailRows" not in qml


def test_desktop_package_does_not_bundle_personal_jira_specification():
    package_spec = (ROOT / "tools/packaging/pyinstaller/main.spec").read_text(encoding="utf-8")

    assert "jira规范" not in package_spec
    assert "jira_format_spec" not in package_spec


def test_ui_translations_have_no_personal_format_audit_messages():
    forbidden = {
        "Jira format audit is ready.",
        "Only Jira managers can run or export format audits.",
        "Load Jira issues before running a format audit.",
        "Format Audit",
        "Audit Loaded Issues",
        "Export XLSX",
    }

    for relative_path in ("ui/example/example_en_US.ts", "ui/example/example_zh_CN.ts"):
        tree = ET.parse(ROOT / relative_path)
        sources = {element.text for element in tree.iter("source")}
        assert forbidden.isdisjoint(sources)
