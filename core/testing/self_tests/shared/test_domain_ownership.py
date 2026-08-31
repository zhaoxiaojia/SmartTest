from __future__ import annotations

import ast
import importlib
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOTS = (
    REPOSITORY_ROOT / "core",
    REPOSITORY_ROOT / "client" / "app",
    REPOSITORY_ROOT / "web" / "backend" / "smarttest_web",
)


def _imports_from(module_name: str) -> list[str]:
    matches: list[str] = []
    for root in PRODUCTION_ROOTS:
        for path in root.rglob("*.py"):
            relative = path.relative_to(REPOSITORY_ROOT)
            if "testing" in relative.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(relative))
            if any(
                isinstance(node, ast.ImportFrom) and node.module == module_name
                or isinstance(node, ast.Import)
                and any(alias.name == module_name for alias in node.names)
                for node in ast.walk(tree)
            ):
                matches.append(relative.as_posix())
    return matches


def test_shared_domain_values_have_a_neutral_owner() -> None:
    values = importlib.import_module("core.domain.values")

    for name in ("FieldBag", "NamedValue", "PersonRef", "SourceRevision"):
        assert getattr(values, name).__module__ == "core.domain.values"


def test_jira_domain_does_not_reexport_shared_domain_values() -> None:
    jira_domain = importlib.import_module("core.jira.domain")

    for name in ("FieldBag", "NamedValue", "PersonRef", "SourceRevision"):
        assert not hasattr(jira_domain, name)


def test_confluence_production_does_not_import_jira_domain() -> None:
    assert not [
        path
        for path in _imports_from("core.jira.domain")
        if path.startswith("core/confluence/")
    ]


def test_production_does_not_import_legacy_issue_models_module() -> None:
    assert _imports_from("core.issues.models") == []
