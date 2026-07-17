from dataclasses import dataclass
from enum import Enum
from support.jira_integration.core.third_party_bug import (
    ThirdPartyBugAttachment,
    ThirdPartyBugComment,
    ThirdPartyBugContext,
    ThirdPartyBugDetail,
    ThirdPartyBugListItem,
    ThirdPartyBugProject,
)


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
    reason: str = ""


RedmineAttachment = ThirdPartyBugAttachment
RedmineJournal = ThirdPartyBugComment
RedmineIssueListItem = ThirdPartyBugListItem
RedmineIssueDetail = ThirdPartyBugDetail
RedmineProject = ThirdPartyBugProject
RedmineContext = ThirdPartyBugContext
