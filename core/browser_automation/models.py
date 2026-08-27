from dataclasses import dataclass


@dataclass(frozen=True)
class ContextKey:
    system_id: str
    account_id: str
