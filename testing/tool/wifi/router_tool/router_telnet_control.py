import time,re
import logging
import traceback
from testing.tool.connect_tool.transports.telnet_tool import TelnetSession


class TelnetVerifier:
    """A simple, dedicated class for verifying router state via Telnet."""

    def __init__(self, host: str, password: str):
        self.host = host
        self.password = password
        self.session = None
        self.prompt = b":/tmp/home/root#"

    def __enter__(self):
        self.session = TelnetSession(host=self.host, port=23, timeout=10)
        self.session.open()

        # Login sequence
        self.session.read_until(b"login:", timeout=5)
        self.session.write(b"admin\n")
        self.session.read_until(b"Password:", timeout=5)
        self.session.write(self.password.encode("ascii") + b"\n")
        self.session.read_until(self.prompt, timeout=5)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    def run_command(self, cmd: str, sleep_time: float = 0.5) -> str:
        """
        Execute a command and return the stripped output.
        :param cmd: The command to execute.
        :param sleep_time: Time to wait for the command to complete.
        """
        self.session.write((cmd + "\n").encode("ascii"))
        time.sleep(sleep_time)  # Allow command to execute
        raw_output = self.session.read_until(self.prompt, timeout=5)
        output_str = raw_output.decode('utf-8', errors='ignore')
        # Parse the output: find the last non-empty line that is not the prompt
        lines = [line.strip() for line in output_str.splitlines() if line.strip()]
        for line in reversed(lines):
            if not line.endswith("#"):
                return line
        return ""

# === 频段配置与模式映射 ===
BAND_CONFIG = {
    '2g': {
        'interface': 'eth6',
        'nvram_prefix': 'wl0_',
        'default_ssid': 'AX86U_24G',
        'modes': {
            # mode_name: (net_mode, nmode_x, 11ax)
            'b-only':      ('b-only', 0, 0),
            'g-only':      ('g-only', 0, 0),
            'bg-mixed':    ('Legacy', 0, 0),
            'n-only':      ('n-only', 1, 0),
            'bgn-mixed':   ('auto',   1, 0),
            'auto':        ('auto',   1, 0),  # 默认 = bgn-mixed
        }
    },
    '5g': {
        'interface': 'eth7',
        'nvram_prefix': 'wl1_',
        'default_ssid': 'AX86U_5G',
        'modes': {
            # mode_name: (net_mode, nmode_x, 11ax)
            'a-only':        ('a-only',     0, 0),
            'an-only':       ('n-only',     1, 0),
            'an-ac-mixed':   ('ac-mixed',   2, 0),
            'ax-mixed':      ('ax-mixed',   3, 1),
            'auto':          ('ac-mixed',   2, 0),  # 5G auto 通常为 an/ac
        }
    }
}
_ASUS_ROUTER_MODE_MAP = {
    '2g': {
        'b-only':      '11b',
        'g-only':      '11g',
        'bg-mixed':    'Legacy',
        'n-only':      '11n',
        'bgn-mixed':   'auto',
        'auto':        'auto',
        'ax-only':     '11ax',
    },
    '5g': {
        'a-only':        '11a',
        'an-only':       '11n',
        'an-ac-mixed':   '11ac',
        'ax-mixed':      '11ax',
        'auto':          'auto',
    }
}

MODE_PARAM = {
    'Open System': 'openowe',   # Note: Some ASUS use 'open', but 'openowe' is common for "Open + WEP optional"
    'Shared Key': 'shared',
    'WPA2-Personal': 'psk2',
    'WPA3-Personal': 'sae',
    'WPA/WPA2-Personal': 'pskpsk2',
    'WPA2/WPA3-Personal': 'psk2sae',
}

SUPPORTED_AUTHENTICATION_METHODS = {
        'Open System': 'open',
        'Open System (Alternative)': 'openowe',
        'Shared Key': 'shared',          # WEP-64/128
        'WPA-Personal': 'psk',
        'WPA2-Personal': 'psk2',
        'WPA3-Personal': 'sae',
        'WPA/WPA2-Personal': 'pskpsk2',
        'WPA2/WPA3-Personal': 'psk2sae',
        # 未来可以在这里添加更多，例如:
        # 'WPA-Enterprise': 'wpa',
        # 'OWE': 'owe',
    }
