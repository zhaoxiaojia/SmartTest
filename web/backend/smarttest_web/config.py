from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    pool_size: int

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] = os.environ) -> "DatabaseSettings":
        required = ("WIFI_DB_HOST", "WIFI_DB_USER", "WIFI_DB_PASSWORD", "WIFI_DB_NAME")
        missing = [name for name in required if not environment.get(name)]
        if missing:
            raise ConfigurationError(f"Missing database environment variables: {', '.join(missing)}")
        return cls(
            host=environment["WIFI_DB_HOST"],
            port=int(environment.get("WIFI_DB_PORT", "3306")),
            user=environment["WIFI_DB_USER"],
            password=environment["WIFI_DB_PASSWORD"],
            database=environment["WIFI_DB_NAME"],
            pool_size=int(environment.get("WIFI_DB_POOL_SIZE", "10")),
        )
