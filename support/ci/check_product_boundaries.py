"""Check dependency boundaries for the new multi-product directory layout."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = ("client", "core", "web", "mobile")
CORE_FORBIDDEN_IMPORTS = frozenset({"client", "web", "mobile"})
FRONTEND_IMPORTS = (
    re.compile(r"\bfrom\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"\bimport\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"\b(?:import|require)\s*\(\s*['\"]([^'\"]+)['\"]"),
)
FRONTEND_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
ANDROID_RULES = {
    "AGENTS.md": "mobile/android/**",
    ".codex/skills/smarttest-dual-codex-delivery/SKILL.md": "mobile/android/**",
    ".codex/skills/smarttest-android-workflow/SKILL.md": "mobile/android/gradlew.bat",
    ".codex/skills/smarttest-case-development/references/case-implementation-template.md": (
        "mobile/android/app/src/main/java/com/smarttest/mobile/runner/cases/"
    ),
}
DESKTOP_RULES = {
    "AGENTS.md": "client/app/ui/**",
    ".codex/skills/smarttest-dual-codex-delivery/SKILL.md": "client/app/ui/**",
    ".codex/skills/smarttest-ui-workflow/SKILL.md": "client/app/main.py",
    ".codex/skills/smarttest-testing-workflow/SKILL.md": "core/config/jsonTool.py",
    ".codex/skills/smarttest-case-development/references/case-implementation-template.md": (
        "client/app/ui/example/bridge/TestPageBridge.py"
    ),
}
CORE_RULES = {
    "AGENTS.md": "core/testing/**",
    ".codex/skills/smarttest-dual-codex-delivery/SKILL.md": "core/testing/**",
    ".codex/skills/smarttest-testing-workflow/SKILL.md": "core/testing/tests/",
    ".codex/skills/smarttest-case-development/references/case-implementation-template.md": (
        "core/testing/tests/<platform>/<case_type>/<domain>/test_<case_name>.py"
    ),
}
LEGACY_DESKTOP_RULE_PATH = re.compile(
    r"(?<!client/app/)ui/(?:\*\*|example|jsonTool|yamlTool|FluentUI)|python(?:\.exe)?\s+main\.py"
)


def _forbidden_python_imports(path: Path, root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    forbidden: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = {alias.name.partition(".")[0] for alias in node.names}
            forbidden.update(imported & CORE_FORBIDDEN_IMPORTS)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported = node.module.partition(".")[0]
            if imported in CORE_FORBIDDEN_IMPORTS:
                forbidden.add(imported)
        elif isinstance(node, ast.ImportFrom) and node.level:
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            targets = (
                [base.joinpath(*node.module.split("."))]
                if node.module
                else [base / alias.name for alias in node.names]
            )
            for target in targets:
                for product in CORE_FORBIDDEN_IMPORTS:
                    product_root = (root / product).resolve()
                    resolved = target.resolve()
                    if resolved == product_root or product_root in resolved.parents:
                        forbidden.add(product)
    return forbidden


def _check_core(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for path in sorted((root / "core").rglob("*.py")):
        if (root / "core" / "testing" / "self_tests") in path.parents:
            continue
        forbidden = sorted(_forbidden_python_imports(path, root))
        if forbidden:
            relative = path.relative_to(root)
            failures.append(f"{relative}: core must not import {', '.join(forbidden)}")
    return failures


def _check_core_location(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for legacy in ("testing", "tool", "jira", "config"):
        if (root / legacy).exists():
            failures.append(f"{legacy}/: legacy core owner path must not exist")
    for relative in (
        "core/testing/__init__.py",
        "core/tools/__init__.py",
        "core/jira/__init__.py",
        "core/config/personnel.json",
    ):
        if not (root / relative).is_file():
            failures.append(f"{relative}: missing core owner")
    return failures


def _check_active_core_rules(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for relative, required in CORE_RULES.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"{relative}: missing active repository rule")
            continue
        source = path.read_text(encoding="utf-8").replace("\\", "/")
        if required not in source:
            failures.append(f"{relative}: missing active core path")
    return failures


def _check_web_frontend(root: Path = ROOT) -> list[str]:
    frontend = root / "web" / "frontend"
    if not frontend.exists():
        return []

    failures: list[str] = []
    core = (root / "core").resolve()
    for path in sorted(frontend.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in FRONTEND_EXTENSIONS:
            continue
        source = path.read_text(encoding="utf-8")
        specifiers = {
            specifier
            for pattern in FRONTEND_IMPORTS
            for specifier in pattern.findall(source)
        }
        for specifier in sorted(specifiers):
            if not specifier.startswith("."):
                continue
            resolved = (path.parent / specifier).resolve()
            if resolved == core or core in resolved.parents:
                relative = path.relative_to(root)
                failures.append(f"{relative}: web frontend must not import {specifier} directly")
    return failures


def _check_android_location(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    if (root / "android_client").exists():
        failures.append("android_client/: legacy Android product path must not exist")
    android = root / "mobile" / "android"
    for relative in ("settings.gradle.kts", "app/build.gradle.kts", "gradlew.bat"):
        if not (android / relative).is_file():
            failures.append(f"mobile/android/{relative}: missing Android project entry")
    return failures


def _check_active_android_rules(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for relative, required in ANDROID_RULES.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"{relative}: missing active repository rule")
            continue
        source = path.read_text(encoding="utf-8")
        if required not in source.replace("\\", "/"):
            failures.append(f"{relative}: missing active mobile/android path")
        if "android_client/" in source.replace("\\", "/"):
            failures.append(f"{relative}: contains legacy Android filesystem path")
    return failures


def _check_desktop_location(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    if (root / "main.py").exists():
        failures.append("main.py: legacy desktop entrypoint must not exist")
    if (root / "ui").exists():
        failures.append("ui/: legacy desktop UI path must not exist")
    for relative in ("client/app/main.py", "client/app/ui/__init__.py"):
        if not (root / relative).is_file():
            failures.append(f"{relative}: missing desktop product entry")
    return failures


def _check_active_desktop_rules(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for relative, required in DESKTOP_RULES.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"{relative}: missing active repository rule")
            continue
        source = path.read_text(encoding="utf-8").replace("\\", "/")
        if required not in source:
            failures.append(f"{relative}: missing active client/app path")
        if LEGACY_DESKTOP_RULE_PATH.search(source):
            failures.append(f"{relative}: contains legacy desktop filesystem path")
    return failures


def main() -> int:
    missing = [name for name in PRODUCTS if not (ROOT / name / "README.md").is_file()]
    failures = [f"{name}/README.md: missing product boundary documentation" for name in missing]
    failures.extend(_check_core())
    failures.extend(_check_core_location())
    failures.extend(_check_active_core_rules())
    failures.extend(_check_web_frontend())
    failures.extend(_check_android_location())
    failures.extend(_check_active_android_rules())
    failures.extend(_check_desktop_location())
    failures.extend(_check_active_desktop_rules())
    if failures:
        print("Product boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Product boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