VALID_INTERNAL_AUTH_VALUES = set(SUPPORTED_AUTHENTICATION_METHODS.values())

def configure_ap_wireless_mode(router, band='2g', mode='auto', ssid=None, password=None):
    """
    配置路由器无线模式（支持 2.4G / 5G），使用 AsusTelnetNvramControl 的 API。

    :param router: AsusTelnetNvramControl 实例（已连接）
    :param band: '2g' or '5g'
    :param mode: 模式名，如 'bgn-mixed', 'an-ac-mixed' 等（来自 BAND_CONFIG）
    :param ssid: 自定义 SSID
    :param password: 自定义密码
    """
    if band not in _ASUS_ROUTER_MODE_MAP:
        raise ValueError(f"Unsupported band: {band}. Use '2g' or '5g'.")

    # 1. 模式映射
    mode_map = _ASUS_ROUTER_MODE_MAP[band]
    if mode not in mode_map:
        supported_modes = ', '.join(mode_map.keys())
        raise ValueError(f"Mode '{mode}' not supported for {band}. Supported: {supported_modes}")

    native_mode = mode_map[mode]  # e.g., 'bgn-mixed' -> 'auto'

    # 2. 设置 SSID 和密码（如果提供）
    if ssid:
        if band == '2g':
            router.set_2g_ssid(ssid)
        else:
            router.set_5g_ssid(ssid)

    if password:
        if band == '2g':
            router.set_2g_authentication("WPA2/WPA3-Personal")
            router.set_2g_password(password)
        else:
            router.set_5g_authentication("WPA2/WPA3-Personal")
            router.set_5g_password(password)

    # 3. 【核心】设置无线模式
    if band == '2g':
        router.set_2g_wireless(native_mode)
    else:
        router.set_5g_wireless(native_mode)

    # 4. 【关键】提交所有更改并重启无线服务
    #    这一步确保 nvram commit 和 restart_wireless 正确执行
    router.commit()

    logging.info(
        f"[{band.upper()}] Wireless mode configured: semantic='{mode}' -> native='{native_mode}', SSID='{ssid or 'default'}'")


# --- 替换整个 verify_ap_wireless_mode 函数 ---

