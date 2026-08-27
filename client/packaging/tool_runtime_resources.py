from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolRuntimeResource:
    source: str
    target: str
    required: bool = True


TOOL_RUNTIME_RESOURCES = (
    ToolRuntimeResource("core/config/personnel.json", "core/config/personnel.json"),
    ToolRuntimeResource(
        "build/generated/build_manifest.json",
        "build/generated/build_manifest.json",
    ),
)


def required_targets() -> tuple[str, ...]:
    return tuple(item.target for item in TOOL_RUNTIME_RESOURCES if item.required)


def missing_required(root: str | Path) -> list[str]:
    root = Path(root)
    return [target for target in required_targets() if not (root / target).is_file()]


def pyinstaller_datas(repo_root: str | Path) -> list[tuple[str, str]]:
    root = Path(repo_root)
    return [
        (str(root / item.source), str(Path(item.target).parent))
        for item in TOOL_RUNTIME_RESOURCES
    ]
