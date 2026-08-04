"""Send built Outlook messages through the fixed corporate SMTP relay."""

from __future__ import annotations

import re
import smtplib
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Literal

from support.logging import smart_log

if TYPE_CHECKING:
    from .message import BuiltEmail


SMTP_HOST = "10.18.11.55"
SMTP_PORT = 25
FROM_ADDRESS = "fae-qa-auto@amlogic.com"
DEFAULT_SENDER_NAME = "SmartTest 自动化平台"


class OutlookSendError(RuntimeError):
    """Raised when the configured SMTP relay cannot deliver a message."""


def send_built_email(
    built: BuiltEmail,
    *,
    smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
) -> None:
    timeout = 20
    smart_log(
        "Outlook SMTP connect start",
        domain="tool",
        source="support.outlook",
        extra={
            "host": SMTP_HOST,
            "port": SMTP_PORT,
            "timeout": timeout,
            "recipient_count": len(built.recipients),
        },
    )
    try:
        with smtp_factory(SMTP_HOST, SMTP_PORT, timeout=timeout) as smtp:
            smart_log("Outlook SMTP connected", domain="tool", source="support.outlook")
            smart_log(
                "Outlook SMTP send started",
                domain="tool",
                source="support.outlook",
                extra={"recipient_count": len(built.recipients)},
            )
            refused = smtp.send_message(
                built.message,
                from_addr=FROM_ADDRESS,
                to_addrs=list(built.recipients),
            )
            if refused:
                smart_log(
                    "Outlook SMTP relay partial refusal",
                    domain="tool",
                    source="support.outlook",
                    level="error",
                    extra={"refused_count": len(refused)},
                )
                raise smtplib.SMTPRecipientsRefused(refused)
            smart_log(
                "Outlook SMTP relay accepted",
                domain="tool",
                source="support.outlook",
                extra={"refused_count": 0},
            )
    except (OSError, smtplib.SMTPException) as exc:
        smart_log(
            "Outlook SMTP failure",
            domain="tool",
            source="support.outlook",
            level="error",
            extra=_safe_error(exc),
        )
        raise OutlookSendError("Outlook 邮件发送失败") from exc


def _safe_error(exc: BaseException) -> dict:
    value = getattr(exc, "smtp_error", None)
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if value is None and isinstance(exc, OSError):
        value = str(exc)
    message = re.sub(r"[^\s@]+@[^\s@]+", "[address]", str(value or ""))[:160]
    result = {"error_type": type(exc).__name__}
    code = getattr(exc, "smtp_code", None)
    if code is not None:
        result["error_code"] = int(code)
    if message:
        result["error_message"] = message
    return result


def send_email(
    *,
    subject: str,
    body: str,
    to: Iterable[str],
    cc: Iterable[str] = (),
    bcc: Iterable[str] = (),
    sender_name: str = DEFAULT_SENDER_NAME,
    body_format: Literal["markdown", "html"] = "markdown",
    attachments: Iterable[str | Path] = (),
    template: str | None = "technology",
    base_dir: str | Path | None = None,
) -> None:
    """Build and send an email; SMTP configuration is intentionally not configurable."""

    to = tuple(to)
    cc = tuple(cc)
    bcc = tuple(bcc)
    attachments = tuple(attachments)
    from .message import build_email

    built = build_email(
        subject=subject,
        body=body,
        to=to,
        cc=cc,
        bcc=bcc,
        sender_name=sender_name,
        body_format=body_format,
        attachments=attachments,
        template=template,
        base_dir=base_dir,
    )
    smart_log(
        "Outlook message built",
        domain="tool",
        source="support.outlook",
        extra={
            "recipient_count": len(built.recipients),
            "attachment_count": len(attachments),
            "inline_count": sum(
                part.get_content_disposition() == "inline"
                for part in built.message.walk()
            ),
        },
    )
    send_built_email(built)