def verify_ap_wireless_mode(router, band='2g', expected_ssid='None', expected_mode='auto'):
    """
    验证 AP 是否处于预期无线模式，并确保其真正可用（Beacon 广播中）。
    若首次验证失败，自动重启无线服务并重试一次。
    """

    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            logging.info(f"🔁 Retrying AP verification (attempt {attempt})")

        # === Step 1: 获取接口和 SSID 配置 ===
        if band not in BAND_CONFIG:
            logging.error(f"Unsupported band: {band}")
            return False

        interface = BAND_CONFIG[band]['interface']
        # === 关键改进：从路由器 nvram 实时读取当前 SSID ===
        try:
            host = router.host
            password = str(router.xpath["passwd"])
        except (AttributeError, KeyError) as e:
            logging.error(f"Failed to extract credentials: {e}")
            return False

        # 先建立一次 Telnet 连接，读取 nvram 中的 SSID
        session = None
        try:
            session = TelnetSession(host=host, port=23, timeout=10)
            session.open()
            session.read_until(b"login:", timeout=5)
            session.write(b"admin\n")
            session.read_until(b"Password:", timeout=5)
            session.write(password.encode("ascii") + b"\n")
            prompt = b":/tmp/home/root#"
            session.read_until(prompt, timeout=5)

            # 读取 nvram 中的 SSID（wl0_ssid 或 wl1_ssid）
            nvram_key = "wl1_ssid" if band == '5g' else "wl0_ssid"
            session.write(f"nvram get {nvram_key}\n".encode("ascii"))
            time.sleep(0.2)
            ssid_output = session.read_until(prompt, timeout=3).decode("utf-8", errors="ignore")
            # 提取真实 SSID（去掉命令回显和提示符）
            lines = [line.strip() for line in ssid_output.splitlines() if line.strip()]
            expected_ssid = lines[-1] if lines and not lines[-1].endswith("#") else lines[-2] if len(
                lines) >= 2 else "ASUS_5G"

            logging.debug(f"[{band}] Read SSID from nvram: '{expected_ssid}'")

        except Exception as e:
            logging.warning(f"Failed to read SSID from nvram: {e}. Using default.")
            xpected_ssid = BAND_CONFIG[band]['default_ssid']
        finally:
            if session:
                try:
                    session.close()
                except:
                    pass

        # === Step 2: 建立 Telnet 会话 ===
        session = None
        try:
            session = TelnetSession(host=host, port=23, timeout=10)
            session.open()
            session.read_until(b"login:", timeout=5)
            session.write(b"admin\n")
            session.read_until(b"Password:", timeout=5)
            session.write(password.encode("ascii") + b"\n")
            prompt = b":/tmp/home/root#"
            session.read_until(prompt, timeout=5)

            # === 安全执行 wl 命令的辅助函数 ===
            def safe_wl_command(cmd):
                session.write((cmd + "\n").encode("ascii"))
                time.sleep(0.3)  # 关键：给命令执行留时间
                output = session.read_until(prompt, timeout=3).decode("utf-8", errors="ignore")
                # 移除命令回显和提示符，只保留最后一行有效输出
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                if lines and not lines[-1].endswith("#"):
                    return lines[-1]
                # 如果最后一行是 prompt，取倒数第二行
                if len(lines) >= 2:
                    return lines[-2]
                return ""

            # --- 检查 1: BSS 是否激活（Beacon 广播）---
            bss_status = safe_wl_command(f"wl -i {interface} bss")
            if bss_status != "up":
                logging.warning(f"[{band}] BSS is '{bss_status}' — Beacon NOT broadcasting!")
                checks_passed = False
            else:
                checks_passed = True


            # --- 检查 3: BSS 是否激活（Beacon 广播）---
            bss_status = safe_wl_command(f"wl -i {interface} bss")
            if bss_status != "up":
                logging.warning(f"[{band}] BSS is '{bss_status}' — Beacon NOT broadcasting!")
                checks_passed = False

            # --- 检查 4: 速率模式（复用您原有的 rateset 逻辑）---
            session.write((f"wl -i {interface} rateset\n").encode("ascii"))
            time.sleep(0.5)
            rateset_output_raw = session.read_until(prompt, timeout=5).decode("utf-8", errors="ignore")

            # 清理输出（移除命令行和提示符）
            lines = []
            for line in rateset_output_raw.splitlines():
                stripped = line.strip()
                if stripped == f"wl -i {interface} rateset" or stripped.endswith("#") or not stripped:
                    continue
                lines.append(line)
            rateset_output = "\n".join(lines).strip()

            if not rateset_output:
                raise ValueError("Empty rateset output")

            # 解析速率集（保持您原有的逻辑不变）
            has_1_2_5p5_11 = False
            has_6_to_54 = False
            has_ht = "MCS SET" in rateset_output
            has_vht = "VHT SET" in rateset_output
            has_he = "HE SET" in rateset_output

            rate_line = None
            for line in rateset_output.split('\n'):
                stripped_line = line.strip()
                if stripped_line.startswith('[') and ']' in stripped_line:
                    if 'MCS' not in stripped_line and 'VHT' not in stripped_line and 'HE' not in stripped_line:
                        rate_line = stripped_line
                        break

            if rate_line:
                content = rate_line[1:rate_line.index(']')]
                rate_items = [item.strip() for item in content.split() if item.strip()]
                actual_rates = set()
                for item in rate_items:
                    clean_item = item.replace('(b)', '')
                    try:
                        actual_rates.add(float(clean_item))
                    except ValueError:
                        continue

                if band == '2g':
                    b_rates = {1.0, 2.0, 5.5, 11.0}
                    has_1_2_5p5_11 = not b_rates.isdisjoint(actual_rates)
                    ofdm_rates = {6.0, 9.0, 12.0, 18.0, 24.0, 36.0, 48.0, 54.0}
                    has_6_to_54 = ofdm_rates.issubset(actual_rates)
                else:
                    ofdm_rates = {6.0, 9.0, 12.0, 18.0, 24.0, 36.0, 48.0, 54.0}
                    has_6_to_54 = ofdm_rates.issubset(actual_rates)
                    if has_1_2_5p5_11:
                        logging.warning("Unexpected 1/2/5.5/11 rates on 5GHz!")
                        checks_passed = False
            else:
                raise ValueError("Could not find rate list")

            # 模式匹配（保持您原有的逻辑）
            mode_valid = False
            if band == '2g':
                if expected_mode == 'b-only':
                    mode_valid = has_1_2_5p5_11
                elif expected_mode == 'g-only':
                    mode_valid = has_6_to_54
                elif expected_mode == 'bg-mixed':
                    mode_valid = has_1_2_5p5_11 and has_6_to_54
                elif expected_mode in ['n-only']:
                    mode_valid = has_6_to_54 and has_ht
                elif expected_mode in ['bgn-mixed', 'auto']:
                    mode_valid = has_1_2_5p5_11 and has_6_to_54 and has_ht
                else:
                    mode_valid = False
            else:  # 5g
                if expected_mode == 'a-only':
                    mode_valid = has_6_to_54
                elif expected_mode == 'an-only':
                    mode_valid = has_6_to_54 and has_ht
                elif expected_mode == 'an-ac-mixed':
                    mode_valid = has_6_to_54 and has_ht
                elif expected_mode == 'ax-mixed':
                    mode_valid = has_6_to_54 and has_ht
                elif expected_mode == 'auto':
                    mode_valid = has_6_to_54 and has_ht
                else:
                    logging.warning(f"Unrecognized mode '{expected_mode}' for {band}")
                    mode_valid = False

            # 最终判断：四项检查都通过
            is_valid = checks_passed and mode_valid

            if is_valid:
                logging.info(f"✅ AP verified: {band} {expected_mode}, SSID='{expected_ssid}', BSS=up")
                return True

        except Exception as e:
            logging.warning(f"Verification failed on attempt {attempt}: {e}")
            is_valid = False
        finally:
            if session:
                try:
                    session.close()
                except:
                    pass

        # === 如果失败且还有重试机会，重启 AP ===
        if attempt < max_retries - 1:
            logging.warning(f"AP verification failed. Restarting wireless service...")
            try:
                # router.telnet_write("stop_wireless")
                # time.sleep(5)
                # router.telnet_write("start_wireless")
                router.telnet_write("restart_wireless &", wait_prompt=False)
                time.sleep(12)  # 给 5G AP 充分时间启动（建议 10～15 秒）
            except Exception as e:
                logging.error(f"Failed to restart AP: {e}")
                break  # 重启失败，不再重试

    return False

