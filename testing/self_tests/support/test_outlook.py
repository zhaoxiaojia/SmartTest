from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

from support.outlook import (
    OutlookAddressError,
    OutlookContentError,
    OutlookSendError,
    build_email,
    send_email,
)
from support.outlook.renderer import render_body
from support.outlook.sender import send_built_email


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
)


def test_markdown_renders_technology_html(tmp_path):
    rendered = render_body(
        "# 周报\n\n**通过**",
        body_format="markdown",
        template="technology",
        base_dir=tmp_path,
    )

    assert "<h1>周报</h1>" in rendered.html
    assert "<strong>通过</strong>" in rendered.html
    assert 'role="presentation"' in rendered.html
    assert rendered.plain_text == "# 周报\n\n**通过**"


def test_markdown_local_image_becomes_cid(tmp_path):
    image = tmp_path / "trend.png"
    image.write_bytes(PNG_BYTES)

    rendered = render_body(
        "![趋势](trend.png)",
        body_format="markdown",
        template=None,
        base_dir=tmp_path,
    )

    assert 'src="cid:' in rendered.html
    assert len(rendered.inline_images) == 1
    assert rendered.inline_images[0].path == image


def test_duplicate_local_image_uses_one_inline_resource(tmp_path):
    image = tmp_path / "trend.png"
    image.write_bytes(PNG_BYTES)

    rendered = render_body(
        '<img src="trend.png"><img src="./trend.png">',
        body_format="html",
        template=None,
        base_dir=tmp_path,
    )

    assert len(rendered.inline_images) == 1
    assert rendered.html.count(f"cid:{rendered.inline_images[0].content_id}") == 2


@pytest.mark.parametrize("scheme", ["https://", "http://", "cid:", "data:"])
def test_nonlocal_image_is_left_unchanged(tmp_path, scheme):
    source = f"{scheme}example.invalid/a.png"

    rendered = render_body(
        f'<img src="{source}">',
        body_format="html",
        template=None,
        base_dir=tmp_path,
    )

    assert source in rendered.html
    assert rendered.inline_images == ()


def test_missing_local_image_fails_before_send(tmp_path):
    with pytest.raises(OutlookContentError, match="missing.png"):
        render_body(
            "![缺失](missing.png)",
            body_format="markdown",
            template=None,
            base_dir=tmp_path,
        )


@pytest.mark.parametrize(
    ("body_format", "template"),
    [("text", None), ("markdown", "unknown")],
)
def test_unsupported_rendering_option_is_rejected(tmp_path, body_format, template):
    with pytest.raises(OutlookContentError):
        render_body("body", body_format=body_format, template=template, base_dir=tmp_path)


