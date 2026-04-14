from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestCaseInfo:
    nodeid: str
    file: str
    name: str
    markers: list[str]
    case_type: str

