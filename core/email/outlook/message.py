"""Validate Outlook email inputs and build MIME messages."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
from pathlib import Path
from typing import Iterable, Literal

from .renderer import OutlookContentError, render_body
from .sender import DEFAULT_SENDER_NAME, FROM_ADDRESS


_ADDRESS_RE = re.compile(r"^[^\s@<>,;:]+@[^\s@<>,;:]+$")


class OutlookAddressError(ValueError):
    """Raised when a recipient address is empty or malformed."""


@dataclass(frozen=True)
class BuiltEmail:
    message: EmailMessage
    recipients: tuple[str, ...]


def _validated_addresses(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    normalized = []
    for value in values:
        if not isinstance(value, str) or "\r" in value or "\n" in value:
            raise OutlookAddressError(f"{field} 包含无效邮件地址")
        display_name, address = parseaddr(value)
        if display_name or address != value.strip() or not _ADDRESS_RE.fullmatch(address):
            raise OutlookAddressError(f"{field} 包含无效邮件地址：{value!r}")
        normalized.append(address)
    return tuple(normalized)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def build_email(
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
) -> BuiltEmail:
    """Build an email using the fixed SmartTest sender identity."""

    to_addresses = _validated_addresses(to, "To")
    cc_addresses = _validated_addresses(cc, "Cc")
    bcc_addresses = _validated_addresses(bcc, "Bcc")
    recipients = _unique((*to_addresses, *cc_addresses, *bcc_addresses))
    if not recipients:
        raise OutlookAddressError("至少需要一个有效收件人")
    if not isinstance(subject, str) or "\r" in subject or "\n" in subject:
        raise OutlookContentError("邮件主题无效")
    if not isinstance(sender_name, str) or "\r" in sender_name or "\n" in sender_name:
        raise OutlookContentError("发件人显示名称无效")

    root = Path.cwd() if base_dir is None else Path(base_dir)
    rendered = render_body(
        body,
        body_format=body_format,
        template=template,
        base_dir=root,
    )
    attachment_paths = tuple(Path(path).resolve() for path in attachments)
    for path in attachment_paths:
        if not path.is_file():
            raise OutlookContentError(f"附件不存在：{path}")

    message = EmailMessage(policy=SMTP)
    message["Subject"] = subject
    message["From"] = Address(display_name=sender_name, addr_spec=FROM_ADDRESS)
    if to_addresses:
        message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message.set_content(rendered.plain_text)
    message.add_alternative(rendered.html, subtype="html")
    html_part = message.get_payload()[-1]
    for image in rendered.inline_images:
        content_type, _encoding = mimetypes.guess_type(image.path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        html_part.add_related(
            image.path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            cid=f"<{image.content_id}>",
            disposition="inline",
        )
    for path in attachment_paths:
        content_type, _encoding = mimetypes.guess_type(path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )
    return BuiltEmail(message, recipients)
