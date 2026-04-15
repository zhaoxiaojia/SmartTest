from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BindingTargetKind(str, Enum):
    CASE = "case"
    CASE_TYPE = "case_type"
    GROUP = "group"


@dataclass(frozen=True)
class ParamGroup:
    group_id: str
    title: str
    param_keys: list[str]


@dataclass(frozen=True)
class CaseParamBinding:
    target_kind: BindingTargetKind
    target_id: str
    param_keys: list[str] = field(default_factory=list)
    group_ids: list[str] = field(default_factory=list)
