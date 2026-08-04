"""Public Outlook email support API."""

from .message import DEFAULT_SENDER_NAME, OutlookAddressError, build_email
from .renderer import OutlookContentError
from .sender import OutlookSendError, send_email

__all__ = [
    "DEFAULT_SENDER_NAME",
    "OutlookAddressError",
    "OutlookContentError",
    "OutlookSendError",
    "build_email",
    "send_email",
]