def configure_ap_channel(router, band='2g', channel=1, ssid=None, password=None):
    """
    配置路由器无线频段的信道（不验证，仅设置）
    Args:
        router: Router 实例 (AsusTelnetNvramControl)
        band (str): '2g' 或 '5g'
        channel (int): 目标信道
        ssid (str, optional): SSID
        password (str, optional): 密码
    """
    # 1. 先设置信道
    if band == '2g':
        router.set_2g_channel(channel)
    else:
        router.set_5g_channel_bandwidth(channel=channel)

    # 2. 复用 configure_ap_wireless_mode 来设置其他参数（SSID, 密码, 模式为 'auto'）
    configure_ap_wireless_mode(
        router,
        band=band,
        mode='auto',  # 使用默认的 'auto' 模式
        ssid=ssid,
        password=password
    )

    # 注意：configure_ap_wireless_mode 内部已经调用了 router.commit()

def configure_ap_bandwidth(router, band='2g', bandwidth='20MHZ'):
    """
    配置路由器无线频段的带宽（不改变模式、SSID、密码，除非显式提供）。
    Args:
        router: AsusTelnetNvramControl 实例 (已连接)
        band (str): '2g' 或 '5g'
        bandwidth (str): 目标带宽，例如 '20MHZ', '40MHZ', '80MHZ'
        ssid (str, optional): 如果提供，则同时更新 SSID
        password (str, optional): 如果提供，则同时更新密码
    """
    _WL0_BANDWIDTH_SEMANTIC_MAP = {
        '20MHZ': '20',
        '40MHZ': '40',
        '20/40MHZ': '20/40',
    }

    # 2. 【核心】设置带宽
    if band == '2g':
        try:
            native_bandwidth = _WL0_BANDWIDTH_SEMANTIC_MAP[bandwidth]
        except KeyError:
            native_bandwidth = bandwidth
            logging.warning(f"[2G] Bandwidth '{bandwidth}' not in semantic map. Using as-is.")

        router.set_2g_bandwidth(native_bandwidth)
    else:  # 5g
        router.set_5g_channel_bandwidth(bandwidth=bandwidth)

    # 3. 提交更改
    router.commit()

    logging.info(f"[{band.upper()}] Bandwidth configured to: {bandwidth} (native: {native_bandwidth if band == '2g' else bandwidth})")

