from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
import re
import signal

import uiautomator2 as u2

from tools.logging import smart_log


class UiautomatorTool:
    """
    Per-device uiautomator2 session wrapper used by DUT UI feature flows.
    """

    def __init__(self, serialnumber: str, type_: str = "u2"):
        if type_ != "u2":
            raise ValueError(f"Unsupported type: {type_}. Only 'u2' is supported.")
        self.serial = serialnumber
        self.d2 = u2.connect(serialnumber)
        smart_log(f"Connected to device: {serialnumber}", level="info")

    def wait(
        self,
        timeout: float = 5.0,
        *,
        text: Optional[str] = None,
        resourceId: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> bool:
        selector_kwargs = {}
        if text is not None:
            selector_kwargs["text"] = text
        if resourceId is not None:
            selector_kwargs["resourceId"] = resourceId
        if description is not None:
            selector_kwargs["description"] = description
        selector_kwargs.update(kwargs)

        smart_log(f"Looking for UI element with selector: {selector_kwargs}", level="info")
        selector = self.d2(**selector_kwargs)
        if selector.wait(timeout=timeout):
            selector.click()
            return True

        smart_log(f"Element NOT found within {timeout}s. Current UI hierarchy:", level="warning")
        try:
            hierarchy = self.d2.dump_hierarchy()
            root = ET.fromstring(hierarchy)
            texts = sorted(
                value
                for node in root.iter("node")
                for value in [node.attrib.get("text", "").strip()]
                if value
            )
            smart_log(f"Found text elements on screen: {texts}", level="warning")
        except Exception as exc:
            smart_log(f"Failed to dump UI hierarchy: {exc}", level="error")
        return False

    def click(self, x: int, y: int):
        self.d2.click(x, y)

    def swipe(self, fx: int, fy: int, tx: int, ty: int, duration: float = 0.1):
        self.d2.swipe(fx, fy, tx, ty, duration)

    def press(self, key: str):
        self.d2.press(key)

    def screenshot(self, filename: str = "screenshot.png"):
        self.d2.screenshot(filename)
        smart_log(f"Screenshot saved: {filename}", level="info")

    def dump(self) -> str:
        return self.d2.dump_hierarchy()


def launch_youtube_tv_and_search(dut, logdir: Path, query: str = "NASA"):
    """Launch YouTube TV and search for a channel on Android TV."""
    try:
        dut.run_device_shell(
            "am start -n "
            "com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity"
        )
        time.sleep(8)
        for _ in range(4):
            dut.keyevent("KEYCODE_DPAD_RIGHT")
            time.sleep(0.5)
        dut.keyevent("KEYCODE_ENTER")
        time.sleep(2)
        dut.text(query)
        time.sleep(1)
        dut.keyevent("KEYCODE_ENTER")
        time.sleep(5)
        smart_log("YouTube TV search completed.", level="info")
        for _ in range(3):
            dut.home()
            time.sleep(1)
        return True
    except Exception as exc:
        smart_log(f"YouTube TV automation failed: {exc}", level="error")
        return False


def enter_wifi_activity(dut) -> None:
    dut.app_stop(dut.SETTING_ACTIVITY_TUPLE[0])
    smart_log('Enter wifi activity', level="info")
    dut.start_activity(*dut.SETTING_ACTIVITY_TUPLE)
    dut.wait_element('Network & Internet', 'text')
    dut.wait_and_tap('Network & Internet', 'text')
    dut.uiautomator_dump()
    if 'Available networks' not in dut.get_dump_info():
        dut.wait_and_tap('Wi-Fi', 'text')
    dut.wait_element('Wi-Fi', 'text')


def enter_hotspot(dut) -> None:
    dut.start_activity(*dut.SETTING_ACTIVITY_TUPLE)
    dut.wait_element('Network & Internet', 'text')
    dut.wait_and_tap('Network & Internet', 'text')
    for _ in range(8):
        dut.keyevent(20)
    dut.wait_and_tap('HotSpot', 'text')


def open_hotspot(dut) -> None:
    enter_hotspot(dut)
    dut.wait_element('Portable HotSpot Enabled', 'text')
    dut.uiautomator_dump()
    if not re.findall(dut.OPEN_INFO, dut.get_dump_info(), re.S):
        dut.wait_and_tap('Portable HotSpot Enabled', 'text')
        dut.get_dump_info()
    times = 0
    while not re.findall(dut.OPEN_INFO, dut.get_dump_info(), re.S):
        time.sleep(1)
        dut.uiautomator_dump()
        times += 1
        if times > 5:
            raise EnvironmentError("Can't open hotspot")


def close_hotspot(dut) -> None:
    kill_setting(dut)
    enter_hotspot(dut)
    dut.wait_element('Portable HotSpot Enabled', 'text')
    dut.uiautomator_dump()
    if re.findall(dut.OPEN_INFO, dut.get_dump_info(), re.S):
        dut.wait_and_tap('Portable HotSpot Enabled', 'text')
        dut.get_dump_info()
    times = 0
    while re.findall(dut.OPEN_INFO, dut.get_dump_info(), re.S):
        time.sleep(1)
        dut.uiautomator_dump()
        times += 1
        if times > 5:
            raise EnvironmentError("Can't close hotspot")


def kill_setting(dut) -> None:
    dut.app_stop(dut.SETTING_ACTIVITY_TUPLE[0])


def kill_moresetting(dut) -> None:
    for _ in range(5):
        dut.keyevent(4)
    kill_setting(dut)


def factory_reset_ui(dut) -> None:
    dut.start_activity(*dut.SETTING_ACTIVITY_TUPLE)
    dut.wait_and_tap('Device Preferences', 'text')
    dut.wait_and_tap('About', 'text')
    dut.wait_and_tap('Factory reset', 'text')
    time.sleep(1)
    dut.keyevent(20)
    dut.keyevent(20)
    dut.keyevent(23)
    time.sleep(1)
    dut.keyevent(20)
    dut.keyevent(20)
    dut.keyevent(23)
    time.sleep(5)
    assert dut.serialnumber not in dut.checkoutput_term('adb devices'), 'Factory reset fail'
    dut.wait_devices()
    smart_log('device done', level="info")


def wait_for_launcher(dut) -> None:
    log = dut.popen("logcat")
    while True:
        try:
            line = log.stdout.readline()
        except UnicodeDecodeError:
            continue
        if "Displayed com.google.android.tvlauncher/.MainActivity" in line:
            time.sleep(1)
            smart_log("wait for launcher", level="info")
            break
    log.terminate()
    log.send_signal(signal.SIGINT)
