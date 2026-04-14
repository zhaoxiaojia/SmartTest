# uiautomator_tool.py
import logging
import time, subprocess
import uiautomator2 as u2
from typing import Optional, Union


class UiautomatorTool:
    """
    A wrapper around uiautomator2 for common UI automation tasks.
    Supports per-device instance (NOT singleton).
    """

    def __init__(self, serialnumber: str, type_: str = "u2"):
        """
        Initialize connection to Android device.

        Args:
            serialnumber: ADB serial number (e.g., '192.168.1.100:5555' or 'emulator-5554')
            type_: Only "u2" is supported currently.
        """
        if type_ != "u2":
            raise ValueError(f"Unsupported type: {type_}. Only 'u2' is supported.")

        self.serial = serialnumber
        self.d2 = u2.connect(serialnumber)
        logging.info(f"Connected to device: {serialnumber}")

    def wait(
            self,
            timeout: float = 5.0,
            *,
            text: Optional[str] = None,
            resourceId: Optional[str] = None,
            description: Optional[str] = None,
            **kwargs
    ) -> bool:
        selector_kwargs = {}
        if text is not None:
            selector_kwargs["text"] = text
        if resourceId is not None:
            selector_kwargs["resourceId"] = resourceId
        if description is not None:
            selector_kwargs["description"] = description
        selector_kwargs.update(kwargs)

        # 🔍 DEBUG: 打印实际传入的 selector 参数
        logging.info(f"Looking for UI element with selector: {selector_kwargs}")

        selector = self.d2(**selector_kwargs)
        if selector.wait(timeout=timeout):
            selector.click()
            return True
        else:
            # 🔍 DEBUG: 元素未找到时，dump 当前 UI 层级到日志
            logging.warning(f"Element NOT found within {timeout}s. Current UI hierarchy:")
            try:
                hierarchy = self.d2.dump_hierarchy()
                # 提取所有 TextView 的 text 内容用于快速查看
                import xml.etree.ElementTree as ET
                root = ET.fromstring(hierarchy)
                texts = set()
                for node in root.iter("node"):
                    t = node.attrib.get("text", "").strip()
                    if t:
                        texts.add(t)
                logging.warning(f"Found text elements on screen: {sorted(texts)}")
            except Exception as e:
                logging.error(f"Failed to dump UI hierarchy: {e}")

            return False

    def wait_until_disappear(
            self,
            timeout: float = 5.0,
            *,
            text: Optional[str] = None,
            resourceId: Optional[str] = None,
            description: Optional[str] = None,
            **kwargs
    ) -> bool:
        """Wait until the specified element disappears (or never appears)."""
        selector_kwargs = {}
        if text is not None:
            selector_kwargs["text"] = text
        if resourceId is not None:
            selector_kwargs["resourceId"] = resourceId
        if description is not None:
            selector_kwargs["description"] = description
        selector_kwargs.update(kwargs)

        logging.info(f"Waiting for element to disappear: {selector_kwargs}")

        end_time = time.time() + timeout
        while time.time() < end_time:
            if not self.d2(**selector_kwargs).exists():
                logging.info("Element has disappeared.")
                return True
            time.sleep(0.5)

        logging.warning(f"Element still exists after {timeout}s: {selector_kwargs}")
        return False

    def send_keys_to(
            self,
            text: Optional[str] = None,
            resourceId: Optional[str] = None,
            clear: bool = True,
            value: str = ""
    ) -> bool:
        """
        Send text to an editable field.

        Args:
            text/resourceId: How to locate the input field.
            clear: Whether to clear before typing.
            value: Text to input.

        Returns:
            True if successful.
        """
        selector_kwargs = {"text": text} if text else {"resourceId": resourceId}
        if not any(selector_kwargs.values()):
            raise ValueError("Either 'text' or 'resourceId' must be provided.")

        selector = self.d2(**selector_kwargs)
        if selector.exists():
            if clear:
                selector.clear_text()
            selector.set_text(value)
            return True
        else:
            logging.error(f"Input field not found: {selector_kwargs}")
            return False

    # --- Additional useful methods ---
    def click(self, x: int, y: int):
        """Click at absolute coordinates."""
        self.d2.click(x, y)

    def swipe(self, fx: int, fy: int, tx: int, ty: int, duration: float = 0.1):
        """Swipe from (fx, fy) to (tx, ty)."""
        self.d2.swipe(fx, fy, tx, ty, duration)

    def press(self, key: str):
        """Press a hardware key (e.g., 'home', 'back', 'recent')."""
        self.d2.press(key)

    def screenshot(self, filename: str = "screenshot.png"):
        """Take a screenshot."""
        self.d2.screenshot(filename)
        logging.info(f"Screenshot saved: {filename}")

    def dump(self) -> str:
        """Get current UI hierarchy as XML string."""
        return self.d2.dump_hierarchy()

    def handle_complete_action_dialog(self, timeout: float = 5.0) -> bool:
        """
        Handle the 'Complete action using' dialog if it appears.
        Returns True if dialog was handled, False if not present.
        """
        if self.d2(text="Complete action using").exists(timeout=timeout):
            logging.info("Detected 'Complete action using' dialog. Handling...")

            # Step 1: Click on the 'Settings' option (the actual app to use)
            settings_option = self.d2(text="Settings")
            if settings_option.exists():
                settings_option.click()
                logging.info("Clicked 'Settings' in chooser.")
            else:
                logging.warning("'Settings' option not found in chooser.")

            time.sleep(0.5)

            # Step 2: Click 'Just once'
            just_once = self.d2(text="Just once")
            if just_once.exists():
                just_once.click()
                logging.info("Clicked 'Just once'.")
                return True
            else:
                logging.warning("'Just once' button not found.")
                # 尝试点击 'Always' 作为 fallback（不推荐，但能继续）
                always_btn = self.d2(text="Always")
                if always_btn.exists():
                    always_btn.click()
                    logging.info("Fallback: clicked 'Always'.")
                    return True

        return False

    # uiautomator_tool.py 中的 launch_system_settings 方法
    # uiautomator_tool.py
    def launch_system_settings(self):
        import subprocess, time, logging
        logging.info(f"Launching standard Android Settings for {self.serial}")

        # 启动 AOSP Settings 主页（通常包含 Wi-Fi）
        cmd = f"adb -s {self.serial} shell am start -n com.android.settings/.Settings"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            time.sleep(2)
            return

        # 回退：使用通用 intent
        cmd = f"adb -s {self.serial} shell am start -a android.settings.SETTINGS"
        subprocess.run(cmd, shell=True, check=True)
        time.sleep(2)