# --- 替换整个 verify_ap_channel_and_beacon 函数 ---

def verify_ap_channel_and_beacon(router, band='2g', expected_channel=1, expected_ssid=None):
    """ 验证 AP 信道和 Beacon 广播是否生效。 """
    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            logging.info(f"🔁 Retrying AP channel verification (attempt {attempt})")

        try:
            host = router.host
            password = str(router.xpath["passwd"])
        except (AttributeError, KeyError) as e:
            logging.error(f"Failed to extract router credentials: {e}")
            return False

        interface = 'eth6' if band == '2g' else 'eth7'
        expected_ssid = expected_ssid or f"AX86U_{band.upper()}"

        try:
            with TelnetVerifier(host=host, password=password) as tv:
                # --- 检查 1: BSS 是否激活 ---
                bss_status = tv.run_command(f"wl -i {interface} bss")
                valid = (bss_status == "up")
                if not valid:
                    logging.warning(f"[{band}] BSS is '{bss_status}' — Beacon NOT broadcasting!")

                # --- 检查 2: SSID 是否匹配 ---
                ssid_raw = tv.run_command(f"wl -i {interface} ssid")
                current_ssid = _extract_ssid_from_wl_output(ssid_raw) # 复用你已有的 extract_ssid 函数
                if current_ssid != expected_ssid:
                    logging.warning(f"[{band}] SSID mismatch: expected '{expected_ssid}', got '{current_ssid}'")
                    valid = False

                # --- 检查 3: 信道是否正确 ---
                chanspec_out = tv.run_command(f"wl -i {interface} chanspec")
                match = re.search(r'^\s*(\d+)', chanspec_out.strip())
                actual_channel = match.group(1) if match else chanspec_out.split("/")[0].strip()
                if str(expected_channel) != actual_channel:
                    logging.warning(f"[{band}] Channel mismatch: expected {expected_channel}, got {actual_channel}")
                    valid = False

                if valid:
                    logging.info(f"✅ [{band}] Verified: channel={expected_channel}, SSID='{expected_ssid}', BSS=up")
                    return True

        except Exception as e:
            logging.warning(f"Verification failed on attempt {attempt}: {e}")

        # === 重启无线服务 ===
        if attempt < max_retries - 1:
            logging.warning(f"[{band}] Verification failed. Restarting wireless service...")
            try:
                router.telnet_write("restart_wireless &", wait_prompt=False)
                time.sleep(12)
            except Exception as e:
                logging.error(f"Failed to restart wireless: {e}")
                break

    return False

