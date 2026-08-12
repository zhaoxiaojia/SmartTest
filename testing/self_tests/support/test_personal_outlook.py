from pathlib import Path

import pytest

from support.personal_outlook import (
    OutlookState,
    PersonalOutlookError,
    choose_backend,
    send_email,
)
from support.personal_outlook.sender import WindowsOutlookPlatform, window_is_compose
from support.report.image import html_page


def _fake_window(handle=42):
    return type(
        "Window", (),
        {"element_info": type("Info", (), {"handle": handle})()},
    )()


def test_new_outlook_is_selected_when_classic_is_also_registered():
    assert choose_backend(OutlookState(True, True, True)) == "new"


def test_installed_new_outlook_is_selected_when_no_window_is_running():
    assert choose_backend(OutlookState(True, False, True)) == "new"


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (OutlookState(False, False, True), "classic Outlook"),
        (OutlookState(False, False, False), "new Outlook is not installed"),
    ],
)
def test_unavailable_outlook_states_have_actionable_errors(state, message):
    with pytest.raises(PersonalOutlookError, match=message):
        choose_backend(state)


def test_send_routes_recipients_and_restores_desktop_state(tmp_path):
    image = tmp_path / "report.png"
    image.write_bytes(b"png")
    events = []
    records = []
    compose = _fake_window()

    class Platform:
        supports_bcc = True
        def detect_state(self): return OutlookState(True, False, True)
        def windows(self): events.append(("windows", ())); return []
        def open_mailto(self, uri): events.append(("mailto", uri))
        def wait_for_unique_compose(self, *_args): return compose
        def capture_foreground(self): return "original-window"
        def capture_clipboard(self): return "original-clipboard"
        def put_image(self, path): events.append(("image", path))
        def focus(self, window): events.append(("focus", window))
        def paste(self): events.append(("paste",))
        def submit_draft(self, window, _timeout, _handle, on_stage):
            on_stage("initial_send_invoke")
            events.extend((("send", window), ("closed",)))
            on_stage("draft_closed")
        def restore_clipboard(self, value): events.append(("clipboard", value))
        def restore_foreground(self, value): events.append(("foreground", value))

    send_email(
        subject="Daily Report marker", image_path=image,
        to=("to@example.com",), cc=("cc@example.com",),
        bcc=("bcc@example.com",), platform=Platform(), timeout=1,
        logger=lambda message, **kwargs: records.append((message, kwargs)),
        operation_id="operation-1",
    )

    assert events[0] == ("windows", ())
    assert events[1][0] == "mailto"
    uri = events[1][1]
    assert "to%40example.com" in uri
    assert "cc=cc%40example.com" in uri
    assert "bcc=bcc%40example.com" in uri
    assert events[2:7] == [
        ("image", image),
        ("focus", compose),
        ("paste",),
        ("send", compose),
        ("closed",),
    ]
    assert events[-2:] == [
        ("clipboard", "original-clipboard"),
        ("foreground", "original-window"),
    ]
    stage_records = [item for item in records if item[0] == "Personal Outlook delivery stage"]
    assert [item[1]["extra"]["stage"] for item in stage_records] == [
        "backend_selection", "outlook_launch_window", "draft_creation_match",
        "image_clipboard_paste", "initial_send_invoke", "draft_closed",
        "restore_state",
    ]
    serialized = repr(records)
    for secret in (
        "to@example.com", "cc@example.com", "bcc@example.com",
        "Daily Report marker", str(image), "original-clipboard",
    ):
        assert secret not in serialized
    assert all(item[1]["extra"]["operation_id"] == "operation-1" for item in records)


