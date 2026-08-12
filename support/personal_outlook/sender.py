from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
from urllib.parse import quote, urlencode
from uuid import uuid4
import winreg

from support.logging import smart_log

from .errors import PersonalOutlookError


@dataclass(frozen=True)
class OutlookState:
    new_installed: bool
    new_window: bool
    classic_registered: bool


def choose_backend(state: OutlookState) -> str:
    if state.new_installed:
        return "new"
    if state.classic_registered:
        raise PersonalOutlookError("only classic Outlook is available; install and start new Outlook")
    raise PersonalOutlookError("new Outlook is not installed")


def window_is_compose(process_name: str, title: str, subject: str) -> bool:
    marker = subject.rsplit(" ", 1)[-1]
    return process_name.casefold() == "olk.exe" and bool(marker) and marker in title


def _window_handle(window) -> int | None:
    value = getattr(getattr(window, "element_info", None), "handle", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


class WindowsOutlookPlatform:
    supports_bcc = True

    def __init__(self, *, wait=time.sleep, foreground_api=None, desktop_factory=None):
        self._wait = wait
        self._foreground_api = foreground_api
        self._desktop_factory = desktop_factory

    def _foreground(self):
        if self._foreground_api is None:
            import win32gui
            self._foreground_api = win32gui
        return self._foreground_api

    def _new_installed(self):
        command = "Get-AppxPackage -Name Microsoft.OutlookForWindows | Select-Object -First 1 -ExpandProperty PackageFullName"
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=15, check=False)
        return result.returncode == 0 and bool(result.stdout.strip())

    def _classic_registered(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Outlook.Application\CLSID"):
                return True
        except OSError:
            return False

    def windows(self):
        try:
            import psutil
            from pywinauto import Desktop
        except ImportError as exc:
            raise PersonalOutlookError("pywinauto and psutil are required for new Outlook delivery") from exc
        found = []
        for window in Desktop(backend="uia").windows():
            try:
                name = psutil.Process(window.element_info.process_id).name()
                title = window.window_text()
            except (OSError, RuntimeError, psutil.Error):
                continue
            if name.casefold() == "olk.exe" and title.strip():
                found.append((window, name, title))
        return found

    def detect_state(self):
        return OutlookState(self._new_installed(), bool(self.windows()), self._classic_registered())

    def open_mailto(self, uri): os.startfile(uri)
    def capture_foreground(self):
        return self._foreground().GetForegroundWindow()
    def restore_foreground(self, handle):
        api = self._foreground()
        if not handle or not api.IsWindow(handle):
            raise PersonalOutlookError(
                "original foreground window is no longer valid"
            )
        try:
            api.SetForegroundWindow(handle)
        except Exception:
            pass
        else:
            if api.GetForegroundWindow() == handle:
                return
        try:
            if self._desktop_factory is None:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")
            else:
                desktop = self._desktop_factory(backend="uia")
            desktop.window(handle=handle).set_focus()
        except Exception as exc:
            raise PersonalOutlookError(
                "unable to restore the original foreground window with native or UIA focus"
            ) from exc
        if api.GetForegroundWindow() != handle:
            raise PersonalOutlookError(
                "UIA focus did not restore the original foreground window"
            )
    def capture_clipboard(self):
        import win32clipboard
        saved = []
        win32clipboard.OpenClipboard()
        try:
            fmt = 0
            while True:
                fmt = win32clipboard.EnumClipboardFormats(fmt)
                if not fmt: break
                try: saved.append((fmt, win32clipboard.GetClipboardData(fmt)))
                except Exception: continue
        finally: win32clipboard.CloseClipboard()
        return saved
    def restore_clipboard(self, saved):
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            for fmt, value in saved: win32clipboard.SetClipboardData(fmt, value)
        finally: win32clipboard.CloseClipboard()
    def put_image(self, path):
        import win32clipboard
        from PIL import Image
        with Image.open(path) as image:
            buffer = io.BytesIO(); image.convert("RGB").save(buffer, "BMP")
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardData(win32clipboard.CF_DIB, buffer.getvalue()[14:])
        finally: win32clipboard.CloseClipboard()
    def wait_for_unique_compose(self, subject, timeout, previous_handles=()):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            matches = [
                item[0] for item in self.windows()
                if (handle := _window_handle(item[0])) is not None
                and handle not in previous_handles
                and window_is_compose(item[1], item[2], subject)
            ]
            if len(matches) > 1: raise PersonalOutlookError("multiple new Outlook drafts match the subject marker")
            if matches: return matches[0]
            time.sleep(0.25)
        raise PersonalOutlookError("new Outlook draft did not appear before timeout")
    def focus(self, window): window.set_focus()
    def paste(self):
        from pywinauto.keyboard import send_keys
        send_keys("^v")
    def _buttons(self, compose):
        return compose.descendants(control_type="Button")

    def _window_open(self, compose_handle):
        if not isinstance(compose_handle, int):
            raise PersonalOutlookError("new Outlook compose window has no valid handle")
        return any(
            _window_handle(item[0]) == compose_handle for item in self.windows()
        )

    @staticmethod
    def _visible(button):
        return button.is_visible()

    @staticmethod
    def _automation_id(button):
        return str(button.element_info.automation_id or "")

    def _primary_buttons(self, compose, buttons=None):
        buttons = self._buttons(compose) if buttons is None else buttons
        return [
            button for button in buttons
            if self._visible(button)
            and "primaryActionButton" in self._automation_id(button)
        ]

    def _confirmation_buttons(self, compose, buttons=None):
        buttons = self._buttons(compose) if buttons is None else buttons
        return [
            button for button in buttons
            if self._visible(button) and button.is_enabled()
            and not self._automation_id(button)
            and button.window_text() == "确定"
        ]

    def _unique_primary(self, compose, *, enabled):
        matches = [
            button for button in self._primary_buttons(compose)
            if button.is_enabled() is enabled
        ]
        if len(matches) != 1:
            raise PersonalOutlookError(
                "new Outlook primary Send control is missing or ambiguous"
            )
        return matches[0]

    def submit_draft(
        self, compose, timeout, compose_handle, on_stage=lambda _stage: None,
    ):
        if not isinstance(compose_handle, int):
            raise PersonalOutlookError("new Outlook compose window has no valid handle")
        deadline = time.monotonic() + timeout
        on_stage("initial_send_invoke")
        while time.monotonic() < deadline:
            if not self._window_open(compose_handle):
                raise PersonalOutlookError(
                    "new Outlook draft closed before Send control became ready"
                )
            primary = [
                button for button in self._primary_buttons(compose)
                if button.is_enabled()
            ]
            if len(primary) > 1:
                raise PersonalOutlookError(
                    "new Outlook primary Send control is ambiguous"
                )
            if len(primary) == 1:
                primary[0].invoke()
                break
            self._wait(0.25)
        else:
            raise PersonalOutlookError(
                "new Outlook primary Send control did not become ready before timeout"
            )
        waiting_for_primary = False
        while time.monotonic() < deadline:
            if not self._window_open(compose_handle):
                on_stage("draft_closed")
                return
            buttons = self._buttons(compose)
            confirmations = self._confirmation_buttons(compose, buttons)
            if len(confirmations) > 1:
                raise PersonalOutlookError(
                    "new Outlook attachment confirmation is ambiguous"
                )
            primary = self._primary_buttons(compose, buttons)
            if len(primary) > 1:
                raise PersonalOutlookError(
                    "new Outlook primary Send control is ambiguous"
                )
            enabled = [button for button in primary if button.is_enabled()]
            if waiting_for_primary:
                if len(enabled) == 1:
                    enabled[0].invoke()
                    waiting_for_primary = False
            elif len(confirmations) == 1:
                on_stage("confirm_handling")
                confirmations[0].invoke()
                waiting_for_primary = True
            self._wait(0.25)
        raise PersonalOutlookError(
            "new Outlook send did not complete before timeout"
        )
    def wait_closed(self, compose_handle, timeout):
        if not isinstance(compose_handle, int):
            raise PersonalOutlookError("new Outlook compose window has no valid handle")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if all(_window_handle(item[0]) != compose_handle for item in self.windows()): return
            time.sleep(0.25)
        raise PersonalOutlookError("send was invoked but the new Outlook draft did not close")


def _mailto(subject, to, cc, bcc):
    query = {"subject": subject}
    if cc: query["cc"] = ";".join(cc)
    if bcc: query["bcc"] = ";".join(bcc)
    return f"mailto:{quote(';'.join(to))}?{urlencode(query, quote_via=quote)}"


def send_email(
    *, subject: str, image_path: str | Path, to, cc=(), bcc=(), timeout=30.0,
    platform=None, logger=smart_log, operation_id=None, clock=time.monotonic,
):
    operation_id = operation_id or uuid4().hex
    started = clock()
    current_stage = "backend_selection"

    def stage(name):
        nonlocal current_stage
        current_stage = name
        logger(
            "Personal Outlook delivery stage",
            domain="support",
            source="personal_outlook",
            extra={
                "operation_id": operation_id,
                "stage": name,
                "elapsed_ms": max(0, round((clock() - started) * 1000)),
            },
        )

    image_path = Path(image_path)
    stage("backend_selection")
    if not image_path.is_file():
        raise PersonalOutlookError(
            "report image does not exist", stage="image_clipboard_paste",
            operation_id=operation_id,
        )
    platform = platform or WindowsOutlookPlatform()
    if bcc and not platform.supports_bcc:
        raise PersonalOutlookError(
            "Bcc cannot be expressed reliably by this new Outlook integration",
            stage=current_stage, operation_id=operation_id,
        )
    try:
        choose_backend(platform.detect_state())
    except PersonalOutlookError as exc:
        exc.stage = current_stage
        exc.operation_id = operation_id
        raise
    except Exception as exc:
        raise PersonalOutlookError(
            "new Outlook backend detection failed",
            stage=current_stage, operation_id=operation_id,
        ) from exc
    foreground = clipboard = None
    failure = None
    try:
        stage("outlook_launch_window")
        foreground = platform.capture_foreground(); clipboard = platform.capture_clipboard()
        previous_handles = {
            handle for item in platform.windows()
            if isinstance(item, tuple)
            and (handle := _window_handle(item[0])) is not None
        }
        platform.open_mailto(_mailto(subject, tuple(to), tuple(cc), tuple(bcc)))
        stage("draft_creation_match")
        compose = platform.wait_for_unique_compose(subject, timeout, previous_handles)
        compose_handle = _window_handle(compose)
        if compose_handle is None:
            raise PersonalOutlookError("new Outlook compose window has no valid handle")
        stage("image_clipboard_paste")
        try:
            platform.put_image(image_path)
            platform.focus(compose)
            platform.paste()
        except Exception as exc:
            raise PersonalOutlookError("unable to paste the report image into new Outlook") from exc
        platform.submit_draft(compose, timeout, compose_handle, stage)
    except Exception as exc:
        failure = exc
        failure_stage = current_stage
    finally:
        stage("restore_state")
        restore_errors = []
        if clipboard is not None:
            try: platform.restore_clipboard(clipboard)
            except Exception as exc: restore_errors.append(f"clipboard ({type(exc).__name__})")
        if foreground is not None:
            try: platform.restore_foreground(foreground)
            except Exception as exc: restore_errors.append(f"foreground window ({type(exc).__name__})")
        if restore_errors:
            failure = PersonalOutlookError(
                "desktop state restoration failed: " + ", ".join(restore_errors),
                stage="restore_state", operation_id=operation_id,
            )
            failure_stage = "restore_state"
    if failure is not None:
        if isinstance(failure, PersonalOutlookError):
            failure.stage = failure.stage or failure_stage
            failure.operation_id = failure.operation_id or operation_id
            raise failure
        raise PersonalOutlookError(
            "Personal Outlook delivery failed",
            stage=failure_stage, operation_id=operation_id,
        ) from failure
