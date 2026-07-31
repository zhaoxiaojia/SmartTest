from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ConfluenceClientConfig:
    base_url: str
    def __post_init__(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Confluence base URL must use HTTP or HTTPS")

@dataclass(frozen=True)
class ConfluencePage:
    id: str
    title: str
    url: str
    body: str = ""
    view_body: str = ""
    version: int = 0
    updated_at: datetime | None = None

@dataclass(frozen=True)
class ConfluenceAttachment:
    id: str
    filename: str
    url: str
    version: int = 0
    created_at: datetime | None = None
    author: str = ""