def test_send_restores_clipboard_and_foreground_after_failure(tmp_path):
    image = tmp_path / "report.png"; image.write_bytes(b"png")
    restored = []
    compose = _fake_window()
    class Platform:
        supports_bcc = True
        def detect_state(self): return OutlookState(True, True, False)
        def windows(self): return []
        def open_mailto(self, _uri): pass
        def wait_for_unique_compose(self, *_args): return compose
        def capture_foreground(self): return 42
        def capture_clipboard(self): return b"clipboard"
        def put_image(self, _path): raise OSError("clipboard locked")
        def restore_clipboard(self, value): restored.append(("clipboard", value))
        def restore_foreground(self, value): restored.append(("foreground", value))
    records = []
    with pytest.raises(PersonalOutlookError, match="paste the report image") as raised:
        send_email(
            subject="Report", image_path=image, to=("a@b.com",),
            platform=Platform(), operation_id="failure-1",
            logger=lambda message, **kwargs: records.append((message, kwargs)),
        )
    assert raised.value.stage == "image_clipboard_paste"
    assert raised.value.operation_id == "failure-1"
    assert records[-1][1]["extra"]["stage"] == "restore_state"
    assert restored == [("clipboard", b"clipboard"), ("foreground", 42)]


def test_send_restores_desktop_when_uia_submission_fails(tmp_path):
    image = tmp_path / "report.png"; image.write_bytes(b"png")
    restored = []
    compose = _fake_window()
    class Platform:
        supports_bcc = True
        def detect_state(self): return OutlookState(True, False, False)
        def windows(self): return []
        def open_mailto(self, _uri): pass
        def wait_for_unique_compose(self, *_args): return compose
        def capture_foreground(self): return 42
        def capture_clipboard(self): return b"clipboard"
        def put_image(self, _path): pass
        def focus(self, _window): pass
        def paste(self): pass
        def submit_draft(self, *_args): raise PersonalOutlookError("confirmation is ambiguous")
        def restore_clipboard(self, value): restored.append(("clipboard", value))
        def restore_foreground(self, value): restored.append(("foreground", value))
    with pytest.raises(PersonalOutlookError, match="confirmation is ambiguous"):
        send_email(subject="Report", image_path=image, to=("a@b.com",), platform=Platform())
    assert restored == [("clipboard", b"clipboard"), ("foreground", 42)]


def test_bcc_fails_before_draft_when_platform_cannot_express_it(tmp_path):
    image = tmp_path / "report.png"; image.write_bytes(b"png")
    class Platform:
        supports_bcc = False
        def detect_state(self): raise AssertionError("must fail before detection")
    with pytest.raises(PersonalOutlookError, match="Bcc"):
        send_email(subject="Report", image_path=image, to=("a@b.com",), bcc=("x@y.com",), platform=Platform())


def test_compose_match_requires_new_outlook_and_subject_marker():
    assert window_is_compose("olk.exe", "Daily Report unique-marker", "Daily Report unique-marker")
    assert not window_is_compose("OUTLOOK.EXE", "Daily Report unique-marker", "Daily Report unique-marker")
    assert not window_is_compose("olk.exe", "Inbox", "Daily Report unique-marker")


def test_multiple_matching_new_outlook_drafts_are_rejected(monkeypatch):
    platform = WindowsOutlookPlatform()
    windows = [
        (type("Window", (), {"element_info": type("Info", (), {"handle": handle})()})(), "olk.exe", "Daily Report marker")
        for handle in (10, 11)
    ]
    monkeypatch.setattr(platform, "windows", lambda: windows)
    with pytest.raises(PersonalOutlookError, match="multiple new Outlook drafts"):
        platform.wait_for_unique_compose("Daily Report marker", 0.1)


class _Button:
    def __init__(self, name, automation_id, enabled=True):
        self._name = name
        self._automation_id = automation_id
        self._enabled = enabled
        self.invocations = 0

    def window_text(self): return self._name
    def is_visible(self): return True
    def is_enabled(self): return self._enabled
    def invoke(self): self.invocations += 1
    @property
    def element_info(self):
        return type(
            "Info", (),
            {"automation_id": self._automation_id, "control_type": "Button"},
        )()


