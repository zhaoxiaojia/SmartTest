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


def _forbidden_python_imports(path: Path, root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
        forbidden = sorted(_forbidden_python_imports(path, root))
        if forbidden:
            relative = path.relative_to(root)
            failures.append(f"{relative}: core must not import {', '.join(forbidden)}")
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


def main() -> int:
    missing = [name for name in PRODUCTS if not (ROOT / name / "README.md").is_file()]
    failures = [f"{name}/README.md: missing product boundary documentation" for name in missing]
    failures.extend(_check_core())
    failures.extend(_check_web_frontend())
    if failures:
        print("Product boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Product boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
