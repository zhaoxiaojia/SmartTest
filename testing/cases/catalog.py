from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


CATALOG_RELATIVE_PATH = Path("testing", "cases", "test_catalog.json")
GENERATED_CATALOG_RELATIVE_PATH = Path("build", "generated", "testing", "cases", "test_catalog.json")


def is_packaged_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def packaged_catalog_path() -> Path:
    for path in packaged_catalog_candidates():
        if path.exists():
            return path
    candidates = packaged_catalog_candidates()
    if candidates:
        return candidates[0]
    return Path(__file__).resolve().parent / "test_catalog.json"


def packaged_catalog_candidates() -> list[Path]:
    candidates: list[Path] = []
    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        root = Path(packaged_root).resolve()
        candidates.append(root / CATALOG_RELATIVE_PATH)
        candidates.append(root.parent / "Resources" / CATALOG_RELATIVE_PATH)

    executable = Path(sys.executable).resolve()
    executable_dir = executable.parent
    candidates.append(executable_dir / CATALOG_RELATIVE_PATH)
    candidates.append(executable_dir.parent / "Resources" / CATALOG_RELATIVE_PATH)
    candidates.append(executable_dir / "Contents" / "Resources" / CATALOG_RELATIVE_PATH)

    candidates.append(Path(__file__).resolve().parent / "test_catalog.json")
    return _unique_paths(candidates)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def source_generated_catalog_path(*, root_dir: Path | None = None) -> Path:
    if root_dir is None:
        root_dir = Path(__file__).resolve().parents[2]
    return root_dir / GENERATED_CATALOG_RELATIVE_PATH


def _load_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def load_packaged_test_catalog() -> list[dict[str, Any]]:
    return _load_catalog(packaged_catalog_path())


def load_runtime_test_catalog(*, root_dir: Path | None = None) -> list[dict[str, Any]]:
    if is_packaged_runtime():
        return load_packaged_test_catalog()
    generated = source_generated_catalog_path(root_dir=root_dir)
    rows = _load_catalog(generated)
    if rows:
        return rows
    return load_packaged_test_catalog()
