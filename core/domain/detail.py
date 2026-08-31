from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


T = TypeVar("T")


class DetailState(str, Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True)
class DetailSection(Generic[T]):
    state: DetailState = DetailState.UNLOADED
    value: T | None = None
    source_revision: str = ""
    error_code: str = ""

    def __post_init__(self) -> None:
        if self.state is DetailState.UNLOADED and self.value is not None:
            raise ValueError("An unloaded detail section cannot contain a value")
        if self.state is DetailState.STALE and self.value is None:
            raise ValueError("A stale detail section must retain its last loaded value")
        if self.state is DetailState.FAILED and not self.error_code:
            raise ValueError("A failed detail section requires an error code")
        if self.state is not DetailState.FAILED and self.error_code:
            raise ValueError("Only a failed detail section can contain an error code")

    @classmethod
    def loaded(cls, value: T, *, source_revision: str = "") -> "DetailSection[T]":
        return cls(DetailState.LOADED, value, source_revision)

    @classmethod
    def stale(cls, value: T, *, source_revision: str = "") -> "DetailSection[T]":
        return cls(DetailState.STALE, value, source_revision)

    @classmethod
    def failed(
        cls,
        error_code: str,
        *,
        value: T | None = None,
        source_revision: str = "",
    ) -> "DetailSection[T]":
        return cls(DetailState.FAILED, value, source_revision, error_code)
