from __future__ import annotations

from testing.tool.dut_tool.features.base import FeatureBase
import uiautomator2 as u2
import logging, subprocess
import time,re,os, tempfile,time
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple, Any, Set

class UiautomatorTool:
    """
    Per-device uiautomator2 session wrapper used by DUT UI feature flows.
    """

    def __init__(self, serialnumber: str, type_: str = "u2"):
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

        logging.info(f"Looking for UI element with selector: {selector_kwargs}")

        selector = self.d2(**selector_kwargs)
        if selector.wait(timeout=timeout):
            selector.click()
            return True

        logging.warning(f"Element NOT found within {timeout}s. Current UI hierarchy:")
        try:
            hierarchy = self.d2.dump_hierarchy()
            root = ET.fromstring(hierarchy)
            texts = set()
            for node in root.iter("node"):
                value = node.attrib.get("text", "").strip()
                if value:
                    texts.add(value)
            logging.warning(f"Found text elements on screen: {sorted(texts)}")
        except Exception as exc:
            logging.error(f"Failed to dump UI hierarchy: {exc}")
        return False

    def wait_until_disappear(
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
        value: str = "",
    ) -> bool:
        selector_kwargs = {"text": text} if text else {"resourceId": resourceId}
        if not any(selector_kwargs.values()):
            raise ValueError("Either 'text' or 'resourceId' must be provided.")

        selector = self.d2(**selector_kwargs)
        if selector.exists():
            if clear:
                selector.clear_text()
            selector.set_text(value)
            return True
        logging.error(f"Input field not found: {selector_kwargs}")
        return False

    def click(self, x: int, y: int):
        self.d2.click(x, y)

    def swipe(self, fx: int, fy: int, tx: int, ty: int, duration: float = 0.1):
        self.d2.swipe(fx, fy, tx, ty, duration)

    def press(self, key: str):
        self.d2.press(key)

    def screenshot(self, filename: str = "screenshot.png"):
        self.d2.screenshot(filename)
        logging.info(f"Screenshot saved: {filename}")

    def dump(self) -> str:
        return self.d2.dump_hierarchy()

    def handle_complete_action_dialog(self, timeout: float = 5.0) -> bool:
        if self.d2(text="Complete action using").exists(timeout=timeout):
            logging.info("Detected 'Complete action using' dialog. Handling...")

            settings_option = self.d2(text="Settings")
            if settings_option.exists():
                settings_option.click()
                logging.info("Clicked 'Settings' in chooser.")
            else:
                logging.warning("'Settings' option not found in chooser.")

            time.sleep(0.5)

            just_once = self.d2(text="Just once")
            if just_once.exists():
                just_once.click()
                logging.info("Clicked 'Just once'.")
                return True

            logging.warning("'Just once' button not found.")
            always_btn = self.d2(text="Always")
            if always_btn.exists():
                always_btn.click()
                logging.info("Fallback: clicked 'Always'.")
                return True

        return False

    def launch_system_settings(self):
        logging.info(f"Launching standard Android Settings for {self.serial}")

        command = f"adb -s {self.serial} shell am start -n com.android.settings/.Settings"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            time.sleep(2)
            return

        command = f"adb -s {self.serial} shell am start -a android.settings.SETTINGS"
        subprocess.run(command, shell=True, check=True)
        time.sleep(2)