def test_uia_submit_closes_after_direct_primary_send():
    send = _Button("Send", "primaryActionButton")
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    platform._buttons = lambda _compose: [send]
    states = iter((True, False))
    platform._window_open = lambda _compose: next(states)

    platform.submit_draft(object(), 1, 42)

    assert send.invocations == 1


def test_initial_primary_send_waits_until_uia_control_is_ready():
    send = _Button("Send", "primaryActionButton")
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    rounds = iter(([], [], [send]))
    platform._buttons = lambda _compose: next(rounds)
    states = iter((True, True, True, False))
    platform._window_open = lambda _handle: next(states)

    platform.submit_draft(object(), 1, 42)

    assert send.invocations == 1


def test_uia_submit_confirms_modal_that_replaces_primary_then_sends_again():
    send = _Button("Send", "primaryActionButton")
    confirm = _Button("确定", "")
    events = []
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    rounds = iter(([send], [confirm], [send]))
    platform._buttons = lambda _compose: next(rounds)
    open_states = iter((True, True, True, False))
    platform._window_open = lambda _compose: next(open_states)
    original_invoke = confirm.invoke
    def invoke_confirm():
        events.append("confirm"); original_invoke(); send._enabled = True
    confirm.invoke = invoke_confirm
    first = True
    original_send = send.invoke
    def invoke_send():
        nonlocal first
        events.append("send")
        original_send()
        if first:
            send._enabled = False; first = False
    send.invoke = invoke_send

    platform.submit_draft(object(), 1, 42)

    assert send.invocations == 2
    assert confirm.invocations == 1
    assert events == ["send", "confirm", "send"]


def test_uia_submit_repeats_confirmation_until_compose_closes():
    send = _Button("Send", "primaryActionButton")
    confirm = _Button("确定", "")
    events = []
    stages = []
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    rounds = iter(([send], [confirm], [send], [confirm], [send]))
    platform._buttons = lambda _compose: next(rounds)
    open_states = iter((True, True, True, True, True, False))
    platform._window_open = lambda _compose: next(open_states)
    original_confirm = confirm.invoke
    def invoke_confirm():
        events.append("confirm"); original_confirm(); send._enabled = True
    confirm.invoke = invoke_confirm
    original_send = send.invoke
    def invoke_send():
        events.append("send"); original_send(); send._enabled = False
    send.invoke = invoke_send

    platform.submit_draft(object(), 1, 42, stages.append)
    events.append("close")

    assert events == ["send", "confirm", "send", "confirm", "send", "close"]
    assert stages == [
        "initial_send_invoke", "confirm_handling", "confirm_handling",
        "draft_closed",
    ]


@pytest.mark.parametrize(
    ("confirm_count", "message"),
    ((0, "did not complete"), (2, "confirmation")),
)
def test_uia_submit_rejects_missing_or_ambiguous_confirmation(confirm_count, message):
    send = _Button("Send", "primaryActionButton")
    confirmations = [_Button("确定", "") for _ in range(confirm_count)]
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    def buttons(_compose):
        if send.invocations: send._enabled = False
        return [send, *confirmations]
    platform._buttons = buttons
    platform._window_open = lambda _compose: True

    with pytest.raises(PersonalOutlookError, match=message):
        platform.submit_draft(object(), 0.001, 42)


def test_transient_none_window_handle_is_skipped_while_tracking_compose():
    def window(handle):
        return type(
            "Window", (),
            {"element_info": type("Info", (), {"handle": handle})()},
        )()
    compose = window(7)
    transient = window(None)
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    snapshots = iter((
        [(transient, "olk.exe", "Dialog"), (compose, "olk.exe", "Draft")],
        [(transient, "olk.exe", "Dialog"), (compose, "olk.exe", "Draft")],
        [(transient, "olk.exe", "Dialog")],
    ))
    platform.windows = lambda: next(snapshots)

    assert platform._window_open(7) is True
    platform.wait_closed(7, 1)