def restore_ap_default_wireless(router, band='2g', original_ssid=None, original_password=None):
    """
    恢复 AP 到默认配置（auto 模式）
    """
    if band not in BAND_CONFIG:
        return

    config = BAND_CONFIG[band]
    ssid = original_ssid or config['default_ssid']
    password = original_password or '88888888'

    if band == '2g':
        router.set_2g_channel("auto")
        configure_ap_bandwidth(router, band='2g', bandwidth='20/40MHZ')
    else:
        router.set_5g_channel_bandwidth(channel="auto", bandwidth="20/40/80MHZ")

    # 2. 复用 configure_ap_wireless_mode 来设置其他参数（SSID, 密码, 模式为 'auto'）
    configure_ap_wireless_mode(
        router,
        band=band,
        mode='auto',  # 使用默认的 'auto' 模式
        ssid=ssid,
        password=password
    )


def _detect_wep_key_format(password: str):
    """
    Automatically detect WEP key format (ASCII or Hex) and type (64/128) based on length.
    Returns: (key_type: str, wep_format: str)
        - key_type: '64-bit' or '128-bit'
        - wep_format: 'ascii' or 'hex'
    Raises ValueError if length is invalid.
    """
    pw_len = len(password)

    # Map valid lengths to (key_type, format)
    length_map = {
        5: ('64-bit', 'ascii'),
        13: ('128-bit', 'ascii'),
        10: ('64-bit', 'hex'),
        26: ('128-bit', 'hex'),
    }

    if pw_len not in length_map:
        raise ValueError(
            f"Invalid WEP key length: {pw_len}. "
            "Valid lengths: 5 (ASCII WEP-64), 13 (ASCII WEP-128), "
            "10 (Hex WEP-64), or 26 (Hex WEP-128)."
        )

    key_type, wep_format = length_map[pw_len]

    # Optional: Add a sanity check for hex keys
    if wep_format == 'hex':
        if not all(c in '0123456789ABCDEFabcdef' for c in password):
            raise ValueError("Provided key appears to be hex (length=10/26) but contains non-hex characters.")

    return key_type, wep_format