class DeviceUiFeature(FeatureBase):
    def u(self, type="u2"):
        return self._u_impl(type=type)

    def _u_impl(self, *, type="u2"):
        raise NotImplementedError

    def uiautomator_dump(self, filepath="", uiautomator_type="u2"):
        return self._uiautomator_dump_impl(filepath=filepath, uiautomator_type=uiautomator_type)

    def _uiautomator_dump_impl(self, *, filepath="", uiautomator_type="u2"):
        raise NotImplementedError

    def wifi_is_valid_ssid(self, text: str) -> bool:
        """Check valid SSID"""
        clean = text.strip()
        if not clean or len(clean) > 32 or len(clean) < 1:
            return False
        lower_clean = clean.lower()
        # invalid SSID list
        non_ssid_keywords: Set[str] = {
            "see all", "add network", "saved networks", "connected", "wlan", "wi-fi",
            "network & internet", "other options", "scanning always available", "settings",
            "hotspot", "internet", "preferences", "more", "turn on wi-fi", "off", "on",
            "toggle", "scan", "search", "available networks", "no networks found",
            "airplane mode", "no sim", "calls & sms", "data saver",
            "scanning...", "quick connect", "add new network", "options", "share",
        }
        if lower_clean in non_ssid_keywords:
            return False
        if clean.isdigit():
            return False
        if any(c in clean for c in ["\n", "\t", ":", "...", '"', "'"]):
            return False
        return True

    @staticmethod
    def is_wifi_network_saved(serial: str, ssid: str, timeout: int = 10) -> bool:
        """
        Check if a Wi-Fi network (by SSID) is in 'Saved' state on the device.

        This function queries the system's Wi-Fi configuration via 'dumpsys wifi'
        and checks for the presence of the SSID in the output, which indicates that
        the network credentials are stored, regardless of its current connection or
        enabled/disabled status.

        Args:
            serial (str): The ADB serial number of the target device.
            ssid (str): The SSID of the Wi-Fi network to check.
            timeout (int): Timeout for the ADB command execution in seconds.

        Returns:
            bool: True if the network is saved, False otherwise.
        """
        # Construct the precise grep command based on observed dumpsys format
        # Note: The format in dumpsys uses 'SSID: "..."', not 'SSID="..."'.
        escaped_ssid = ssid.replace('"', '\\"')  # Escape quotes in SSID if any
        cmd = f"adb -s {serial} shell \"dumpsys wifi | grep 'SSID: \\\"{escaped_ssid}\\\"'\""

        logging.debug(f"Checking if SSID '{ssid}' is saved with command: {cmd}")

        try:
            output = DeviceUiFeature._run_adb_capture_output(cmd, timeout=timeout)
            # If the grep finds a match, stdout will contain the line; otherwise, it's empty.
            is_saved = len(output.strip()) > 0
            logging.info(f"SSID '{ssid}' is {'Saved' if is_saved else 'NOT Saved'} on {serial}.")
            return is_saved
        except Exception as e:
            logging.error(f"Exception while checking saved state for SSID '{ssid}': {e}")
            return False

    @staticmethod
    def _go_to_home(serial: str, timeout: int = 5) -> bool:
        """
        Return to device home screen (Launcher) via ADB Intent.

        This is more reliable than KEYCODE_HOME on vendor-customized ROMs.

        Args:
            serial (str): Device serial number.
            timeout (int): Command timeout in seconds.

        Returns:
            bool: True if command executed successfully, False otherwise.
        """
        try:
            cmd = [
                "adb", "-s", serial, "shell",
                "am", "start",
                "-a", "android.intent.action.MAIN",
                "-c", "android.intent.category.HOME"
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                logging.info(f"鉁?Successfully returned to home screen on {serial}")
                return True
            else:
                logging.error(f"鉂?Failed to go home on {serial}: {result.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            logging.error(f"鈴?Timeout while trying to go home on {serial}")
            return False
        except Exception as e:
            logging.exception(f"馃挜 Exception in _go_to_home on {serial}: {e}")
            return False

    @staticmethod
    def _open_wifi_settings_page(serial: str) -> bool:
        """
        Open Android Wi-Fi Settings page via ADB.

        Args:
            serial (str): Device serial number.

        Returns:
            bool: True if command executed successfully, False otherwise.
        """
        try:
            success = DeviceUiFeature._go_to_home(serial)

            cmd = f"adb -s {serial} shell am start -a android.settings.WIFI_SETTINGS"
            logging.debug(f"Executing: {cmd}")
            ret = os.system(cmd)
            # os.system returns 0 on success
            if ret == 0:
                logging.info(f"Successfully opened Wi-Fi settings page on {serial}")
                return True
            else:
                logging.error(f"Failed to open Wi-Fi settings page on {serial}, exit code: {ret}")
                return False
        except Exception as e:
            logging.exception(f"Exception while opening Wi-Fi settings on {serial}: {e}")
            return False

    def wifi_wait_for_networks(self, timeout: int = 12) -> List[str]:
        """
        Wait for real Wi-Fi SSIDs to appear on screen.
        Returns list of detected SSIDs.
        """
        ui_tool = self.u(type="u2")
        start_time = time.time()
        scan_clicked = False

        while time.time() - start_time < timeout:
            try:
                all_texts = self._get_visible_texts(ui_tool)
                candidates = [text for text in all_texts if self.wifi_is_valid_ssid(text)]

                if candidates:
                    logging.info(f"鉁?Found real SSIDs: {candidates}")
                    return candidates

                # 5绉掑悗灏濊瘯鐐瑰嚮 Scan / 鎼滅储
                if not scan_clicked and time.time() - start_time > 5:
                    if ui_tool.wait(text="Scan", timeout=1):
                        logging.info("Triggered manual 'Scan' to refresh networks.")
                        scan_clicked = True
                        time.sleep(2)
                    elif ui_tool.wait(text="鎼滅储", timeout=1):
                        logging.info("Triggered manual '鎼滅储' to refresh networks.")
                        scan_clicked = True
                        time.sleep(2)

                time.sleep(1)
            except Exception as e:
                logging.warning(f"Error during Wi-Fi scan wait: {e}")
                time.sleep(1)

        logging.warning("鈿狅笍 Timeout waiting for real Wi-Fi networks (SSIDs).")
        return []

    @staticmethod
    def wifi_is_on_settings_page(ui_tool) -> bool:
        """
        Check if the current UI screen is the Wi-Fi settings page.

        :param ui_tool: An instance of UiautomatorTool (e.g., from dut.u())
        :return: True if on Wi-Fi settings page, False otherwise.
        """
        try:
            # Look for key indicators of Wi-Fi settings page
            if (ui_tool.wait(text="Wi-Fi", timeout=2) or
                    ui_tool.wait(text="WLAN", timeout=2) or
                    ui_tool.wait(text="鏃犵嚎灞€鍩熺綉", timeout=2) or
                    ui_tool.xpath('//*[@resource-id="com.android.settings:id/wifi_settings"]').exists):
                return True
        except Exception as e:
            logging.debug(f"Error in wifi_is_on_settings_page: {e}")
        return False

    def _get_visible_texts(self, ui_tool) -> List[str]:
        """Safely extract all non-empty TextView texts from current UI."""
        texts = set()
        try:
            for view in ui_tool.d2(className="android.widget.TextView"):
                text = view.info.get("text", "")
                if isinstance(text, str) and text.strip():
                    texts.add(text.strip())
        except Exception as e:
            logging.debug(f"Failed to extract visible texts: {e}")
        return list(texts)

    @staticmethod
    def get_device_ip_adb(serial: str) -> str:
        """
        Get the first valid Wi-Fi IP address from any active interface.
        Skips loopback (127.*) and link-local (169.254.*) addresses.
        Prioritizes interfaces starting with 'wlan'.
        """
        try:
            # Get all interface address
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "ip addr show"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=8
            )
            lines = result.stdout.splitlines()

            # IP List
            candidates = []  # [(interface, ip), ...]

            current_iface = None
            for line in lines:
                # eg "3: wlan0: <BROADCAST,MULTICAST,UP> ..."
                if line.strip() and line[0].isdigit():
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip()
                elif "inet " in line and current_iface:
                    ip_with_mask = line.strip().split()[1]
                    ip = ip_with_mask.split("/")[0]
                    if ip.startswith("127.") or ip.startswith("169.254."):
                        continue
                    candidates.append((current_iface, ip))

            # Return wlan* IP
            for iface, ip in candidates:
                if iface and iface.startswith("wlan"):
                    logging.debug(f"Found valid IP on {iface}: {ip}")
                    return ip

            # If no wlan锛宺eturn vaild IP锛坒allback锛?
            if candidates:
                iface, ip = candidates[0]
                logging.warning(f"No 'wlan' interface found. Using IP from {iface}: {ip}")
                return ip

        except Exception as e:
            logging.error(f"Failed to get IP via ADB: {e}")

        return ""

    @staticmethod
    def get_wifi_mac_adb(serial: str) -> str:
        """
        Get Wi-Fi MAC address from any active wlan interface.
        Returns uppercase, colon-separated format (e.g., AA:BB:CC:DD:EE:FF).
        """
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "ip addr show"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5
            )
            lines = result.stdout.splitlines()
            current_iface = None

            for line in lines:
                if line.strip() and line[0].isdigit():
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip()
                elif "link/ether" in line and current_iface and current_iface.startswith("wlan"):
                    mac = line.strip().split()[1].upper()
                    # Validate MAC format
                    if len(mac.replace(":", "")) == 12:
                        return mac
        except Exception as e:
            logging.error(f"Failed to get Wi-Fi MAC: {e}")
        return ""

    def _get_wifi_state_adb(serial: str) -> bool:
        """Use ADB to check if Wi-Fi is enabled (returns True if ON)."""
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "dumpsys wifi"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5, encoding='utf-8', errors='ignore'
            )
            output = result.stdout

            if not output or not isinstance(output, str):
                logging.warning("ADB dumpsys wifi returned empty or non-string output")
                return False

            if "mWifiEnabled=true" in output:
                return True
            if "mWifiEnabled=false" in output:
                return False
            if "Wi-Fi is enabled" in output:
                return True
            if "Wi-Fi is disabled" in output:
                return False

            logging.warning(f"Could not determine Wi-Fi state from dumpsys. First 200 chars: {output[:200]}")
            return False

        except Exception as e:
            logging.warning(f"Failed to get Wi-Fi state via ADB: {e}")
            return False

    def wifi_get_connected_ssid(self) -> str:
        """
        Try to extract the SSID of the currently connected Wi-Fi network.
        Returns empty string if not connected.
        """
        ui_tool = self.u(type="u2")
        time.sleep(2)
        try:
            # Look for the "Connected" indicator element.
            connected_elements = ui_tool.d2.xpath('//*[@text="Connected"]')
            if connected_elements.exists:
                parent = connected_elements.parent()
                if parent.exists:
                    ssid_text = parent.child(className="android.widget.TextView").get_text()
                    if ssid_text and ssid_text not in ["Connected"]:
                        logging.info(f"Detected connected SSID via UI: {ssid_text}")
                        return ssid_text
        except Exception as e:
            logging.debug(f"XPath failed in wifi_get_connected_ssid: {e}")
        logging.info("No 'Connected' indicator found. Assuming not connected.")
        return ""

    def get_connected_ssid_via_cli_adb(self, serial):
        """Reliable SSID fetch via 'iw dev wlan0 link' without shell pipes."""
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "su 0 iw dev wlan0 link"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=8,
                encoding='utf-8',
                errors='ignore'
            )
            logging.info(f"wlan0 link result : {result}")
            if result.returncode != 0:
                logging.warning(f"Failed to run 'iw dev wlan0 link': {result.stderr}")
                return ""

            output = result.stdout
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    ssid = line[5:].strip()  # Remove "SSID:"
                    if ssid:
                        return ssid
            return ""  # Not connected or hidden SSID
        except Exception as e:
            logging.error(f"Exception in get_connected_ssid_via_cli_adb: {e}")
            return ""

    def get_connected_channel_via_cli_adb(self, serial: str) -> int:
        """
        鑾峰彇褰撳墠杩炴帴鐨?Wi-Fi 淇￠亾鍙枫€?
        閫氳繃 'iw wlan0 link' 鍛戒护鑾峰彇杩炴帴棰戠巼锛岀劧鍚庤浆鎹负淇￠亾鍙枫€?
        鏀寔 2.4GHz 鍜?5GHz 棰戞銆?

        Args:
            serial (str): ADB 璁惧搴忓垪鍙?

        Returns:
            int: 杩炴帴鐨勪俊閬撳彿锛屾湭杩炴帴鎴栨棤娉曡幏鍙栨椂杩斿洖 0
        """
        try:
            # 鎵ц涓?get_connected_ssid_via_cli_adb 鐩稿悓鐨勫懡浠?
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "su 0 iw dev wlan0 link"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=8,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode != 0:
                logging.warning(f"Failed to run 'iw dev wlan0 link': {result.stderr}")
                return 0

            output = result.stdout
            logging.debug(f"iw wlan0 link output:\n{output}")

            # 妫€鏌ユ槸鍚﹀凡杩炴帴
            if "Not connected" in output or "no current connection" in output.lower():
                logging.info("Device is not connected to any Wi-Fi network")
                return 0

            # 鎻愬彇棰戠巼 (freq)
            freq_match = re.search(r'freq:\s*(\d+)', output)
            if not freq_match:
                logging.warning("Could not find frequency in iw link output")
                return 0

            freq = int(freq_match.group(1))
            logging.debug(f"Connected frequency: {freq} MHz")

            # 棰戠巼鍒颁俊閬撶殑鏄犲皠
            FREQ_TO_CHANNEL = {
                # 2.4GHz 棰戞
                2412: 1, 2417: 2, 2422: 3, 2427: 4, 2432: 5, 2437: 6,
                2442: 7, 2447: 8, 2452: 9, 2457: 10, 2462: 11, 2467: 12,
                2472: 13, 2484: 14,

                # 5GHz 棰戞 (UNII-1 & UNII-2)
                5180: 36, 5200: 40, 5220: 44, 5240: 48,
                5260: 52, 5280: 56, 5300: 60, 5320: 64,

                # 5GHz 棰戞 (UNII-2e)
                5500: 100, 5520: 104, 5540: 108, 5560: 112,
                5580: 116, 5600: 120, 5620: 124, 5640: 128,
                5660: 132, 5680: 136, 5700: 140, 5720: 144,

                # 5GHz 棰戞 (UNII-3)
                5745: 149, 5765: 153, 5785: 157, 5805: 161, 5825: 165
            }

            # 灏濊瘯鐩存帴鏄犲皠
            if freq in FREQ_TO_CHANNEL:
                channel = FREQ_TO_CHANNEL[freq]
                logging.info(f"鉁?Connected to channel {channel} (frequency: {freq} MHz)")
                return channel

            # 灏濊瘯璁＄畻 2.4GHz 棰戞 (2412 + 5*(n-1))
            if 2400 <= freq <= 2500:
                # 鍏紡锛歝hannel = (freq - 2407) / 5
                channel = (freq - 2407) // 5
                if 1 <= channel <= 14:
                    logging.info(f"鉁?Calculated 2.4GHz channel {channel} (frequency: {freq} MHz)")
                    return channel

            # 灏濊瘯璁＄畻 5GHz 棰戞 UNII-1 & UNII-2 (5180 + 20*(n-1))
            if 5100 <= freq <= 5350:
                # 浠?36 寮€濮?
                channel = 36 + ((freq - 5180) // 20) * 4
                if channel in [36, 40, 44, 48, 52, 56, 60, 64]:
                    logging.info(f"鉁?Calculated 5GHz channel {channel} (frequency: {freq} MHz)")
                    return channel

            # 灏濊瘯璁＄畻 5GHz 棰戞 UNII-2e (5500 + 20*(n-1))
            if 5400 <= freq <= 5750:
                # 浠?100 寮€濮?
                channel = 100 + ((freq - 5500) // 20) * 4
                if channel in [100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144]:
                    logging.info(f"鉁?Calculated 5GHz channel {channel} (frequency: {freq} MHz)")
                    return channel

            # 灏濊瘯璁＄畻 5GHz 棰戞 UNII-3 (5745 + 20*(n-1))
            if 5700 <= freq <= 5900:
                # 浠?149 寮€濮?
                channel = 149 + ((freq - 5745) // 20) * 4
                if channel in [149, 153, 157, 161, 165]:
                    logging.info(f"鉁?Calculated 5GHz channel {channel} (frequency: {freq} MHz)")
                    return channel

            logging.warning(f"鈿狅笍 Unknown frequency {freq} MHz, cannot determine channel")
            return 0

        except subprocess.TimeoutExpired:
            logging.error(f"Timeout while getting connected channel on {serial}")
            return 0
        except Exception as e:
            logging.error(f"Exception in get_connected_channel_via_cli_adb: {e}")
            return 0

    def get_connected_ssid_adb(self, serial: Optional[str] = None) -> str:
        device_serial = serial or getattr(self, 'serial', None)
        if not device_serial:
            return ""

        try:
            result = subprocess.run(
                ["adb", "-s", device_serial, "shell", "dumpsys wifi"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=8,
                encoding='utf-8', errors='ignore'
            )
            output = result.stdout
            if not output:
                return ""

            # Usually Connected status
            is_in_connected_state = any(state in output for state in [
                "curState=ConnectedState",
                "curState=ObtainingIpState",
                "curState=RoamingState"
                "curState=L2ConnectedState",  # Android 10+
                "curState=L3ConnectedState",  # L3 Network
                "curState=StartedState"
            ])

            if not is_in_connected_state:
                return ""

            # Verify if wlan0 has IP
            try:
                ip_result = subprocess.run(
                    ["adb", "-s", device_serial, "shell", "ip addr show wlan0"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5
                )
                if "inet " not in ip_result.stdout:
                    logging.debug("No IP on wlan0, treating as disconnected despite state.")
                    return ""
            except:
                pass  # fallback to dumpsys only

            if not is_in_connected_state:
                logging.debug("Device is not in a connected Wi-Fi state.")
                return ""

            # Get SSID if valid
            ssid_match = re.search(r'mLastNetworkSsid\s*=\s*"([^"]*)"', output)
            if ssid_match:
                ssid = ssid_match.group(1).strip()
                if ssid and ssid not in ("", "<unknown ssid>"):
                    return ssid

            ssid_match2 = re.search(r'SSID:\s*"([^"]+)"', output)
            if ssid_match2:
                candidate = ssid_match2.group(1).strip()
                if self.wifi_is_valid_ssid(candidate):
                    return candidate

            return "CONNECTED_HIDDEN_SSID"

        except Exception as e:
            logging.error(f"Error in get_connected_ssid_adb: {e}")
            return ""

    def enter_wifi_network_list_page(self, timeout: int = 5) -> bool:
        """
        Click on 'Wi-Fi' / 'WLAN' entry to enter the actual network scan list page.
        Returns True if clicked successfully.
        """
        ui_tool = self.u()
        for keyword in ["Wi-Fi", "WLAN", "鏃犵嚎灞€鍩熺綉"]:
            if ui_tool.wait(text=keyword, timeout=timeout):
                logging.info(f"Clicked '{keyword}' to enter Wi-Fi network list.")
                time.sleep(2)
                return True
        logging.warning("Failed to enter Wi-Fi network list page.")
        return False

    def _capture_screenshot(dut, logdir: Path, step_name: str):
        """Capture and return path to screenshot."""
        safe_name = "".join(c if c.isalnum() else "_" for c in step_name)
        timestamp = int(time.time())
        img_path = logdir / f"{safe_name}_{timestamp}.png"
        try:
            dut.u().screenshot(str(img_path))
            return img_path
        except Exception as e:
            print(f"Failed to capture screenshot for '{step_name}': {e}")
            return None

    def is_wired_connection_active(self, serial: str, timeout: int = 8) -> Tuple[bool, str]:
        """
        Check if any wired (Ethernet) interface is active.
        Returns:
            (is_active: bool, debug_output: str)
        """
        wired_ifaces = ["eth0", "enp0s1", "wired0"]
        active_wired = []
        output_log = ""

        for iface in wired_ifaces:
            try:
                # Run: adb -s <serial> shell ip addr show <iface>
                result = subprocess.run(
                    ["adb", "-s", serial, "shell", "ip addr show", iface],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=8
                )
                output = result.stdout.strip()
                output_log += f"\n[iface: {iface}]\n{output}"
                if "state UP" in output or "inet " in output:
                    active_wired.append(iface)
            except Exception as e:
                output_log += f"\n[iface: {iface} EXCEPTION] {e}"

        is_active = len(active_wired) > 0
        summary = f"Wired interfaces active: {active_wired}" if is_active else "No active wired interfaces"
        full_output = f"{summary}\n--- Details ---{output_log}"
        return is_active, full_output

    def wait_for_device_boot(self, serial: str, timeout: int = 150) -> Tuple[bool, str]:
        """
        Wait for device to come online and complete boot.
        Returns:
            (booted: bool, debug_info: str)
        """
        debug_log = []

        # Step 1: Wait for ADB device to appear
        try:
            result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True)
            if serial in result.stdout:
                # reboot device
                subprocess.run(["adb", "-s", serial, "reboot"], check=True, timeout=20)
                logging.info("Reboot command sent successfully.")
            else:
                logging.warning("Device not online. Assuming reboot is already in progress.")
        except Exception as e:
            logging.error(f"Warning: Failed to send reboot command: {e}. Proceeding to wait...")

        time.sleep(5)

        start = time.time()
        while time.time() - start < timeout:
            try:
                subprocess.run(
                    ["adb", "-s", serial, "wait-for-device"],
                    check=True, timeout=timeout
                )
                logging.info("Device detected via ADB")
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception as e:
                time.sleep(2)
                continue
        else:
            logging.error("Timeout: Device did not come back online.")
            return False, "\n".join(debug_log)

        # Step 2: Wait for sys.boot_completed == 1
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=10
                )
                if result.stdout.strip() == "1":
                    logging.info("Boot completed (sys.boot_completed=1)")
                    return True, "\n".join(debug_log)
            except Exception as e:
                logging.warning(f"getprop error: {e}")
            time.sleep(2)

        msg = f"Boot completion not detected within {timeout}s"
        logging.error(msg)
        return False, "\n".join(debug_log)

    @staticmethod
    def _enable_wifi_adb(serial: str, timeout: int = 10) -> bool:
        """
        Enable Wi-Fi via ADB command 'svc wifi enable'.
        Returns True if command executed successfully (does not guarantee Wi-Fi is fully up).
        """
        try:
            import subprocess
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "svc", "wifi", "enable"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
            )
            if result.returncode == 0:
                logging.info(f"Wi-Fi enable command sent successfully to {serial}")
                return True
            else:
                logging.error(f"Failed to enable Wi-Fi on {serial}: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Exception while enabling Wi-Fi on {serial}: {e}")
            return False

    @staticmethod
    def _disable_wifi_adb(serial: str, timeout: int = 10) -> bool:
        """
        Enable Wi-Fi via ADB command 'svc wifi enable'.
        Returns True if command executed successfully (does not guarantee Wi-Fi is fully up).
        """
        try:
            import subprocess
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "svc", "wifi", "disable"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
            )
            if result.returncode == 0:
                logging.info(f"Wi-Fi disable command sent successfully to {serial}")
                return True
            else:
                logging.error(f"Failed to disable Wi-Fi on {serial}: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Exception while disabling Wi-Fi on {serial}: {e}")
            return False

    @staticmethod
    def _disconnect_and_prevent_reconnect(serial: str, timeout: int = 10) -> bool:
        """
        Disconnect from current Wi-Fi and prevent auto-reconnect by removing the network.
        This ensures device stays disconnected for subsequent test steps.
        """
        try:
            import subprocess
            import time

            # Step 1: List networks to find CURRENT one
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "wpa_cli", "list_networks"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
            )

            if result.returncode != 0:
                logging.error(f"Failed to list Wi-Fi networks on {serial}")
                return False

            lines = result.stdout.strip().split('\n')
            current_net_id = None
            for line in lines[1:]:  # Skip header
                if "[CURRENT]" in line:
                    parts = line.split()
                    if parts:
                        current_net_id = parts[0]
                        break

            if current_net_id is None:
                logging.info("No current network found, already disconnected.")
                return True

            # Step 2: Remove (forget) the current network
            result2 = subprocess.run(
                ["adb", "-s", serial, "shell", "wpa_cli", "remove_network", current_net_id],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
            )

            if result2.returncode == 0:
                logging.info(f"Removed network ID {current_net_id} on {serial} to prevent reconnect")
                time.sleep(2)
                return True
            else:
                logging.error(f"Failed to remove network {current_net_id}: {result2.stderr}")
                return False

        except Exception as e:
            logging.error(f"Exception in _disconnect_and_prevent_reconnect on {serial}: {e}")
            return False

    @staticmethod
    def _run_adb(cmd: str) -> None:
        """鎵ц ADB 鍛戒护锛堥潤榛橈級"""
        try:
            #subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # 鑷姩澶勭悊 stdout/stderr
                text=True,  # 杩斿洖瀛楃涓茶€岄潪 bytes
                timeout=30,
                # 闃叉鍙ユ焺娉勬紡
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                logging.error(f"ADB command failed: {result.stderr}")
            return result.stdout

        except subprocess.TimeoutExpired:
            logging.error("ADB command timed out")
            raise
        except Exception as e:
            logging.error(f"Exception running ADB: {e}")
            raise

    # 鍦?ui_mixin.py 涓紝DeviceUiFeature 绫诲唴娣诲姞锛?
    @staticmethod
    def _run_adb_capture_output(cmd: str, timeout: int = 10) -> str:
        """Run an ADB command and return stdout for parsing."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logging.warning(f"ADB command failed (exit {result.returncode}): {cmd}")
                logging.debug(f"STDERR: {result.stderr}")
                return ""
        except subprocess.TimeoutExpired:
            logging.error(f"ADB command timed out: {cmd}")
            return ""
        except Exception as e:
            logging.error(f"Exception running ADB: {e}")
            return ""

    @staticmethod
    def _dump_ui(serial: str, logdir: Optional[Path] = None) -> Any:
        """Dump the current UI hierarchy and return the parsed XML root."""
        remote_path = "/sdcard/window_dump.xml"
        if logdir is None:
            # 鍒涘缓涓€涓湡姝ｇ殑涓存椂鏂囦欢锛堣嚜鍔ㄥ垹闄わ級
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.xml') as tmp:
                local_path = Path(tmp.name)
        else:
            local_path = logdir / f"ui_dump_{int(time.time())}.xml"

        try:
            # 鎵ц dump 鍜?pull
            DeviceUiFeature._run_adb(f"adb -s {serial} shell uiautomator dump {remote_path} --compressed")
            DeviceUiFeature._run_adb(f"adb -s {serial} pull {remote_path} {local_path}")

            # 鍏抽敭锛氳鍙栨枃浠跺唴瀹瑰埌鍐呭瓨锛屽啀瑙ｆ瀽
            with open(local_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            root = ET.fromstring(xml_content)

            logging.debug(f"[DEBUG] UI dumped and parsed from: {local_path}")
            return root

        except Exception as e:
            logging.error(f"Failed to dump or parse UI: {e}")
            raise

        finally:
            # 鍙湁涓存椂鏂囦欢鎵嶅垹闄わ紙涓旂‘淇濆凡璇诲叆鍐呭瓨锛?
            if logdir is None and local_path.exists():
                local_path.unlink() # 蹇界暐鍒犻櫎澶辫触
    # def _dump_ui(serial: str, logdir: Optional[Path] = None) -> Any:
    #     """Dump 褰撳墠 UI 骞惰繑鍥?XML 鏍硅妭鐐广€傝В鏋愬悗鑷姩娓呯悊涓存椂鏂囦欢锛堥櫎闈炴寚瀹?logdir锛?""
    #     remote_path = "/sdcard/window_dump.xml"
    #     if logdir is None:
    #         # 鍒涘缓涓€涓湡姝ｇ殑涓存椂鏂囦欢锛堣嚜鍔ㄥ垹闄わ級
    #         with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.xml') as tmp:
    #             local_path = Path(tmp.name)
    #     else:
    #         local_path = logdir / f"ui_dump_{int(time.time())}.xml"
    #
    #     try:
    #         # 鎵ц dump 鍜?pull
    #         DeviceUiFeature._run_adb(f"adb -s {serial} shell uiautomator dump {remote_path} --compressed")
    #         DeviceUiFeature._run_adb(f"adb -s {serial} shell rm -f {remote_path}")  # 鍙€夛細娓呯悊璁惧绔畫鐣?
    #         DeviceUiFeature._run_adb(f"adb -s {serial} pull {remote_path} {local_path}")
    #
    #         # 鍏抽敭锛氳鍙栨枃浠跺唴瀹瑰埌鍐呭瓨锛屽啀瑙ｆ瀽
    #         with open(local_path, 'r', encoding='utf-8') as f:
    #             xml_content = f.read()
    #         root = ET.fromstring(xml_content)
    #
    #         logging.debug(f"[DEBUG] UI dumped and parsed from: {local_path}")
    #         return root
    #
    #     except Exception as e:
    #         logging.error(f"Failed to dump or parse UI: {e}")
    #         raise
    #
    #
    #     finally:
    #         if logdir is None:
    #             for attempt in range(3):  # 灏濊瘯3娆?
    #                 try:
    #                     local_path.unlink()
    #                     logging.debug(f"[DEBUG] Successfully deleted temp file: {local_path}")
    #                     break  # 鍒犻櫎鎴愬姛锛岃烦鍑哄惊鐜?
    #                 except FileNotFoundError:
    #                     logging.debug(f"[DEBUG] Temp file not found (already deleted): {local_path}")
    #                     break
    #                 except (OSError, PermissionError) as e:
    #                     if attempt == 2:  # 鏈€鍚庝竴娆″皾璇曚篃澶辫触浜?
    #                         logging.warning(
    #                             f"[WARN] Failed to delete temp file after 3 attempts: {local_path}. Error: {e}")
    #                     else:
    #                         time.sleep(0.1)  # 绛夊緟100ms鍚庨噸璇曪紝姣?0ms鏇村鏉?

    @staticmethod
    def _find_clickable_parent_of_text(root, target_texts: List[str]) -> Optional[Tuple[int, int]]:
        """Find clickable coordinates for a target text within the UI tree."""
        nodes = []
        for node in root.iter("node"):
            bounds = node.attrib.get("bounds", "")
            coords = list(map(int, re.findall(r"\d+", bounds))) if bounds else []
            nodes.append({
                'node': node,
                'text': node.attrib.get("text", "").strip(),
                'clickable': node.attrib.get("clickable") == "true",
                'bounds_rect': coords
            })

        for item in nodes:
            if not item['text']:
                continue
            for kw in target_texts:
                if kw.lower() in item['text'].lower():
                    child_rect = item['bounds_rect']
                    if len(child_rect) != 4:
                        continue

                    candidates = []
                    for parent in nodes:
                        if not parent['clickable']:
                            continue
                        pr = parent['bounds_rect']
                        if len(pr) != 4:
                            continue
                        if pr[0] <= child_rect[0] and pr[1] <= child_rect[1] and pr[2] >= child_rect[2] and pr[3] >= \
                                child_rect[3]:
                            area = (pr[2] - pr[0]) * (pr[3] - pr[1])
                            candidates.append((area, pr))

                    if candidates:
                        candidates.sort()
                        x = (candidates[0][1][0] + candidates[0][1][2]) // 2
                        y = (candidates[0][1][1] + candidates[0][1][3]) // 2
                        logging.info(f"[DEBUG] Found clickable parent for '{item['text']}' at ({x}, {y})")
                        return x, y

                    if len(child_rect) == 4:
                        x = (child_rect[0] + child_rect[2]) // 2
                        y = (child_rect[1] + child_rect[3]) // 2
                        logging.warning(f"[DEBUG] No clickable parent! Fallback to text coords ({x}, {y})")
                        return x, y

        logging.info("[DEBUG] No matching text found.")
        return None

    @staticmethod
    def _find_ssid_in_list(root, target_ssid: str) -> Optional[Tuple[int, int]]:
        """Find SSID coordinates in the Wi-Fi list via content-desc or child text."""

        def clean_text(text: str) -> str:
            #return re.sub(r"[^a-z0-9]", "", text.strip().lower())
            return text.strip()

        target_clean = clean_text(target_ssid)
        logging.info(f"[DEBUG] Searching for cleaned SSID: '{target_clean}'")

        for node in root.iter("node"):
            if node.attrib.get("clickable") == "true":
                bounds = node.attrib.get("bounds", "")
                coords = list(map(int, re.findall(r"\d+", bounds)))
                if len(coords) != 4:
                    continue
                x = (coords[0] + coords[2]) // 2
                y = (coords[1] + coords[3]) // 2

                # 浼樺厛浠?content-desc 瑙ｆ瀽
                content_desc = node.attrib.get("content-desc", "")
                if content_desc:
                    ssid_from_desc = content_desc.split(",")[0].strip()
                    clean_candidate = clean_text(ssid_from_desc)
                    if target_clean in clean_candidate or clean_candidate in target_clean:
                        return x, y

                # 鍏舵浠庡瓙鑺傜偣 text 瑙ｆ瀽
                for child in node.iter("node"):
                    child_text = child.attrib.get("text", "").strip()
                    if child_text:
                        clean_candidate = clean_text(child_text)
                        if target_clean in clean_candidate or clean_candidate in target_clean:
                            logging.info(f"[DEBUG] 鉁?Match via child text! Raw: '{child_text}' 鈫?Click at ({x}, {y})")
                            return x, y

        logging.info(f"[DEBUG] 鉂?SSID '{target_ssid}' not found.")
        return None

    @staticmethod
    def _connect_to_wifi_via_ui(
            serial: str,
            ssid: str,
            password: str = "",
            logdir: Path = None
    ) -> bool:
        """
        Connect SSID via UI
        """
        for retry_count in range(2):
            try:
                logging.info(f"[UI Connect] Attempt {retry_count + 1}/2 to connect to '{ssid}'")
                # Step 1: Open Wi-Fi Setting
                try:
                    temp_mixin = DeviceUiFeature()
                    temp_mixin.reset_settings_ui(serial)  # 鈫?鐜板湪鍙互璋冪敤浜?
                except Exception as e:
                    logging.warning(f"[UI Connect] Failed to reset settings UI: {e}")
                success = DeviceUiFeature._go_to_home(serial)
                DeviceUiFeature._open_wifi_settings_page(serial)
                time.sleep(2)

                # Step 2: Click "See all"
                see_all_texts = ["See all", "See all networks", "鍏ㄩ儴缃戠粶", "鏌ョ湅鍏ㄩ儴", "Show all"]
                logging.info(f"[DEBUG] Looking for 'See all' keywords: {see_all_texts}")
                for retry in range(5):
                    logging.info(f"\nAttempt {retry + 1}/5 to find 'See all' ---")
                    root = DeviceUiFeature._dump_ui(serial, logdir)
                    pos = DeviceUiFeature._find_clickable_parent_of_text(root, see_all_texts)
                    if pos:
                        logging.info(f"[INFO] Clicking 'See all' at ({pos[0]}, {pos[1]})")
                        DeviceUiFeature._run_adb(f"adb -s {serial} shell input tap {pos[0]} {pos[1]}")
                        time.sleep(4)
                        break
                    time.sleep(2)

                # Step 3: Scroll to bottom
                logging.info("[INFO] Scrolling to bottom of network list...")
                for _ in range(15):
                    DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_DOWN")
                    time.sleep(0.3)

                # Step 4: Find and click target SSID
                for attempt in range(30):
                    root = DeviceUiFeature._dump_ui(serial, logdir)
                    pos = DeviceUiFeature._find_ssid_in_list(root, ssid)
                    logging.info(f"[INFO] Found pos: {pos}")
                    if pos:
                        x, y = pos
                        logging.info(f"[INFO] Found SSID '{ssid}' at screen position ({x}, {y}). Tapping directly.")
                        DeviceUiFeature._run_adb(f"adb -s {serial} shell input tap {x} {y}")
                        time.sleep(1.0)

                        # Input password
                        if password:
                            logging.info(f"[INFO] Password required. Entering password.")
                            DeviceUiFeature._run_adb(f"adb -s {serial} shell input text '{password}'")
                            time.sleep(0.5)

                            # Try to Connect
                            try:
                                root_post = DeviceUiFeature._dump_ui(serial, logdir)
                                for node in root_post.iter("node"):
                                    text = node.attrib.get("text", "").strip().lower()
                                    if text in ["connect", "杩炴帴", "ok"]:
                                        bounds = node.attrib.get("bounds", "")
                                        coords = list(map(int, re.findall(r"\d+", bounds)))
                                        if len(coords) == 4:
                                            btn_x = (coords[0] + coords[2]) // 2
                                            btn_y = (coords[1] + coords[3]) // 2
                                            DeviceUiFeature._run_adb(f"adb -s {serial} shell input tap {btn_x} {btn_y}")
                                            logging.info("[INFO] Clicked 'Connect' button.")
                                            break
                                else:
                                    logging.info("[INFO] 'Connect' not found. Sending ENTER.")
                                    DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
                            except Exception as e:
                                logging.warning(f"[WARN] Failed to click Connect: {e}. Using ENTER fallback.")
                                DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")

                            time.sleep(2.0)
                        else:
                            time.sleep(2.0)

                        time.sleep(30)
                        return True

                    for _ in range(5):
                        DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_UP")
                        time.sleep(0.1)

            except Exception as e:
                if retry_count == 0:
                    logging.info("[UI Connect] Retrying in 60 seconds...")
                    time.sleep(60)
                    # 缁х画澶栧眰寰幆鐨勪笅涓€娆¤凯浠?
                    continue
                else:
                    # 濡傛灉鏄浜屾灏濊瘯涔熷け璐ヤ簡锛岃繑鍥?False
                    logging.error("[UI Connect] Failed to connect after 2 attempts.")
                    return False
        return False

    def launch_youtube_tv_and_search(self, serial: str, logdir: Path, query: str = "NASA"):
        """Launch YouTube TV and search for a channel on Android TV."""
        try:
            # Launch
            DeviceUiFeature._run_adb(
                f"adb -s {serial} shell am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity"
            )
            time.sleep(8)
            #capture test picture and log
            #self._capture_screenshot(logdir, "tv_youtube_home")

            # Navigate to Search (usually top-right)
            for _ in range(4):  # Move right to "Search"
                DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_RIGHT")
                time.sleep(0.5)
            DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
            time.sleep(2)

            # Input text
            DeviceUiFeature._run_adb(f"adb -s {serial} shell input text '{query}'")
            time.sleep(1)
            DeviceUiFeature._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
            time.sleep(5)

            # capture test picture and log
            #self._capture_screenshot(logdir, "tv_search_results")
            logging.info("鉁?YouTube TV search completed.")

            logging.info("猬咃笍 Exiting Wi-Fi settings UI...")
            for _ in range(3):
                success = DeviceUiFeature._go_to_home(serial)
                time.sleep(1)

            return True
        except Exception as e:
            logging.error(f"鉂?YouTube TV automation failed: {e}")
            return False

    def get_wifi_scan_results_via_cmd(self, serial: str) -> List[Tuple[str, int]]:
        """
        use 'cmd wifi list-scan-results' get Wi-Fi scan result.
        """
        try:
            output = self._run_adb_capture_output(
                f"adb -s {serial} shell cmd wifi list-scan-results", timeout=10
            )
            if not output or "BSSID" not in output:
                return []

            ap_list = []
            lines = output.strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or "BSSID" in line or "------" in line:
                    continue

                parts = re.split(r'\s{2,}', line)
                if len(parts) < 5:
                    continue

                rssi_str = parts[2].strip()
                ssid_raw = parts[4].strip()

                if not ssid_raw or ssid_raw == "''":
                    continue

                ssid = ssid_raw.strip('"').strip("'").strip()
                if not self.wifi_is_valid_ssid(ssid):
                    continue

                try:
                    rssi = int(rssi_str)
                    ap_list.append((ssid, rssi))
                except ValueError:
                    continue

            return ap_list

        except Exception as e:
            logging.error(f"Parse error in scan results: {e}", exc_info=True)
            return []

    @staticmethod
    def _clear_saved_wifi_networks(serial: str):
        """Clear saved Wi-Fi """
        try:
            logging.info(f"馃Ч Clearing all saved Wi-Fi networks on {serial}...")

            # Step 1: Try CLI commands
            cli_success = DeviceUiFeature._clear_all_wifi_records(serial)
            if cli_success:
                logging.info("鉁?All networks removed via 'cmd wifi'.")
            else:
                # Step 2: CLI failed锛寀se wpa_cli command
                logging.warning("鈿狅笍 CLI method failed. Falling back to wpa_cli disconnect.")
                DeviceUiFeature._disconnect_and_prevent_reconnect(serial)
                time.sleep(2)

            # Step 3: Close Wi-Fi Service
            DeviceUiFeature._run_adb(f"adb -s {serial} shell svc wifi disable")
            time.sleep(2)

            # Step 4: Deleted config files
            DeviceUiFeature._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/*.conf")
            DeviceUiFeature._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/wpa_supplicant.conf")
            logging.info("鉁?Deleted Wi-Fi config files (fallback cleanup).")

            # Step 5: Enable Wi-Fi
            DeviceUiFeature._run_adb(f"adb -s {serial} shell svc wifi enable")
            time.sleep(5)

            logging.info("鉁?Wi-Fi cleanup completed.")
        except Exception as e:
            logging.error(f"鉂?Failed to clear Wi-Fi networks: {e}")

    @staticmethod
    def _list_saved_networks(serial: str) -> List[int]:
        """浣跨敤 'cmd wifi list-saved-networks' 鑾峰彇鎵€鏈夊凡淇濆瓨缃戠粶鐨?ID 鍒楄〃"""
        try:
            output = DeviceUiFeature._run_adb_capture_output(
                f"adb -s {serial} shell cmd wifi list-saved-networks", timeout=8
            )
            if not output:
                return []
            ids = []
            for line in output.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    ids.append(int(line))
            return ids
        except Exception as e:
            logging.warning(f"Failed to list saved networks on {serial}: {e}")
            return []

    @staticmethod
    def _clear_all_wifi_records(serial: str) -> bool:
        try:
            logging.info(f"馃Ч Using 'cmd wifi forget-network' on {serial}...")

            # 1. Disabled Wi-Fi
            DeviceUiFeature._run_adb(f"adb -s {serial} shell svc wifi disable")
            time.sleep(2)

            # 2. Get networkId锛堝幓閲?+ 鎺掑簭锛?
            try:
                output = DeviceUiFeature._run_adb_capture_output(
                    f"adb -s {serial} shell cmd wifi list-saved-networks", timeout=8
                )
                network_ids = sorted(set(int(line.strip()) for line in output.splitlines() if line.strip().isdigit()))
            except Exception as e:
                logging.warning(f"Failed to list networks, assuming none: {e}")
                network_ids = []

            # 3. forget everyone
            if network_ids:
                logging.info(f"Forgetting network IDs: {network_ids}")
                for nid in network_ids:
                    cmd = f"adb -s {serial} shell cmd wifi forget-network {nid}"
                    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5)
                    if "Forget successful" in result.stdout or result.returncode == 0:
                        logging.debug(f"鉁?Forgot network {nid}")
                    else:
                        logging.warning(f"鈿狅笍 Failed to forget {nid}: {result.stderr.strip()}")
                    time.sleep(0.3)
            else:
                logging.info("No saved networks to forget.")

            # 4. Delete config files
            DeviceUiFeature._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/*.conf")
            DeviceUiFeature._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/wpa_supplicant.conf")

            # 5. Enable Wi-Fi
            DeviceUiFeature._run_adb(f"adb -s {serial} shell svc wifi enable")
            time.sleep(5)

            logging.info("鉁?Wi-Fi cleanup via 'cmd wifi forget-network' completed.")
            return True

        except Exception as e:
            logging.error(f"鉂?Cleanup failed: {e}")
            return False

    def _forget_wifi_via_ui(self, serial: str, target_ssid: str = "None"):
        logging.info(f"馃Ч Forgetting Wi-Fi '{target_ssid}' via UI on {serial}...")

        target_ssid = self.get_connected_ssid_via_cli_adb(serial)

        self.reset_settings_ui(serial)
        # Open Wi-Fi Settings
        DeviceUiFeature._open_wifi_settings_page(serial)
        time.sleep(5)

        # Ensure Wi-Fi is on
        state = self._run_adb_capture_output(f"adb -s {serial} shell settings get global wifi_on").strip()
        if state == "0":
            self._run_adb(f"adb -s {serial} shell svc wifi enable")
            time.sleep(5)

        # Step 1: Find and click the SSID (with retry)
        # Step 1: Find and click the SSID (click twice to ensure it works on STB)
        root = self._dump_ui(serial)
        pos = self._find_clickable_parent_of_text(root, [target_ssid])
        if not pos:
            logging.error(f"SSID '{target_ssid}' not found in Wi-Fi list.")
            return False

        x, y = pos
        logging.info(f"鉁?Found SSID '{target_ssid}' at ({x}, {y}). Clicking twice...")

        # First click
        self._run_adb(f"adb -s {serial} shell input tap {x} {y}")
        time.sleep(1)

        # Second click (to ensure it registers on STB)
        self._run_adb(f"adb -s {serial} shell input tap {x} {y}")
        time.sleep(2)  # Give time to enter detail page
        detail_indicators = ["Forget", "蹇樿", "Security", "瀹夊叏绫诲瀷", "IP settings", "Signal", target_ssid]
        root_check = self._dump_ui(serial)
        in_detail_page = any(
            self._find_clickable_parent_of_text(root_check, [keyword]) is not None
            for keyword in detail_indicators
        )

        if not in_detail_page:
            logging.error("鉂?Still in Wi-Fi list or failed to enter network detail page. Exiting.")
            return False

        logging.info("鉁?Confirmed: entered network detail page.")

        # Step 2: Scroll down to reveal 'Forget' button (STB uses DPAD)
        logging.info("猬囷笍 Scrolling down to reveal 'Forget' button...")
        for i in range(8):  # Press DOWN
            self._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_DOWN")
            time.sleep(0.3)

        time.sleep(1)

        # Step 3: Find and click 'Forget'
        root2 = self._dump_ui(serial)
        forget_pos = self._find_clickable_parent_of_text(root2, ["Forget", "蹇樿", "鍒犻櫎"])
        if forget_pos:
            fx, fy = forget_pos
            logging.info(f"鉁?Found 'Forget' at ({fx}, {fy}). Clicking...")
            self._run_adb(f"adb -s {serial} shell input tap {fx} {fy}")
            time.sleep(1)
        else:
            logging.error("鉂?'Forget' button NOT FOUND!")
            return False

        # Step 4: Wait for confirmation dialog and click OK
        logging.info("馃攳 Waiting for 'Forget network' confirmation dialog...")
        for _ in range(5):  # 鏈€澶氱瓑寰?10 绉?
            root3 = self._dump_ui(serial)
            ok_pos = self._find_clickable_parent_of_text(root3, ["OK", "纭", "纭畾"])
            if ok_pos:
                ox, oy = ok_pos
                logging.info(f"鉁?Found 'OK' at ({ox}, {oy}). Clicking...")
                self._run_adb(f"adb -s {serial} shell input tap {ox} {oy}")
                logging.info("鉁?Successfully forgot network via UI.")
                break
            time.sleep(1)

        else:
            logging.error("鉂?'OK' button not found in confirmation dialog!")
            return False

        logging.info("猬咃笍 Exiting Wi-Fi settings UI...")
        for _ in range(3):
            self._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_BACK")
            success = DeviceUiFeature._go_to_home(serial)
            time.sleep(1)

        logging.info("鉁?Exited Wi-Fi settings UI.")
        return True

    @staticmethod
    def _add_manual_wifi_network(
            serial: str,
            ssid: str,
            security: str,
            password: Optional[str] = None,
            logdir: Optional[Path] = None
    ) -> bool:
        import time
        import re

        # --- Helper Functions ---
        def _execute_adb_command(cmd: str):
            DeviceUiFeature._run_adb(f"adb -s {serial} {cmd}")

        def _dump_ui():
            return DeviceUiFeature._dump_ui(serial, logdir)

        def _tap_text(root, keywords: List[str]) -> bool:
            pos = DeviceUiFeature._find_clickable_parent_of_text(root, keywords)
            if pos:
                x, y = pos
                _execute_adb_command(f"shell input tap {x} {y}")
                return True
            return False

        def _get_center(node) -> Tuple[int, int]:
            bounds = node.attrib.get("bounds", "")
            coords = list(map(int, re.findall(r"\d+", bounds)))
            if len(coords) == 4:
                return (coords[0] + coords[2]) // 2, (coords[1] + coords[3]) // 2
            return 0, 0

        def _escape_text_for_input(text: str) -> str:
            text = text.replace(" ", "%s")
            text = text.replace("'", "\\'")
            return text

        def _take_screenshot(name: str):
            if logdir:
                path = logdir / f"{name}_{int(time.time())}.png"
                _execute_adb_command(f"exec-out screencap -p > '{path}'")

        try:
            logging.info(f"Starting manual connect to hidden SSID: {ssid}, security: {security}")

            # --- Step 1: Open Wi-Fi settings ---
            if not DeviceUiFeature._open_wifi_settings_page(serial):
                logging.error("Failed to open Wi-Fi settings page")
                _take_screenshot("fail_open_wifi")
                return False
            time.sleep(3)
            _take_screenshot("wifi_settings_page")

            # --- Step 2: Click "Add new network" BUTTON ---
            # We are now on the main Wi-Fi settings page (showing network list)
            add_net_clicked = False
            for attempt in range(5):
                root = _dump_ui()
                # DEBUG: Log all texts to see what's actually on screen
                all_texts = [node.attrib.get("text", "") for node in root.iter("node") if node.attrib.get("text")]
                logging.info(
                    f"[DEBUG] Attempt {attempt + 1} - Visible texts: {[t for t in all_texts if t.strip()][:10]}")

                add_net_keywords = [
                    "Add new network", "Add network", "Add Wi-Fi network",
                    "Join other network", "Other networks",
                    "+",
                ]

                if _tap_text(root, add_net_keywords):
                    logging.info("鉁?Successfully clicked 'Add new network' button")
                    add_net_clicked = True
                    break
                else:
                    logging.warning(f"'Add new network' not found on attempt {attempt + 1}")
                    # Try scrolling down in case button is off-screen
                    _execute_adb_command("shell input swipe 500 1000 500 300 300")
                    time.sleep(2)

            if not add_net_clicked:
                logging.error("鉂?Failed to find and click 'Add new network' button")
                _take_screenshot("add_network_not_found")
                return False

            # --- Step 3: Wait for SSID input page ---
            ssid_input_page = False
            for wait_attempt in range(8):  # Wait up to 8 seconds
                time.sleep(1)
                root = _dump_ui()
                all_texts = {node.attrib.get("text", "") for node in root.iter("node")}
                if "Enter name of Wi-Fi network" in all_texts:
                    ssid_input_page = True
                    logging.info("鉁?SSID input page loaded")
                    break

            if not ssid_input_page:
                logging.error("鉂?SSID input page did not appear after clicking 'Add new network'")
                _take_screenshot("ssid_input_not_loaded")
                return False

            _take_screenshot("ssid_input_page")

            # --- Step 4: Input SSID ---
            ssid_input_found = False
            for node in root.iter("node"):
                text = node.attrib.get("text", "")
                hint = node.attrib.get("hint", "")
                if "Enter name of Wi-Fi network" in (text, hint):
                    x, y = _get_center(node)
                    _execute_adb_command(f"shell input tap {x} {y}")
                    time.sleep(0.5)
                    escaped_ssid = _escape_text_for_input(ssid)
                    logging.info(f"Entering SSID: {ssid}")
                    _execute_adb_command(f"shell input text '{escaped_ssid}'")
                    ssid_input_found = True
                    break

            if not ssid_input_found:
                logging.error("SSID input field not found")
                _take_screenshot("no_ssid_field")
                return False

            # --- Step 5: Click Next/Connect ---
            next_keywords = ["Next", "Connect", "OK", "Continue"]
            if not _tap_text(_dump_ui(), next_keywords):
                logging.warning("Next button not found, trying ENTER key")
                _execute_adb_command("shell input keyevent KEYCODE_ENTER")
            time.sleep(2)

            # --- Step 6: Select Security Type ---
            root = _dump_ui()
            all_texts = [node.attrib.get("text", "") for node in root.iter("node")]

            # Check if we are on the security selection page
            if any("Type of security" in txt for txt in all_texts):
                logging.info("鉁?Found 'Type of security' page")

                # Define mapping from test case security to UI text
                security_mapping = {
                    "None": ["None"],
                    "Enhanced Open": ["Enhanced Open"],
                    "WEP": ["WEP"],
                    "WPA/WPA2": ["WPA/WPA2-Personal"],
                    "WPA3": ["WPA3-Personal"]
                }

                target_options = security_mapping.get(security, [security])
                logging.info(f"Trying to select security: {target_options}")

                if _tap_text(root, target_options):
                    logging.info(f"鉁?Successfully selected security: {security}")
                else:
                    logging.warning(f"鈿狅笍 Could not find security option: {target_options}")

            # --- Step 7: Input Password if needed ---
            if password and password.strip():
                logging.info(f"Inputting password: {password}")

                # Wait for password page
                password_page_found = False
                for wait_attempt in range(5):
                    time.sleep(1)
                    root = _dump_ui()
                    all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                    if any("Enter password" in txt for txt in all_texts):
                        password_page_found = True
                        break

                if not password_page_found:
                    logging.warning("Password page not detected, proceeding anyway...")

                password_input_found = False

                # Method 1: Try to find by class and position
                for node in root.iter("node"):
                    node_class = node.attrib.get("class", "")
                    clickable = node.attrib.get("clickable", "")
                    focusable = node.attrib.get("focusable", "")

                    if ("EditText" in node_class or "TextView" in node_class) and \
                            clickable == "true" and focusable == "true":

                        # Additional check: should be empty (no text)
                        if node.attrib.get("text", "") == "":
                            x, y = _get_center(node)
                            _execute_adb_command(f"shell input tap {x} {y}")
                            time.sleep(0.5)
                            escaped_pwd = _escape_text_for_input(password)
                            _execute_adb_command(f"shell input text '{escaped_pwd}'")
                            password_input_found = True
                            logging.info("鉁?Password input field found by class properties")
                            break

                # Method 2: Fallback to fixed position if not found
                if not password_input_found:
                    logging.info("Using fallback: clicking fixed password position")
                    _execute_adb_command("shell input tap 540 650")  # Middle of screen, adjust as needed
                    time.sleep(0.5)
                    escaped_pwd = _escape_text_for_input(password)
                    _execute_adb_command(f"shell input text '{escaped_pwd}'")

                    # --- Step: Submit password using multiple fallback strategies ---
                    def _submit_password_input(serial, execute_adb_func, dump_ui_func, timeout=8):
                        """
                        Robustly submit password input using multiple strategies.
                        Works across different devices, resolutions, and IMEs.
                        """
                        import time
                        import logging

                        # Strategy 1: Try KEYCODE_ENTER (most universal)
                        logging.info("馃攼 [Strategy 1] Submitting via KEYCODE_ENTER")
                        execute_adb_func("shell input keyevent KEYCODE_ENTER")
                        time.sleep(2)

                        # Check if we've left the password page
                        root = dump_ui_func()
                        all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                        if not any("Enter password" in t or "password" in t.lower() for t in all_texts):
                            logging.info("鉁?Password submitted successfully via KEYCODE_ENTER")
                            return True

                        # Strategy 2: Dynamic coordinate click (bottom-right area)
                        logging.info("馃攼 [Strategy 2] Trying dynamic coordinate click")

                        # Get logical screen size safely
                        try:
                            wm_output = DeviceUiFeature._run_adb(f"adb -s {serial} shell wm size")
                            lines = wm_output.strip().split('\n')
                            size_line = lines[-1]  # Usually last line has the size
                            if 'x' in size_line:
                                w, h = map(int, size_line.split()[-1].split('x'))
                            else:
                                w, h = 1080, 2340
                        except Exception as e:
                            logging.warning(f"Failed to parse screen size, using default: {e}")
                            w, h = 1080, 2340

                        logging.info(f"Screen logical size: {w}x{h}")

                        # Click bottom-right corner (where IME confirm button usually is)
                        confirm_x = int(w * 0.90)  # 90% from left
                        confirm_y = int(h * 0.95)  # 95% from top
                        logging.info(f"Clicking IME confirm at ({confirm_x}, {confirm_y})")
                        execute_adb_func(f"shell input tap {confirm_x} {confirm_y}")
                        time.sleep(2)

                        # Re-check page
                        root = dump_ui_func()
                        all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                        if not any("Enter password" in t or "password" in t.lower() for t in all_texts):
                            logging.info("鉁?Password submitted successfully via coordinate click")
                            return True

                        # Strategy 3: Try common IME button texts
                        logging.info("馃攼 [Strategy 3] Trying IME button text match")
                        ime_keywords = ["Go", "Next", "Done", "Continue", "Enter"]
                        for keyword in ime_keywords:
                            for node in root.iter("node"):
                                if keyword in node.attrib.get("text", ""):
                                    bounds = node.attrib.get("bounds", "")
                                    import re
                                    coords = list(map(int, re.findall(r"\d+", bounds)))
                                    if len(coords) == 4:
                                        x = (coords[0] + coords[2]) // 2
                                        y = (coords[1] + coords[3]) // 2
                                        execute_adb_func(f"shell input tap {x} {y}")
                                        time.sleep(2)
                                        logging.info(f"Clicked IME button: '{keyword}'")

                                        # Final check
                                        root = dump_ui_func()
                                        all_texts = [n.attrib.get("text", "") for n in root.iter("node")]
                                        if not any("Enter password" in t for t in all_texts):
                                            logging.info("鉁?Password submitted via IME text button")
                                            return True
                                        break

                        logging.error("鉂?All password submission strategies failed")
                        return False

                    # --- Call the robust submit function ---
                    logging.info("馃攼 Submitting password with multi-strategy approach")
                    password_submitted = _submit_password_input(
                        serial=serial,
                        execute_adb_func=_execute_adb_command,
                        dump_ui_func=_dump_ui
                    )

                    if not password_submitted:
                        logging.warning("Password submission may have failed. Continuing anyway...")

            time.sleep(30)
            return True

        except Exception as e:
            logging.exception(f"Error in _add_manual_wifi_network: {e}")
            _take_screenshot("exception")
            return False

    @staticmethod
    def _check_network_ping(serial: str):
        """
           Check network connectivity by pinging 8.8.8.8.

           Performs a ping test and optionally retries on failure to handle
           slow network initialization.

           Args:
               serial (str): ADB serial of the target device.
               retries (int): Number of retry attempts after initial failure.
               delay_before_check (float): Seconds to sleep before the first ping.

           Returns:
               bool: True if ping succeeds in any attempt, False otherwise.
       """
        for attempt in range(5):
            try:
                output = DeviceUiFeature._run_adb_capture_output(
                    f"adb -s {serial} shell ping -c 10 8.8.8.8",
                    timeout=10
                ) #8.8.8.8 111.45.11.5
                # 妫€鏌ユ槸鍚︽敹鍒板洖澶嶏紙鍏稿瀷鎴愬姛杈撳嚭鍖呭惈 "bytes from 8.8.8.8"锛?
                if "bytes from 8.8.8.8" in output or "64 bytes from" in output:
                    logging.info(f"Ping succeeded, {output}")
                    return True
                else:
                    logging.warning(f"Ping failed (attempt {attempt + 1}), output:\n{output}")
            except Exception as e:
                logging.warning(f"Ping command failed (attempt {attempt + 1}): {e}")

            if attempt == 0:
                time.sleep(30)

        return False

    def reset_settings_ui(self, serial: str, timeout: int = 5) -> bool:
        """
        閫氱敤鏂规硶锛氬己鍒堕€€鍑哄崱姝荤殑 Wi-Fi 璁剧疆鐣岄潰锛屽苟杩斿洖鍒板共鍑€鐨勪富璁剧疆椤甸潰鎴?Home銆?

        鏀寔澶氱 Android DUT锛?
          - 鏍囧噯 Android (com.android.settings)
          - Android TV (com.android.tv.settings)
          - Google TV / Chromecast
          - 鍗庣銆佸皬绫崇瓑瀹氬埗 ROM

        澶嶇敤鏈被宸叉湁鐨?_run_adb 鍜?_go_to_home 鏂规硶銆?

        Args:
            serial (str): ADB 璁惧搴忓垪鍙?
            timeout (int): 姣忔鎿嶄綔绛夊緟鏃堕棿锛堢锛?

        Returns:
            bool: True if success, False otherwise
        """
        # Step 1: 鑾峰彇鎵€鏈夊凡瀹夎鐨勫寘锛堜娇鐢?_run_adb_capture_output 澶嶇敤鐜版湁閫昏緫锛?
        try:
            output = self._run_adb_capture_output(
                f"adb -s {serial} shell pm list packages", timeout=timeout + 5
            )
            if not output:
                logging.warning(f"[UI Reset] Failed to list packages on {serial}")
                installed_packages = set()
            else:
                installed_packages = {
                    line.strip().replace("package:", "")
                    for line in output.splitlines()
                    if line.strip().startswith("package:")
                }
        except Exception as e:
            logging.error(f"[UI Reset] Exception while listing packages: {e}")
            installed_packages = set()

        # Step 2: 瀹氫箟鍊欓€夌殑 (package, activity) 鍒楄〃锛屾寜浼樺厛绾ф帓搴?
        candidates = [
            # Android TV (Google 瀹樻柟)
            ("com.android.tv.settings", ".MainSettings"),
            ("com.android.tv.settings", ".settings.MainSettings"),

            # Standard Android (Phone/Tablet)
            ("com.android.settings", ".Settings"),
            ("com.android.settings", ".homepage.SettingsHomepageActivity"),

            # Google TV / Chromecast
            ("com.google.android.tv.settings", ".MainSettings"),
            ("com.google.android.tv.settings", ".homepage.SettingsHomepageActivity"),

            # ASUS TV
            ("com.asus.tv.settings", ".MainActivity"),
            ("com.asus.tv.settings", ".SettingsActivity"),

            # Xiaomi / MIUI
            ("com.miui.settings", ".Settings"),

            # Samsung
            ("com.sec.android.app.settings", ".Settings"),
        ]

        # Step 3: 灏濊瘯 force-stop + restart 姣忎釜瀛樺湪鐨勫€欓€?
        for package, activity in candidates:
            if package not in installed_packages:
                continue  # 璺宠繃鏈畨瑁呯殑鍖?

            try:
                # 寮哄埗鍋滄鏁翠釜搴旂敤锛堝鐢?_run_adb锛?
                self._run_adb(f"adb -s {serial} shell am force-stop {package}")
                time.sleep(1)

                # 灏濊瘯鍚姩涓荤晫闈紙澶嶇敤 _run_adb锛?
                self._run_adb(f"adb -s {serial} shell am start -n {package}{activity}")
                time.sleep(timeout)

                logging.info(f"[UI Reset] Successfully restarted {package}{activity} on {serial}")
                return True

            except Exception as e:
                logging.debug(f"[UI Reset] Failed to restart {package}{activity}: {e}")
                continue

        # Step 4: 鎵€鏈?Settings 閲嶅惎閮藉け璐?鈫?鍥為€€鍒?Home Screen锛堜繚搴曟柟妗堬級
        # 鐩存帴澶嶇敤宸叉湁鐨?_go_to_home 闈欐€佹柟娉曪紒
        logging.warning("[UI Reset] All Settings restart attempts failed. Falling back to Home.")
        return DeviceUiFeature._go_to_home(serial, timeout=timeout)

    import re

    @staticmethod
    @staticmethod
    def get_wifi_country_code(serial: str, timeout: int = 8) -> str:
        """
        Get the effective Wi-Fi regulatory country code via 'iw reg get' on the device.

        Returns:
            str: Country code in uppercase (e.g., "US", "CN", "DE"). Returns empty string if failed.
        """
        try:
            cmd = f"adb -s {serial} shell iw reg get"
            logging.debug(f"Executing: {cmd}")
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode != 0:
                logging.error(f"Failed to run 'iw reg get' on {serial}: {result.stderr.strip()}")
                return ""

            output = result.stdout.strip()
            logging.info(f"iw reg get info: {output}")
            if not output:
                logging.warning(f"'iw reg get' returned empty output on {serial}")
                return ""

            # Parse the output to find the global country line
            lines = output.splitlines()
            in_global_section = False
            for line in lines:
                line = line.strip()
                if line == "global":
                    in_global_section = True
                    continue
                if in_global_section and line.startswith("country "):
                    # Extract country code (ensure it's uppercase)
                    # Match exactly 2 capital letters after "country"
                    match = re.search(r'country\s+([A-Z]{2})', line)
                    if match:
                        country_code = match.group(1).upper()  # Double ensure uppercase
                        logging.info(f"鉁?Successfully retrieved country code: {country_code}")
                        return country_code  # <-- 鐩存帴杩斿洖瀛楃涓?"US"
                    else:
                        logging.warning(f"Regex did not match country code in line: {line}")
                        break  # Exit loop if format is wrong
                # Exit if we are past the global section (optional optimization)
                elif in_global_section and line.startswith("country") is False and line != "":
                    break

            logging.warning(f"Could not find valid country code in 'iw reg get' output.")
            return ""

        except subprocess.TimeoutExpired:
            logging.error(f"鈴?Timeout while running 'iw reg get' on {serial}")
            return ""
        except Exception as e:
            logging.exception(f"馃挜 Exception in get_wifi_country_code: {e}")
            return ""

    def set_wifi_country_code(self, serial: str, country_code: str, timeout: int = 8) -> dict:
        """
        Set the Wi-Fi regulatory country code.

        Returns:
            dict: Always returns a dictionary with 'status', 'message', '2g_channels' (list), '5g_channels' (list).
        """
        # --- 棰戠巼鑼冨洿鍒颁俊閬撳垪琛ㄧ殑鏄犲皠琛?(淇鐗? ---
        # 杩欓噷瀹氫箟鏍囧噯鐨勯鐜囪寖鍥村搴旂殑淇￠亾
        FREQUENCY_TO_CHANNEL_MAP = {
            # --- 2.4G 棰戞 ---
            # 鎴戜滑浣跨敤鑼冨洿鏉ュ畾涔夛紝浠ｇ爜閫昏緫浼氬垽鏂叿浣撳睘浜庡摢涓寖鍥?
            # (min_freq, max_freq): [channels]
            # 鎯呭喌1: 棰戠巼涓婇檺鍦?2472 宸﹀彸 (鍖呭惈 Ch 1-11)
            # 鎯呭喌2: 棰戠巼涓婇檺鍦?2483 宸﹀彸 (鍖呭惈 Ch 1-13)
            # 鎯呭喌3: 棰戠巼涓婇檺鍦?2494 宸﹀彸 (鍖呭惈 Ch 1-14锛岄€氬父浠呮棩鏈?

            # --- 5G 棰戞 ---
            # 瀹氫箟甯歌鐨?5G 棰戞鑼冨洿
            (5150, 5250): [36, 40, 44, 48],  # UNII-1
            (5250, 5350): [52, 56, 60, 64],  # UNII-2A (DFS)
            (5470, 5730): [100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144],  # UNII-2C (DFS)
            (5735, 5835): [149, 153, 157, 161, 165],  # UNII-3
            #(5850, 5895): [169, 173, 177],  # UNII-4 (閮ㄥ垎璁惧)
        }

        def map_frequency_to_channels(freq_start: int, freq_end: int) -> List[int]:
            """
            鏍规嵁棰戠巼鑼冨洿鏌ユ壘瀵瑰簲鐨勪俊閬撳垪琛ㄣ€?
            閫昏緫锛?
            1. 濡傛灉鏄?2.4G 棰戞锛屾牴鎹粨鏉熼鐜囧垽鏂槸 Ch 1-11 杩樻槸 1-13銆?
            2. 濡傛灉鏄?5G 棰戞锛屾煡鎵炬槧灏勮〃銆?
            """
            channels = []

            # --- 2.4G 閫昏緫 (鏍稿績淇) ---
            if 2400 <= freq_start < 2500:
                # 鏍规嵁缁撴潫棰戠巼鍒ゆ柇
                if freq_end <= 2472:
                    # 鍙敮鎸佸埌 2472 (Ch 11)
                    channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
                    logging.debug(f"2.4G Logic: {freq_start}-{freq_end} -> Ch 1-11")
                elif freq_end <= 2483:
                    # 鏀寔鍒?2483 (Ch 13)
                    channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
                    logging.debug(f"2.4G Logic: {freq_start}-{freq_end} -> Ch 1-13")
                else:
                    # 鏀寔鍒?2494 (Ch 14)
                    channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
                    logging.debug(f"2.4G Logic: {freq_start}-{freq_end} -> Ch 1-14")

            # --- 5G 閫昏緫 ---
            elif freq_start >= 5000:
                # 閬嶅巻鏄犲皠琛紝妫€鏌ユ槸鍚︽湁閲嶅彔
                for (f_min, f_max), ch_list in FREQUENCY_TO_CHANNEL_MAP.items():
                    if freq_start <= f_max and freq_end >= f_min:
                        channels.extend(ch_list)

            return sorted(list(set(channels)))

        try:
            # 1. Set the country code (Assuming this part is handled elsewhere or not needed here)
            # If you need to set it, uncomment the following:
            # cmd_set = f"adb -s {serial} shell iw reg set {country_code}"
            # ... (subprocess.run for set) ...
            cmd_set = f"adb -s {serial} shell iw reg set {country_code}"
            result_get = subprocess.run(
                cmd_set,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            logging.info(f"iw reg set info: {result_get}")

            cmd_reload = f"adb -s {serial} shell iw reg reload"
            result_get = subprocess.run(
                cmd_reload,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            logging.info(f"iw reg reload info: {result_get}")

            # 2. Get status
            cmd_get = f"adb -s {serial} shell iw reg get"
            result_get = subprocess.run(
                cmd_get,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            #logging.info(f"iw reg get info: {result_get}")
            if result_get.returncode != 0:
                error_msg = f"Failed to run 'iw reg get': {result_get.stderr.strip()}"
                logging.error(error_msg)
                return {
                    'status': False,
                    'message': error_msg,
                    '2g_channels': [],
                    '5g_channels': []
                }

            output = result_get.stdout.strip()
            if not output:
                error_msg = "Empty output from 'iw reg get'"
                logging.error(error_msg)
                return {
                    'status': False,
                    'message': error_msg,
                    '2g_channels': [],
                    '5g_channels': []
                }

            # --- 瑙ｆ瀽閫昏緫 ---
            lines = output.splitlines()
            in_global_section = False
            all_2g_channels = set()
            all_5g_channels = set()

            for line in lines:
                line = line.strip()
                if line == "global":
                    in_global_section = True
                    continue
                if in_global_section:
                    # 閬囧埌涓嬩竴涓?section 鎴栫┖琛岀粨鏉?
                    if line and not line.startswith("(") and not line.startswith("country"):
                        break
                    if line.startswith("("):
                        match = re.search(r'\((\d+)\s*-\s*(\d+)', line)
                        if match:
                            freq_start = int(match.group(1))
                            freq_end = int(match.group(2))
                            logging.debug(f"Detected Frequency Range: {freq_start} - {freq_end}")

                            # --- 鏍稿績杞崲閫昏緫 ---
                            channels = map_frequency_to_channels(freq_start, freq_end)

                            # 鏍规嵁棰戠巼鍒ゆ柇棰戞
                            if 2400 <= freq_start < 2500:
                                all_2g_channels.update(channels)
                                logging.info(f"鉁?Matched 2.4G channels: {channels} for range {freq_start}-{freq_end}")
                            elif 5000 <= freq_start < 5925:
                                all_5g_channels.update(channels)
                                logging.info(f"鉁?Matched 5G channels: {channels} for range {freq_start}-{freq_end}")
                            elif freq_start >= 5925:
                                logging.debug(f"Ignoring 6G band frequency: {freq_start}-{freq_end}")

            # 杞崲涓烘帓搴忓垪琛?
            ch_2g_list = sorted(list(all_2g_channels))
            ch_5g_list = sorted(list(all_5g_channels))

            result_dict = {
                'status': True,
                'message': f"Country {country_code} channels parsed",
                '2g_channels': ch_2g_list,
                '5g_channels': ch_5g_list
            }

            logging.info(f"鉁?Final Result: {result_dict}")
            return result_dict

        except Exception as e:
            error_msg = f"Exception: {e}"
            logging.exception(error_msg)
            return {
                'status': False,
                'message': error_msg,
                '2g_channels': [],
                '5g_channels': []
            }

    def set_wifi_country_code_default(self, serial: str, country_code: str, timeout: int = 8) -> dict:
        """
        Set the Wi-Fi regulatory country code to default.

        Returns:
            dict: Always returns a dictionary with 'status' (bool) and 'message' (str).
        """
        try:
            # 1. Set the country code
            cmd_set = f"adb -s {serial} shell iw reg set {country_code}"
            logging.debug(f"Executing: {cmd_set}")
            result_set = subprocess.run(
                cmd_set,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result_set.returncode != 0:
                error_msg = f"鉂?Failed to run 'iw reg set {country_code}': {result_set.stderr.strip()}"
                logging.error(error_msg)
                # --- 淇敼鐐癸細杩斿洖閿欒瀛楀吀 ---
                return {
                    'status': False,
                    'message': error_msg,
                    '2g_channels': [],
                    '5g_channels': []
                }

            logging.info(f"鉁?Successfully sent 'iw reg set {country_code}' command.")

            # --- 淇敼鐐癸細鎴愬姛鏃惰繑鍥炲瓧鍏?---
            return {
                'status': True,
                'message': f"Default country {country_code} set",
                '2g_channels': ['2412-2472'],  # 绀轰緥鏁版嵁锛屽疄闄呭彲鑳介渶瑕佽В鏋?
                '5g_channels': ['5180-5320', '5745-5825']
            }

        except Exception as e:
            error_msg = f"馃挜 Exception in set_wifi_country_code_default: {e}"
            logging.exception(error_msg)
            # --- 淇敼鐐癸細杩斿洖閿欒瀛楀吀 ---
            return {
                'status': False,
                'message': error_msg,
                '2g_channels': [],
                '5g_channels': []
            }