def test_submit_uses_stable_handle_when_original_wrapper_loses_handle():
    info = type("Info", (), {"handle": 42})()
    compose = type("Compose", (), {"element_info": info})()
    send = _Button("Send", "primaryActionButton")
    platform = WindowsOutlookPlatform(wait=lambda _seconds: None)
    platform._buttons = lambda _compose: [send]
    window_rounds = iter(([(compose, "olk.exe", "Draft")], []))
    platform.windows = lambda: next(window_rounds)
    original_invoke = send.invoke
    def invoke_send():
        original_invoke(); info.handle = None
    send.invoke = invoke_send

    platform.submit_draft(compose, 1, 42)

    assert send.invocations == 1


def test_stable_handle_stays_open_through_fresh_window_wrapper():
    stale_info = type("Info", (), {"handle": None})()
    stale = type("Window", (), {"element_info": stale_info})()
    fresh_info = type("Info", (), {"handle": 42})()
    fresh = type("Window", (), {"element_info": fresh_info})()
    platform = WindowsOutlookPlatform()
    platform.windows = lambda: [
        (stale, "olk.exe", "Dialog"),
        (fresh, "olk.exe", "Draft"),
    ]

    assert platform._window_open(42) is True


def test_restore_foreground_accepts_verified_native_success():
    class Api:
        foreground = 1
        def IsWindow(self, handle): return handle == 42
        def SetForegroundWindow(self, handle): self.foreground = handle
        def GetForegroundWindow(self): return self.foreground
    api = Api()
    platform = WindowsOutlookPlatform(foreground_api=api)

    platform.restore_foreground(42)

    assert api.foreground == 42


def test_restore_foreground_uses_verified_uia_fallback_after_native_failure():
    events = []
    class Api:
        foreground = 1
        def IsWindow(self, _handle): return True
        def SetForegroundWindow(self, _handle): raise OSError("native denied")
        def GetForegroundWindow(self): return self.foreground
    api = Api()
    class Window:
        def set_focus(self): events.append("uia"); api.foreground = 42
    desktop = type("Desktop", (), {"window": lambda _self, **_kwargs: Window()})()
    platform = WindowsOutlookPlatform(
        foreground_api=api, desktop_factory=lambda **_kwargs: desktop,
    )

    platform.restore_foreground(42)

    assert events == ["uia"] and api.foreground == 42


@pytest.mark.parametrize("fallback_fails", (True, False))
def test_restore_foreground_reports_fallback_failure_or_verification_mismatch(fallback_fails):
    class Api:
        def IsWindow(self, _handle): return True
        def SetForegroundWindow(self, _handle): raise OSError("native denied")
        def GetForegroundWindow(self): return 7
    class Window:
        def set_focus(self):
            if fallback_fails: raise RuntimeError("UIA denied")
    desktop = type("Desktop", (), {"window": lambda _self, **_kwargs: Window()})()
    platform = WindowsOutlookPlatform(
        foreground_api=Api(), desktop_factory=lambda **_kwargs: desktop,
    )

    with pytest.raises(PersonalOutlookError, match="foreground window"):
        platform.restore_foreground(42)


def test_html_page_renderer_requests_one_full_page_screenshot(monkeypatch, tmp_path):
    source = tmp_path / "report.html"
    source.write_text("<html></html>", "utf-8")
    output = tmp_path / "report.png"
    calls = []
    class Page:
        async def goto(self, uri, **kwargs): calls.append(("goto", uri, kwargs))
        async def evaluate(self, expression): calls.append(("evaluate", expression))
        async def screenshot(self, **kwargs): calls.append(("screenshot", kwargs))
        async def close(self): calls.append(("page-close",))
    async def async_page(): return Page()
    class Runtime:
        async def context(self, *_args):
            return type("Session", (), {"new_page": lambda _self: async_page()})()
        async def close(self): calls.append(("runtime-close",))
    monkeypatch.setattr(html_page, "BrowserRuntime", lambda **_kwargs: Runtime())

    assert html_page.render_html_page_image(source, output) == output
    assert ("screenshot", {"path": str(output), "full_page": True}) in calls
