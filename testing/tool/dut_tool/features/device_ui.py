from __future__ import annotations

import xml.etree.ElementTree as ET
import logging
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from testing.params.adb_devices import resolve_adb_serial_for_command

import uiautomator2 as u2

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


def launch_youtube_tv_and_search(serial: str, logdir: Path, query: str = "NASA"):
    """Launch YouTube TV and search for a channel on Android TV."""
    try:
        _run_adb(
            f"adb -s {serial} shell am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity"
        )
        time.sleep(8)
        for _ in range(4):
            _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_RIGHT")
            time.sleep(0.5)
        _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
        time.sleep(2)
        _run_adb(f"adb -s {serial} shell input text '{query}'")
        time.sleep(1)
        _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
        time.sleep(5)
        logging.info("YouTube TV search completed.")
        for _ in range(3):
            _go_to_home(serial)
            time.sleep(1)
        return True
    except Exception as exc:
        logging.error("YouTube TV automation failed: %s", exc)
        return False

def wifi_is_valid_ssid(text: str) -> bool:
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

def _go_to_home(serial: str, timeout: int = 5) -> bool:
    try:
        _run_adb(
            f"adb -s {serial} shell am start -a android.intent.action.MAIN -c android.intent.category.HOME"
        )
        return True
    except Exception as exc:
        logging.exception("Failed to go home on %s: %s", serial, exc)
        return False

def _open_wifi_settings_page(serial: str) -> bool:
    try:
        _go_to_home(serial)
        _run_adb(f"adb -s {serial} shell am start -a android.settings.WIFI_SETTINGS")
        return True
    except Exception as exc:
        logging.exception("Failed to open Wi-Fi settings on %s: %s", serial, exc)
        return False

def get_connected_ssid_via_cli_adb(serial):
    output = _run_adb_capture_output(
        f"adb -s {serial} shell su 0 iw dev wlan0 link",
        timeout=8,
    )
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("SSID:"):
            return line[5:].strip()
    return ""

def _disconnect_and_prevent_reconnect(serial: str, timeout: int = 10) -> bool:
    """
    Disconnect from current Wi-Fi and prevent auto-reconnect by removing the network.
    This ensures device stays disconnected for subsequent test steps.
    """
    try:
        output = _run_adb_capture_output(
            f"adb -s {serial} shell wpa_cli list_networks",
            timeout=timeout,
        )
        lines = output.strip().split('\n')
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
        _run_adb(f"adb -s {serial} shell wpa_cli remove_network {current_net_id}")
        logging.info("Removed network ID %s on %s to prevent reconnect", current_net_id, serial)
        time.sleep(2)
        return True

    except Exception as e:
        logging.error(f"Exception in _disconnect_and_prevent_reconnect on {serial}: {e}")
        return False

