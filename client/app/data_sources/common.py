from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class AuthenticatedCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class DataSourceError:
    code: str
    retryable: bool
    stage: str
    http_status: int | None = None


@dataclass(frozen=True)
class DataSourceResult(Generic[T]):
    value: T | None = None
    error: DataSourceError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def success(cls, value: T) -> "DataSourceResult[T]":
        return cls(value=value)

    @classmethod
    def failure(cls, error: DataSourceError) -> "DataSourceResult[T]":
        return cls(error=error)
