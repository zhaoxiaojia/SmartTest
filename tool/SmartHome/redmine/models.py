from dataclasses import dataclass
from enum import Enum


class AuthState(str, Enum):
    IDLE = "idle"; SIGNING_IN = "signing_in"; CREDENTIALS_REQUIRED = "credentials_required"
    VERIFICATION_REQUIRED = "verification_required"; AUTHENTICATED = "authenticated"; FAILED = "failed"


@dataclass(frozen=True)
class Credential:
    username: str
    password: str


@dataclass(frozen=True)
class AuthResult:
    state: AuthState
    message: str = ""
    username: str = ""