def _run_adb(cmd: str) -> None:
    """Run an ADB command."""
    try:
        normalized_cmd = _normalize_adb_command(cmd)
        result = subprocess.run(
            normalized_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # 閼奉亜濮╂径鍕倞 stdout/stderr
            text=True,  # 鏉╂柨娲栫€涙顑佹稉鑼垛偓宀勬姜 bytes
            timeout=30,
            # 闂冨弶顒涢崣銉︾労濞夊嫭绱?
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

# 閸?ui_mixin.py 娑擃叏绱滵eviceUiFeature 缁鍞村ǎ璇插閿?
def _run_adb_capture_output(cmd: str, timeout: int = 10) -> str:
    """Run an ADB command and return stdout for parsing."""
    try:
        normalized_cmd = _normalize_adb_command(cmd)
        result = subprocess.run(
            normalized_cmd,
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

def _normalize_adb_command(cmd: str) -> str:
    text = str(cmd or "").strip()
    match = re.match(r"^(adb)\s+-s\s+(\S+)(\s+.*)?$", text)
    if not match:
        return text
    serial = resolve_adb_serial_for_command(match.group(2))
    suffix = str(match.group(3) or "")
    if serial:
        return f"adb -s {serial}{suffix}"
    return f"adb{suffix}"

def _dump_ui(serial: str, logdir: Optional[Path] = None) -> Any:
    """Dump the current UI hierarchy and return the parsed XML root."""
    remote_path = "/sdcard/window_dump.xml"
    if logdir is None:
        # 閸掓稑缂撴稉鈧稉顏嗘埂濮濓絿娈戞稉瀛樻閺傚洣娆㈤敍鍫ｅ殰閸斻劌鍨归梽銈忕礆
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.xml') as tmp:
            local_path = Path(tmp.name)
    else:
        local_path = logdir / f"ui_dump_{int(time.time())}.xml"

    try:
        # 閹笛嗩攽 dump 閸?pull
        _run_adb(f"adb -s {serial} shell uiautomator dump {remote_path} --compressed")
        _run_adb(f"adb -s {serial} pull {remote_path} {local_path}")

        # 閸忔娊鏁敍姘愁嚢閸欐牗鏋冩禒璺哄敶鐎圭懓鍩岄崘鍛摠閿涘苯鍟€鐟欙絾鐎?
        with open(local_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        root = ET.fromstring(xml_content)

        logging.debug(f"[DEBUG] UI dumped and parsed from: {local_path}")
        return root

    except Exception as e:
        logging.error(f"Failed to dump or parse UI: {e}")
        raise

    finally:
        # 閸欘亝婀佹稉瀛樻閺傚洣娆㈤幍宥呭灩闂勩倧绱欐稉鏃傗€樻穱婵嗗嚒鐠囪鍙嗛崘鍛摠閿?
        if logdir is None and local_path.exists():
            local_path.unlink() # 韫囩晫鏆愰崚鐘绘珟婢惰精瑙?
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

            # 娴兼ê鍘涙禒?content-desc 鐟欙絾鐎?
            content_desc = node.attrib.get("content-desc", "")
            if content_desc:
                ssid_from_desc = content_desc.split(",")[0].strip()
                clean_candidate = clean_text(ssid_from_desc)
                if target_clean in clean_candidate or clean_candidate in target_clean:
                    return x, y

            # 閸忚埖顐兼禒搴＄摍閼哄倻鍋?text 鐟欙絾鐎?
            for child in node.iter("node"):
                child_text = child.attrib.get("text", "").strip()
                if child_text:
                    clean_candidate = clean_text(child_text)
                    if target_clean in clean_candidate or clean_candidate in target_clean:
                        logging.info(f"[DEBUG] 閴?Match via child text! Raw: '{child_text}' 閳?Click at ({x}, {y})")
                        return x, y

    logging.info(f"[DEBUG] 閴?SSID '{target_ssid}' not found.")
    return None

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
                reset_settings_ui(serial)
            except Exception as e:
                logging.warning(f"[UI Connect] Failed to reset settings UI: {e}")
            success = _go_to_home(serial)
            _open_wifi_settings_page(serial)
            time.sleep(2)

            # Step 2: Click "See all"
            see_all_texts = ["See all", "See all networks", "閸忋劑鍎寸純鎴犵捕", "閺屻儳婀呴崗銊╁劥", "Show all"]
            logging.info(f"[DEBUG] Looking for 'See all' keywords: {see_all_texts}")
            for retry in range(5):
                logging.info(f"\nAttempt {retry + 1}/5 to find 'See all' ---")
                root = _dump_ui(serial, logdir)
                pos = _find_clickable_parent_of_text(root, see_all_texts)
                if pos:
                    logging.info(f"[INFO] Clicking 'See all' at ({pos[0]}, {pos[1]})")
                    _run_adb(f"adb -s {serial} shell input tap {pos[0]} {pos[1]}")
                    time.sleep(4)
                    break
                time.sleep(2)

            # Step 3: Scroll to bottom
            logging.info("[INFO] Scrolling to bottom of network list...")
            for _ in range(15):
                _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_DOWN")
                time.sleep(0.3)

            # Step 4: Find and click target SSID
            for attempt in range(30):
                root = _dump_ui(serial, logdir)
                pos = _find_ssid_in_list(root, ssid)
                logging.info(f"[INFO] Found pos: {pos}")
                if pos:
                    x, y = pos
                    logging.info(f"[INFO] Found SSID '{ssid}' at screen position ({x}, {y}). Tapping directly.")
                    _run_adb(f"adb -s {serial} shell input tap {x} {y}")
                    time.sleep(1.0)

                    # Input password
                    if password:
                        logging.info(f"[INFO] Password required. Entering password.")
                        _run_adb(f"adb -s {serial} shell input text '{password}'")
                        time.sleep(0.5)

                        # Try to Connect
                        try:
                            root_post = _dump_ui(serial, logdir)
                            for node in root_post.iter("node"):
                                text = node.attrib.get("text", "").strip().lower()
                                if text in ["connect", "ok"]:
                                    bounds = node.attrib.get("bounds", "")
                                    coords = list(map(int, re.findall(r"\d+", bounds)))
                                    if len(coords) == 4:
                                        btn_x = (coords[0] + coords[2]) // 2
                                        btn_y = (coords[1] + coords[3]) // 2
                                        _run_adb(f"adb -s {serial} shell input tap {btn_x} {btn_y}")
                                        logging.info("[INFO] Clicked 'Connect' button.")
                                        break
                            else:
                                logging.info("[INFO] 'Connect' not found. Sending ENTER.")
                                _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
                        except Exception as e:
                            logging.warning(f"[WARN] Failed to click Connect: {e}. Using ENTER fallback.")
                            _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")

                        time.sleep(2.0)
                    else:
                        time.sleep(2.0)

                    time.sleep(30)
                    return True

                for _ in range(5):
                    _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_UP")
                    time.sleep(0.1)

        except Exception as e:
            if retry_count == 0:
                logging.info("[UI Connect] Retrying in 60 seconds...")
                time.sleep(60)
                # 缂佈呯敾婢舵牕鐪板顏嗗箚閻ㄥ嫪绗呮稉鈧▎陇鍑禒?
                continue
            else:
                # 婵″倹鐏夐弰顖滎儑娴滃本顐肩亸婵婄槸娑旂喎銇戠拹銉ょ啊閿涘矁绻戦崶?False
                logging.error("[UI Connect] Failed to connect after 2 attempts.")
                return False
    return False

def _clear_saved_wifi_networks(serial: str):
    """Clear saved Wi-Fi """
    try:
        logging.info(f"棣冃?Clearing all saved Wi-Fi networks on {serial}...")

        # Step 1: Try CLI commands
        cli_success = _clear_all_wifi_records(serial)
        if cli_success:
            logging.info("閴?All networks removed via 'cmd wifi'.")
        else:
            # Step 2: CLI failed閿涘瘈se wpa_cli command
            logging.warning("閳跨媴绗?CLI method failed. Falling back to wpa_cli disconnect.")
            _disconnect_and_prevent_reconnect(serial)
            time.sleep(2)

        # Step 3: Close Wi-Fi Service
        _run_adb(f"adb -s {serial} shell svc wifi disable")
        time.sleep(2)

        # Step 4: Deleted config files
        _run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/*.conf")
        _run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/wpa_supplicant.conf")
        logging.info("閴?Deleted Wi-Fi config files (fallback cleanup).")

        # Step 5: Enable Wi-Fi
        _run_adb(f"adb -s {serial} shell svc wifi enable")
        time.sleep(5)

        logging.info("閴?Wi-Fi cleanup completed.")
    except Exception as e:
        logging.error(f"閴?Failed to clear Wi-Fi networks: {e}")

def _list_saved_networks(serial: str) -> List[int]:
    try:
        output = _run_adb_capture_output(
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

def _clear_all_wifi_records(serial: str) -> bool:
    try:
        logging.info(f"棣冃?Using 'cmd wifi forget-network' on {serial}...")

        # 1. Disabled Wi-Fi
        _run_adb(f"adb -s {serial} shell svc wifi disable")
        time.sleep(2)

        # 2. Get networkId閿涘牆骞撻柌?+ 閹烘帒绨敍?
        try:
            output = _run_adb_capture_output(
                f"adb -s {serial} shell cmd wifi list-saved-networks", timeout=8
            )
            network_ids = sorted(set(int(line.strip()) for line in output.splitlines() if line.strip().isdigit()))
        except Exception as e:
            logging.warning(f"Failed to list networks, assuming none: {e}")
            network_ids = []

        # 3. forget everyone
        if network_ids:
            for nid in network_ids:
                _run_adb(f"adb -s {serial} shell cmd wifi forget-network {nid}")
                logging.debug("Forgot network %s", nid)
                time.sleep(0.3)
        else:
            logging.info("No saved networks to forget.")

        # 4. Delete config files
        _run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/*.conf")
        _run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/wpa_supplicant.conf")

        # 5. Enable Wi-Fi
        _run_adb(f"adb -s {serial} shell svc wifi enable")
        time.sleep(5)

        logging.info("閴?Wi-Fi cleanup via 'cmd wifi forget-network' completed.")
        return True

    except Exception as e:
        logging.error(f"閴?Cleanup failed: {e}")
        return False

def _forget_wifi_via_ui(serial: str, target_ssid: str = "None"):
    logging.info(f"棣冃?Forgetting Wi-Fi '{target_ssid}' via UI on {serial}...")

    target_ssid = get_connected_ssid_via_cli_adb(serial)

    reset_settings_ui(serial)
    # Open Wi-Fi Settings
    _open_wifi_settings_page(serial)
    time.sleep(5)

    # Ensure Wi-Fi is on
    state = _run_adb_capture_output(f"adb -s {serial} shell settings get global wifi_on").strip()
    if state == "0":
        _run_adb(f"adb -s {serial} shell svc wifi enable")
        time.sleep(5)

    # Step 1: Find and click the SSID (with retry)
    # Step 1: Find and click the SSID (click twice to ensure it works on STB)
    root = _dump_ui(serial)
    pos = _find_clickable_parent_of_text(root, [target_ssid])
    if not pos:
        logging.error(f"SSID '{target_ssid}' not found in Wi-Fi list.")
        return False

    x, y = pos
    logging.info(f"閴?Found SSID '{target_ssid}' at ({x}, {y}). Clicking twice...")

    # First click
    _run_adb(f"adb -s {serial} shell input tap {x} {y}")
    time.sleep(1)

    # Second click (to ensure it registers on STB)
    _run_adb(f"adb -s {serial} shell input tap {x} {y}")
    time.sleep(2)  # Give time to enter detail page
    detail_indicators = ["Forget", "Security", "IP settings", "Signal", target_ssid]
    root_check = _dump_ui(serial)
    in_detail_page = any(
        _find_clickable_parent_of_text(root_check, [keyword]) is not None
        for keyword in detail_indicators
    )

    if not in_detail_page:
        logging.error("閴?Still in Wi-Fi list or failed to enter network detail page. Exiting.")
        return False

    logging.info("閴?Confirmed: entered network detail page.")

    # Step 2: Scroll down to reveal 'Forget' button (STB uses DPAD)
    logging.info("鐚浄绗?Scrolling down to reveal 'Forget' button...")
    for i in range(8):  # Press DOWN
        _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_DOWN")
        time.sleep(0.3)

    time.sleep(1)

    # Step 3: Find and click 'Forget'
    root2 = _dump_ui(serial)
    forget_pos = _find_clickable_parent_of_text(root2, ["Forget", "Remove"])
    if forget_pos:
        fx, fy = forget_pos
        logging.info(f"閴?Found 'Forget' at ({fx}, {fy}). Clicking...")
        _run_adb(f"adb -s {serial} shell input tap {fx} {fy}")
        time.sleep(1)
    else:
        logging.error("閴?'Forget' button NOT FOUND!")
        return False

    # Step 4: Wait for confirmation dialog and click OK
    logging.info("棣冩敵 Waiting for 'Forget network' confirmation dialog...")
    for _ in range(5):  # 閺堚偓婢舵氨鐡戝?10 缁?
        root3 = _dump_ui(serial)
        ok_pos = _find_clickable_parent_of_text(root3, ["OK", "Confirm"])
        if ok_pos:
            ox, oy = ok_pos
            logging.info(f"閴?Found 'OK' at ({ox}, {oy}). Clicking...")
            _run_adb(f"adb -s {serial} shell input tap {ox} {oy}")
            logging.info("閴?Successfully forgot network via UI.")
            break
        time.sleep(1)

    else:
        logging.error("閴?'OK' button not found in confirmation dialog!")
        return False

    logging.info("鐚拑绗?Exiting Wi-Fi settings UI...")
    for _ in range(3):
        _run_adb(f"adb -s {serial} shell input keyevent KEYCODE_BACK")
        _go_to_home(serial)
        time.sleep(1)

    logging.info("閴?Exited Wi-Fi settings UI.")
    return True

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
        _run_adb(f"adb -s {serial} {cmd}")

    def _dump_ui():
        return _dump_ui(serial, logdir)

    def _tap_text(root, keywords: List[str]) -> bool:
        pos = _find_clickable_parent_of_text(root, keywords)
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
        if not _open_wifi_settings_page(serial):
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
                logging.info("閴?Successfully clicked 'Add new network' button")
                add_net_clicked = True
                break
            else:
                logging.warning(f"'Add new network' not found on attempt {attempt + 1}")
                # Try scrolling down in case button is off-screen
                _execute_adb_command("shell input swipe 500 1000 500 300 300")
                time.sleep(2)

        if not add_net_clicked:
            logging.error("閴?Failed to find and click 'Add new network' button")
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
                logging.info("閴?SSID input page loaded")
                break

        if not ssid_input_page:
            logging.error("閴?SSID input page did not appear after clicking 'Add new network'")
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
            logging.info("閴?Found 'Type of security' page")

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
                logging.info(f"閴?Successfully selected security: {security}")
            else:
                logging.warning(f"閳跨媴绗?Could not find security option: {target_options}")

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
                        logging.info("閴?Password input field found by class properties")
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
                    logging.info("棣冩敿 [Strategy 1] Submitting via KEYCODE_ENTER")
                    execute_adb_func("shell input keyevent KEYCODE_ENTER")
                    time.sleep(2)

                    # Check if we've left the password page
                    root = dump_ui_func()
                    all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                    if not any("Enter password" in t or "password" in t.lower() for t in all_texts):
                        logging.info("閴?Password submitted successfully via KEYCODE_ENTER")
                        return True

                    # Strategy 2: Dynamic coordinate click (bottom-right area)
                    logging.info("棣冩敿 [Strategy 2] Trying dynamic coordinate click")

                    # Get logical screen size safely
                    try:
                        wm_output = _run_adb(f"adb -s {serial} shell wm size")
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
                        logging.info("閴?Password submitted successfully via coordinate click")
                        return True

                    # Strategy 3: Try common IME button texts
                    logging.info("棣冩敿 [Strategy 3] Trying IME button text match")
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
                                        logging.info("閴?Password submitted via IME text button")
                                        return True
                                    break

                    logging.error("閴?All password submission strategies failed")
                    return False

                # --- Call the robust submit function ---
                logging.info("棣冩敿 Submitting password with multi-strategy approach")
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
            output = _run_adb_capture_output(
                f"adb -s {serial} shell ping -c 10 8.8.8.8",
                timeout=10
            ) #8.8.8.8 111.45.11.5
            # 濡偓閺屻儲妲搁崥锔芥暪閸掓澘娲栨径宥忕礄閸忕鐎烽幋鎰鏉堟挸鍤崠鍛儓 "bytes from 8.8.8.8"閿?
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

def reset_settings_ui(serial: str, timeout: int = 5) -> bool:
    """
    闁氨鏁ら弬瑙勭《閿涙艾宸遍崚鍫曗偓鈧崙鍝勫幢濮濊崵娈?Wi-Fi 鐠佸墽鐤嗛悾宀勬桨閿涘苯鑻熸潻鏂挎礀閸掓澘鍏遍崙鈧惃鍕瘜鐠佸墽鐤嗘い鐢告桨閹?Home閵?

    閺€顖涘瘮婢舵氨顫?Android DUT閿?
      - 閺嶅洤鍣?Android (com.android.settings)
      - Android TV (com.android.tv.settings)
      - Google TV / Chromecast
      - 閸楀海顢氶妴浣哥毈缁磭鐡戠€规艾鍩?ROM

    婢跺秶鏁ら張顒傝瀹稿弶婀侀惃?_run_adb 閸?_go_to_home 閺傝纭堕妴?

    Args:
        serial (str): ADB 鐠佹儳顦惔蹇撳灙閸?
        timeout (int): 濮ｅ繑顒為幙宥勭稊缁涘绶熼弮鍫曟？閿涘牏顫楅敍?

    Returns:
        bool: True if success, False otherwise
    """
    # Step 1: 閼惧嘲褰囬幍鈧張澶婂嚒鐎瑰顥婇惃鍕瘶閿涘牅濞囬悽?_run_adb_capture_output 婢跺秶鏁ら悳鐗堟箒闁槒绶敍?
    try:
        output = _run_adb_capture_output(
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

    # Step 2: 鐎规矮绠熼崐娆撯偓澶屾畱 (package, activity) 閸掓銆冮敍灞惧瘻娴兼ê鍘涚痪褎甯撴惔?
    candidates = [
        # Android TV (Google 鐎规ɑ鏌?
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

    # Step 3: 鐏忔繆鐦?force-stop + restart 濮ｅ繋閲滅€涙ê婀惃鍕偓娆撯偓?
    for package, activity in candidates:
        if package not in installed_packages:
            continue  # 鐠哄疇绻冮張顏勭暔鐟佸懐娈戦崠?

        try:
            # 瀵搫鍩楅崑婊勵剾閺佺繝閲滄惔鏃傛暏閿涘牆顦查悽?_run_adb閿?
            _run_adb(f"adb -s {serial} shell am force-stop {package}")
            time.sleep(1)

            # 鐏忔繆鐦崥顖氬З娑撹崵鏅棃顫礄婢跺秶鏁?_run_adb閿?
            _run_adb(f"adb -s {serial} shell am start -n {package}{activity}")
            time.sleep(timeout)

            logging.info(f"[UI Reset] Successfully restarted {package}{activity} on {serial}")
            return True

        except Exception as e:
            logging.debug(f"[UI Reset] Failed to restart {package}{activity}: {e}")
            continue

    # Step 4: 閹碘偓閺?Settings 闁插秴鎯庨柈钘夈亼鐠?閳?閸ョ偤鈧偓閸?Home Screen閿涘牅绻氭惔鏇熸煙濡楀牞绱?
    # 閻╁瓨甯存径宥囨暏瀹稿弶婀侀惃?_go_to_home 闂堟瑦鈧焦鏌熷▔鏇磼
    logging.warning("[UI Reset] All Settings restart attempts failed. Falling back to Home.")
    return _go_to_home(serial, timeout=timeout)