def configure_ap_security_universal(router, band: str, security_mode: str, password: str, encryption: str = "aes", pmf: int | None = None) -> None:
    """
    A universal function to configure AP security mode, mimicking the successful pattern from hidden_ssid tests.

    This function does NOT modify AsusTelnetNvramControl and relies on its existing public methods.

    Args:
        router: An instance of AsusTelnetNvramControl.
        band: '2g' or '5g'.
        security_mode: The semantic security mode name, e.g., 'Open System', 'Shared Key', 'WPA2-Personal'.
        password: The network key. Required for all modes except 'Open System'. For 'Shared Key', it must be a 10-char hex WEP key.
    """
    import logging
    from typing import Optional

    # --- Input Validation ---
    if band not in ('2g', '5g'):
        raise ValueError(f"Invalid band '{band}'. Expected '2g' or '5g'.")

    # Define the list of supported modes based on what AsusTelnetNvramControl's MODE_PARAM keys are.
    # This should match the keys used in hidden_ssid.py.
    SUPPORTED_MODES = {
        'Open System',
        'Shared Key',
        'WPA2-Personal',
        'WPA3-Personal',
        'WPA/WPA2-Personal',
        'WPA2/WPA3-Personal'
    }
    _ENCRYPTION_MAP = {
        "aes": "aes",  # 对应 nvram 的 'aes'
        "tkip+aes": "tkip+aes"  # 对应 nvram 的 'tkip+aes'
    }

    if security_mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported security mode: '{security_mode}'. Supported: {SUPPORTED_MODES}")

    _ENCRYPTION_MAP = {"aes": "aes", "tkip+aes": "tkip+aes"}
    if encryption not in _ENCRYPTION_MAP:
        raise ValueError(f"Unsupported encryption: '{encryption}'. Use 'aes' or 'tkip+aes'.")
    crypto_value = _ENCRYPTION_MAP[encryption]

    # Validate PMF value if provided
    if pmf is not None and pmf not in (0, 1, 2):
        raise ValueError("pmf must be 0 (disabled), 1 (optional), 2 (required), or None (skip).")

    logging.info(f"[{band.upper()}] Configuring: mode='{security_mode}', "
                 f"encryption='{encryption}', pmf={'set to ' + str(pmf) if pmf is not None else 'unchanged'}")

    wl_prefix = "wl0_" if band == "2g" else "wl1_"

    # --- Special Case 1: WEP (Shared Key) ---
    if security_mode == 'Shared Key':
        if not password:
            raise ValueError("For 'Shared Key' mode, a 10-character hexadecimal WEP key is required as 'password'.")

        # Validate WEP key length and determine key type
        key_type, wep_format = _detect_wep_key_format(password)
        bands_to_config = [band]

        router.set_wep_mode_dual_band(key_type=key_type, wep_key=password, bands=bands_to_config)
        logging.info(f"[{band.upper()}] WEP-64 configured successfully.")
        return

    # --- Special Case 2: Open System ---
    if security_mode == 'Open System':
        # Call the authentication method with 'Open System'
        if band == '2g':
            router.set_2g_authentication('Open System')
        else:
            router.set_5g_authentication('Open System')
        logging.info(f"[{band.upper()}] Open System configured successfully.")
        return

    # --- General Case: WPA/WPA2/WPA3 Modes ---
    # These modes require both an authentication type and a password.
    if not password:
        raise ValueError(f"Password is required for security mode '{security_mode}'.")

    # Step 1: Set the authentication mode using the semantic name.
    if band == '2g':
        router.set_2g_authentication(security_mode)
        # Step 2: Set the password.
        router.set_2g_password(password)
    else:  # band == '5g'
        router.set_5g_authentication(security_mode)
        router.set_5g_password(password)

    # Set encryption
    router.telnet_write(f"nvram set {wl_prefix}crypto={crypto_value}")

    # ✅ Only set PMF if explicitly requested
    if pmf is not None:
        router.telnet_write(f"nvram set {wl_prefix}pmf={pmf}")
        logging.debug(f"[{band.upper()}] PMF explicitly set to {pmf}.")

    # 3. 提交更改
    router.commit()

    logging.info(f"[{band.upper()}] Security mode '{security_mode}' with password and encryption='{encryption}' configured.")


