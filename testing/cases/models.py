from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TestCaseInfo:
    nodeid: str
    file: str
    name: str
    markers: list[str]
    case_type: str
    required_params: list[str] = field(default_factory=list)
    required_param_groups: list[str] = field(default_factory=list)