def test_build_email_sets_headers_hides_bcc_and_embeds_resources(tmp_path):
    image = tmp_path / "trend.png"
    image.write_bytes(PNG_BYTES)
    attachment = tmp_path / "detail.csv"
    attachment.write_text("id,status\n1,pass\n", encoding="utf-8")

    built = build_email(
        subject="周报",
        body="![趋势](trend.png)",
        to=["to@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        sender_name="SmartTest 周报",
        attachments=[attachment],
        base_dir=tmp_path,
    )

    assert str(built.message["From"]) == "SmartTest 周报 <fae-qa-auto@amlogic.com>"
    assert built.message["To"] == "to@example.com"
    assert built.message["Cc"] == "cc@example.com"
    assert built.message["Bcc"] is None
    assert built.recipients == (
        "to@example.com",
        "cc@example.com",
        "bcc@example.com",
    )
    assert any(
        part.get_content_disposition() == "inline" for part in built.message.walk()
    )
    assert any(part.get_filename() == "detail.csv" for part in built.message.walk())


@pytest.mark.parametrize("recipients", [[], ["invalid"], [""], ["a@example.com\nBcc:x@y.com"]])
def test_invalid_recipients_fail_before_smtp(recipients):
    with pytest.raises(OutlookAddressError):
        build_email(subject="x", body="x", to=recipients)


def test_missing_attachment_fails_before_smtp(tmp_path):
    with pytest.raises(OutlookContentError, match="missing.csv"):
        build_email(
            subject="x",
            body="x",
            to=["to@example.com"],
            attachments=[tmp_path / "missing.csv"],
        )


def test_sender_uses_only_fixed_server_and_envelope_addresses():
    built = build_email(
        subject="x",
        body="x",
        to=["to@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
    )
    calls = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            calls["connect"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def send_message(self, message, *, from_addr, to_addrs):
            calls["send"] = (message, from_addr, to_addrs)

    send_built_email(built, smtp_factory=FakeSmtp)

    assert str(built.message["From"]) == (
        "SmartTest 自动化平台 <fae-qa-auto@amlogic.com>"
    )
    assert calls["connect"] == ("10.18.11.55", 25, 20)
    assert calls["send"] == (
        built.message,
        "fae-qa-auto@amlogic.com",
        ["to@example.com", "cc@example.com", "bcc@example.com"],
    )


def test_sender_wraps_transport_errors_and_preserves_cause():
    built = build_email(subject="x", body="x", to=["to@example.com"])
    failure = OSError("offline")

    def failing_factory(*_args, **_kwargs):
        raise failure

    with pytest.raises(OutlookSendError) as caught:
        send_built_email(built, smtp_factory=failing_factory)

    assert caught.value.__cause__ is failure


def test_sender_logs_safe_stages_and_rejects_partial_delivery(monkeypatch):
    built = build_email(subject="secret subject", body="secret body", to=["private@example.com"])
    records = []
    monkeypatch.setattr("support.outlook.sender.smart_log", lambda message, **kwargs: records.append((message, kwargs.get("extra", {}))))
    class FakeSmtp:
        def __init__(self, *_args, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def send_message(self, *_args, **_kwargs): return {"private@example.com": (550, b"refused private@example.com")}
    with pytest.raises(OutlookSendError) as caught:
        send_built_email(built, smtp_factory=FakeSmtp)
    assert isinstance(caught.value.__cause__, __import__("smtplib").SMTPRecipientsRefused)
    rendered = repr(records)
    assert "connect start" in rendered and "connected" in rendered and "send started" in rendered and "failure" in rendered
    assert "private@example.com" not in rendered and "secret" not in rendered


@pytest.mark.parametrize("failure", [TimeoutError("timed out"), __import__("smtplib").SMTPDataError(554, b"relay rejected")])
def test_sender_failure_logs_safe_type_code_and_message(monkeypatch, failure):
    built = build_email(subject="sensitive", body="body", to=["hidden@example.com"])
    records = []
    monkeypatch.setattr("support.outlook.sender.smart_log", lambda message, **kwargs: records.append((message, kwargs.get("extra", {}))))
    def factory(*_args, **_kwargs): raise failure
    with pytest.raises(OutlookSendError): send_built_email(built, smtp_factory=factory)
    rendered = repr(records)
    assert type(failure).__name__ in rendered
    assert "hidden@example.com" not in rendered and "sensitive" not in rendered


def test_send_email_logs_only_safe_message_counts(monkeypatch):
    records = []
    monkeypatch.setattr(
        "support.outlook.sender.smart_log",
        lambda message, **kwargs: records.append((message, kwargs.get("extra", {}))),
    )
    monkeypatch.setattr("support.outlook.sender.send_built_email", lambda _built: None)

    send_email(
        subject="sensitive subject",
        body="sensitive body",
        to=["hidden@example.com"],
    )

    assert records == [
        (
            "Outlook message built",
            {"recipient_count": 1, "attachment_count": 0, "inline_count": 0},
        )
    ]
    assert "hidden@example.com" not in repr(records)
    assert "sensitive" not in repr(records)


def test_send_email_has_explicit_keyword_only_public_contract():
    signature = inspect.signature(send_email)

    assert tuple(signature.parameters) == (
        "subject",
        "body",
        "to",
        "cc",
        "bcc",
        "sender_name",
        "body_format",
        "attachments",
        "template",
        "base_dir",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError, match="smtp_host"):
        send_email(subject="x", body="x", to=["to@example.com"], smtp_host="other")


def test_daily_report_reuses_public_fixed_outlook_delivery_entrypoint():
    from tool.common.daily_report import service

    assert service.send_email is send_email