# def configure_and_verify_ap_country_code(router, country_code="US"):
#     """
#     配置路由器的国家码 (Country Code)，并验证设置结果。
#     如果设置成功，返回当前 AP 在 2.4G 和 5G 频段支持的信道列表。
#
#     Args:
#         router: AsusTelnetNvramControl 实例（已连接）。
#         country_code (str): 目标国家码，例如 'US', 'CN', 'JP'。
#
#     Returns:
#         dict: 包含验证结果和支持信道的字典。
#               {
#                   'country_code_set': bool, # 国家码是否成功设置
#                   'verified_country_code': str, # 验证后读取的实际国家码
#                   '2g_channels': list[int], # 2.4G 支持的信道列表
#                   '5g_channels': list[int]  # 5G 支持的信道列表
#               }
#     """
#
#     result = {
#         'country_code_set': False,
#         'verified_country_code': "",
#         '2g_channels': [],
#         '5g_channels': []
#     }
#
#     try:
#         host = router.host
#         password = str(router.xpath["passwd"])
#     except (AttributeError, KeyError) as e:
#         logging.error(f"Failed to extract router credentials: {e}")
#         return result
#
#     # === Step 1: 设置国家码 ===
#     try:
#         # 使用 router 对象的 API 设置国家码
#         # router.telnet_write(f"nvram set wl_country_code={country_code}")
#         # if country_code == "US":
#         #     router.telnet_write(f"nvram set wl0_country_code={country_code}")
#         #     router.telnet_write(f"nvram set wl1_country_code={country_code}")
#         # router.commit() # nvram commit & restart_wireless
#         router.change_country_v2(country_code)
#         logging.info(f"Country code set to '{country_code}' via UI setting")
#         time.sleep(180) # 等待无线服务完全启动
#         router.close_browser()
#     except Exception as e:
#         logging.error(f"Failed to set country code '{country_code}': {e}")
#         return result
#
#     session = None
#
#     try:
#         with TelnetVerifier(host=host, password=password) as tv:
#             # Verify country code
#             # verified_cc = tv.run_command(f"nvram get wl_country_code").strip()
#             # verified_cc2 = tv.run_command(f"wl -i eth6 country").strip()
#             raw_cc = tv.run_command(f"nvram get wl_country_code")
#             verified_cc = re.sub(r'\s+', '', raw_cc)
#             raw_cc2 = tv.run_command(f"wl -i eth6 country")
#
#             cc2_match = re.search(r'^([A-Z]{2})', raw_cc2)
#             if cc2_match:
#                 verified_cc2 = cc2_match.group(1)
#             else:
#                 verified_cc2 = re.sub(r'\s+', '', raw_cc2.split()[0] if raw_cc2.split() else "")
#
#             logging.info(f"Country code set to  {verified_cc2}")
#             expected_driver_code = RouterTools.UI_TO_DRIVER_COUNTRY_MAP.get(country_code, country_code)
#             if country_code == 'EU':
#                 if verified_cc2 not in ('E0', 'DE'):
#                     error_msg = f"EU region expected 'E0' or 'DE', got '{verified_cc2}'"
#                     logging.error(error_msg)
#                     raise RuntimeError(error_msg)
#             elif verified_cc2 != expected_driver_code:
#                 error_msg = f"Driver country code mismatch: expected '{expected_driver_code}', got '{verified_cc2}'"
#                 logging.error(error_msg)
#                 raise RuntimeError(error_msg)
#
#             if verified_cc != country_code:
#                 logging.warning(f"NVRAM country code ('{verified_cc}') differs from driver ('{verified_cc2}')")
#             result['verified_country_code'] = verified_cc2
#
#             # Wait some minutes to makesure channel list takes affect, Get channel lists
#             time.sleep(200)
#             chlist_2g_str = tv.run_command("nvram get wl0_chlist").strip()
#             chlist_5g_str = tv.run_command("nvram get wl1_chlist").strip()
#
#             # Convert space-separated string to list of ints
#             result['2g_channels'] = [int(ch) for ch in chlist_2g_str.split() if ch.isdigit()]
#             result['5g_channels'] = [int(ch) for ch in chlist_5g_str.split() if ch.isdigit()]
#
#             result['country_code_set'] = True
#             logging.info(f"✅ Country code verified as '{verified_cc2}'. "
#                          f"2.4G Channels: {result['2g_channels']}, "
#                          f"5G Channels: {result['5g_channels']}")
#
#     except Exception as e:
#         logging.error(f"Verification failed: {e}", exc_info=True)
#         raise
#
#     return result
def configure_and_verify_ap_country_code(router, country_code="US", dut_country_code=None):
    """
    Unified interface for country code configuration and verification.

    This function delegates to the router-specific implementation.
    All router control classes must implement:
        configure_and_verify_country_code(country_code: str) -> dict
    """
    # 直接调用 router 对象的方法（多态）
    lookup_country = dut_country_code if dut_country_code is not None else country_code
    result = router.configure_and_verify_country_code(
        country_code=country_code,
        dut_country_code=dut_country_code  # ← 必须传！
    )
    time.sleep(60)
    return result

def _extract_ssid_from_wl_output(output: str) -> str:
    """Extract SSID from 'wl -i <iface> ssid' command output."""
    match = re.search(r'Current SSID:\s*"([^"]*)"', output)
    if match:
        return match.group(1)
    # Fallback: clean up the raw output
    cleaned = output.strip()
    if cleaned.startswith("Current SSID:"):
        cleaned = cleaned[len("Current SSID:"):].strip()
    return cleaned.strip('" \n')
