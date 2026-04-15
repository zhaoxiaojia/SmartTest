import time,re
import logging
import traceback
from testing.tool.dut_tool.transports.telnet_tool import TelnetSession


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

# === 棰戞閰嶇疆涓庢ā寮忔槧灏?===
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
            'auto':        ('auto',   1, 0),  # 榛樿 = bgn-mixed
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
            'auto':          ('ac-mixed',   2, 0),  # 5G auto 閫氬父涓?an/ac
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
        # 鏈潵鍙互鍦ㄨ繖閲屾坊鍔犳洿澶氾紝渚嬪:
        # 'WPA-Enterprise': 'wpa',
        # 'OWE': 'owe',
    }
VALID_INTERNAL_AUTH_VALUES = set(SUPPORTED_AUTHENTICATION_METHODS.values())

def configure_ap_wireless_mode(router, band='2g', mode='auto', ssid=None, password=None):
    """
    閰嶇疆璺敱鍣ㄦ棤绾挎ā寮忥紙鏀寔 2.4G / 5G锛夛紝浣跨敤 AsusTelnetNvramControl 鐨?API銆?

    :param router: AsusTelnetNvramControl 瀹炰緥锛堝凡杩炴帴锛?
    :param band: '2g' or '5g'
    :param mode: 妯″紡鍚嶏紝濡?'bgn-mixed', 'an-ac-mixed' 绛夛紙鏉ヨ嚜 BAND_CONFIG锛?
    :param ssid: 鑷畾涔?SSID
    :param password: 鑷畾涔夊瘑鐮?
    """
    if band not in _ASUS_ROUTER_MODE_MAP:
        raise ValueError(f"Unsupported band: {band}. Use '2g' or '5g'.")

    # 1. 妯″紡鏄犲皠
    mode_map = _ASUS_ROUTER_MODE_MAP[band]
    if mode not in mode_map:
        supported_modes = ', '.join(mode_map.keys())
        raise ValueError(f"Mode '{mode}' not supported for {band}. Supported: {supported_modes}")

    native_mode = mode_map[mode]  # e.g., 'bgn-mixed' -> 'auto'

    # 2. 璁剧疆 SSID 鍜屽瘑鐮侊紙濡傛灉鎻愪緵锛?
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

    # 3. 銆愭牳蹇冦€戣缃棤绾挎ā寮?
    if band == '2g':
        router.set_2g_wireless(native_mode)
    else:
        router.set_5g_wireless(native_mode)

    # 4. 銆愬叧閿€戞彁浜ゆ墍鏈夋洿鏀瑰苟閲嶅惎鏃犵嚎鏈嶅姟
    #    杩欎竴姝ョ‘淇?nvram commit 鍜?restart_wireless 姝ｇ‘鎵ц
    router.commit()

    logging.info(
        f"[{band.upper()}] Wireless mode configured: semantic='{mode}' -> native='{native_mode}', SSID='{ssid or 'default'}'")


# --- 鏇挎崲鏁翠釜 verify_ap_wireless_mode 鍑芥暟 ---

def verify_ap_wireless_mode(router, band='2g', expected_ssid='None', expected_mode='auto'):
    """
    楠岃瘉 AP 鏄惁澶勪簬棰勬湡鏃犵嚎妯″紡锛屽苟纭繚鍏剁湡姝ｅ彲鐢紙Beacon 骞挎挱涓級銆?
    鑻ラ娆￠獙璇佸け璐ワ紝鑷姩閲嶅惎鏃犵嚎鏈嶅姟骞堕噸璇曚竴娆°€?
    """

    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            logging.info(f"馃攣 Retrying AP verification (attempt {attempt})")

        # === Step 1: 鑾峰彇鎺ュ彛鍜?SSID 閰嶇疆 ===
        if band not in BAND_CONFIG:
            logging.error(f"Unsupported band: {band}")
            return False

        interface = BAND_CONFIG[band]['interface']
        # === 鍏抽敭鏀硅繘锛氫粠璺敱鍣?nvram 瀹炴椂璇诲彇褰撳墠 SSID ===
        try:
            host = router.host
            password = str(router.xpath["passwd"])
        except (AttributeError, KeyError) as e:
            logging.error(f"Failed to extract credentials: {e}")
            return False

        # 鍏堝缓绔嬩竴娆?Telnet 杩炴帴锛岃鍙?nvram 涓殑 SSID
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

            # 璇诲彇 nvram 涓殑 SSID锛坵l0_ssid 鎴?wl1_ssid锛?
            nvram_key = "wl1_ssid" if band == '5g' else "wl0_ssid"
            session.write(f"nvram get {nvram_key}\n".encode("ascii"))
            time.sleep(0.2)
            ssid_output = session.read_until(prompt, timeout=3).decode("utf-8", errors="ignore")
            # 鎻愬彇鐪熷疄 SSID锛堝幓鎺夊懡浠ゅ洖鏄惧拰鎻愮ず绗︼級
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

        # === Step 2: 寤虹珛 Telnet 浼氳瘽 ===
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

            # === 瀹夊叏鎵ц wl 鍛戒护鐨勮緟鍔╁嚱鏁?===
            def safe_wl_command(cmd):
                session.write((cmd + "\n").encode("ascii"))
                time.sleep(0.3)  # 鍏抽敭锛氱粰鍛戒护鎵ц鐣欐椂闂?
                output = session.read_until(prompt, timeout=3).decode("utf-8", errors="ignore")
                # 绉婚櫎鍛戒护鍥炴樉鍜屾彁绀虹锛屽彧淇濈暀鏈€鍚庝竴琛屾湁鏁堣緭鍑?
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                if lines and not lines[-1].endswith("#"):
                    return lines[-1]
                # 濡傛灉鏈€鍚庝竴琛屾槸 prompt锛屽彇鍊掓暟绗簩琛?
                if len(lines) >= 2:
                    return lines[-2]
                return ""

            # --- 妫€鏌?1: BSS 鏄惁婵€娲伙紙Beacon 骞挎挱锛?--
            bss_status = safe_wl_command(f"wl -i {interface} bss")
            if bss_status != "up":
                logging.warning(f"[{band}] BSS is '{bss_status}' 鈥?Beacon NOT broadcasting!")
                checks_passed = False
            else:
                checks_passed = True


            # --- 妫€鏌?3: BSS 鏄惁婵€娲伙紙Beacon 骞挎挱锛?--
            bss_status = safe_wl_command(f"wl -i {interface} bss")
            if bss_status != "up":
                logging.warning(f"[{band}] BSS is '{bss_status}' 鈥?Beacon NOT broadcasting!")
                checks_passed = False

            # --- 妫€鏌?4: 閫熺巼妯″紡锛堝鐢ㄦ偍鍘熸湁鐨?rateset 閫昏緫锛?--
            session.write((f"wl -i {interface} rateset\n").encode("ascii"))
            time.sleep(0.5)
            rateset_output_raw = session.read_until(prompt, timeout=5).decode("utf-8", errors="ignore")

            # 娓呯悊杈撳嚭锛堢Щ闄ゅ懡浠よ鍜屾彁绀虹锛?
            lines = []
            for line in rateset_output_raw.splitlines():
                stripped = line.strip()
                if stripped == f"wl -i {interface} rateset" or stripped.endswith("#") or not stripped:
                    continue
                lines.append(line)
            rateset_output = "\n".join(lines).strip()

            if not rateset_output:
                raise ValueError("Empty rateset output")

            # 瑙ｆ瀽閫熺巼闆嗭紙淇濇寔鎮ㄥ師鏈夌殑閫昏緫涓嶅彉锛?
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

            # 妯″紡鍖归厤锛堜繚鎸佹偍鍘熸湁鐨勯€昏緫锛?
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

            # 鏈€缁堝垽鏂細鍥涢」妫€鏌ラ兘閫氳繃
            is_valid = checks_passed and mode_valid

            if is_valid:
                logging.info(f"鉁?AP verified: {band} {expected_mode}, SSID='{expected_ssid}', BSS=up")
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

        # === 濡傛灉澶辫触涓旇繕鏈夐噸璇曟満浼氾紝閲嶅惎 AP ===
        if attempt < max_retries - 1:
            logging.warning(f"AP verification failed. Restarting wireless service...")
            try:
                # router.telnet_write("stop_wireless")
                # time.sleep(5)
                # router.telnet_write("start_wireless")
                router.telnet_write("restart_wireless &", wait_prompt=False)
                time.sleep(12)  # 缁?5G AP 鍏呭垎鏃堕棿鍚姩锛堝缓璁?10锝?5 绉掞級
            except Exception as e:
                logging.error(f"Failed to restart AP: {e}")
                break  # 閲嶅惎澶辫触锛屼笉鍐嶉噸璇?

    return False

def configure_ap_channel(router, band='2g', channel=1, ssid=None, password=None):
    """
    閰嶇疆璺敱鍣ㄦ棤绾块娈电殑淇￠亾锛堜笉楠岃瘉锛屼粎璁剧疆锛?
    Args:
        router: Router 瀹炰緥 (AsusTelnetNvramControl)
        band (str): '2g' 鎴?'5g'
        channel (int): 鐩爣淇￠亾
        ssid (str, optional): SSID
        password (str, optional): 瀵嗙爜
    """
    # 1. 鍏堣缃俊閬?
    if band == '2g':
        router.set_2g_channel(channel)
    else:
        router.set_5g_channel_bandwidth(channel=channel)

    # 2. 澶嶇敤 configure_ap_wireless_mode 鏉ヨ缃叾浠栧弬鏁帮紙SSID, 瀵嗙爜, 妯″紡涓?'auto'锛?
    configure_ap_wireless_mode(
        router,
        band=band,
        mode='auto',  # 浣跨敤榛樿鐨?'auto' 妯″紡
        ssid=ssid,
        password=password
    )

    # 娉ㄦ剰锛歝onfigure_ap_wireless_mode 鍐呴儴宸茬粡璋冪敤浜?router.commit()

def configure_ap_bandwidth(router, band='2g', bandwidth='20MHZ'):
    """
    閰嶇疆璺敱鍣ㄦ棤绾块娈电殑甯﹀锛堜笉鏀瑰彉妯″紡銆丼SID銆佸瘑鐮侊紝闄ら潪鏄惧紡鎻愪緵锛夈€?
    Args:
        router: AsusTelnetNvramControl 瀹炰緥 (宸茶繛鎺?
        band (str): '2g' 鎴?'5g'
        bandwidth (str): 鐩爣甯﹀锛屼緥濡?'20MHZ', '40MHZ', '80MHZ'
        ssid (str, optional): 濡傛灉鎻愪緵锛屽垯鍚屾椂鏇存柊 SSID
        password (str, optional): 濡傛灉鎻愪緵锛屽垯鍚屾椂鏇存柊瀵嗙爜
    """
    _WL0_BANDWIDTH_SEMANTIC_MAP = {
        '20MHZ': '20',
        '40MHZ': '40',
        '20/40MHZ': '20/40',
    }

    # 2. 銆愭牳蹇冦€戣缃甫瀹?
    if band == '2g':
        try:
            native_bandwidth = _WL0_BANDWIDTH_SEMANTIC_MAP[bandwidth]
        except KeyError:
            native_bandwidth = bandwidth
            logging.warning(f"[2G] Bandwidth '{bandwidth}' not in semantic map. Using as-is.")

        router.set_2g_bandwidth(native_bandwidth)
    else:  # 5g
        router.set_5g_channel_bandwidth(bandwidth=bandwidth)

    # 3. 鎻愪氦鏇存敼
    router.commit()

    logging.info(f"[{band.upper()}] Bandwidth configured to: {bandwidth} (native: {native_bandwidth if band == '2g' else bandwidth})")

# --- 鏇挎崲鏁翠釜 verify_ap_channel_and_beacon 鍑芥暟 ---

def verify_ap_channel_and_beacon(router, band='2g', expected_channel=1, expected_ssid=None):
    """ 楠岃瘉 AP 淇￠亾鍜?Beacon 骞挎挱鏄惁鐢熸晥銆?"""
    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            logging.info(f"馃攣 Retrying AP channel verification (attempt {attempt})")

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
                # --- 妫€鏌?1: BSS 鏄惁婵€娲?---
                bss_status = tv.run_command(f"wl -i {interface} bss")
                valid = (bss_status == "up")
                if not valid:
                    logging.warning(f"[{band}] BSS is '{bss_status}' 鈥?Beacon NOT broadcasting!")

                # --- 妫€鏌?2: SSID 鏄惁鍖归厤 ---
                ssid_raw = tv.run_command(f"wl -i {interface} ssid")
                current_ssid = _extract_ssid_from_wl_output(ssid_raw) # 澶嶇敤浣犲凡鏈夌殑 extract_ssid 鍑芥暟
                if current_ssid != expected_ssid:
                    logging.warning(f"[{band}] SSID mismatch: expected '{expected_ssid}', got '{current_ssid}'")
                    valid = False

                # --- 妫€鏌?3: 淇￠亾鏄惁姝ｇ‘ ---
                chanspec_out = tv.run_command(f"wl -i {interface} chanspec")
                match = re.search(r'^\s*(\d+)', chanspec_out.strip())
                actual_channel = match.group(1) if match else chanspec_out.split("/")[0].strip()
                if str(expected_channel) != actual_channel:
                    logging.warning(f"[{band}] Channel mismatch: expected {expected_channel}, got {actual_channel}")
                    valid = False

                if valid:
                    logging.info(f"鉁?[{band}] Verified: channel={expected_channel}, SSID='{expected_ssid}', BSS=up")
                    return True

        except Exception as e:
            logging.warning(f"Verification failed on attempt {attempt}: {e}")

        # === 閲嶅惎鏃犵嚎鏈嶅姟 ===
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
    鎭㈠ AP 鍒伴粯璁ら厤缃紙auto 妯″紡锛?
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

    # 2. 澶嶇敤 configure_ap_wireless_mode 鏉ヨ缃叾浠栧弬鏁帮紙SSID, 瀵嗙爜, 妯″紡涓?'auto'锛?
    configure_ap_wireless_mode(
        router,
        band=band,
        mode='auto',  # 浣跨敤榛樿鐨?'auto' 妯″紡
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
        "aes": "aes",  # 瀵瑰簲 nvram 鐨?'aes'
        "tkip+aes": "tkip+aes"  # 瀵瑰簲 nvram 鐨?'tkip+aes'
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

    # 鉁?Only set PMF if explicitly requested
    if pmf is not None:
        router.telnet_write(f"nvram set {wl_prefix}pmf={pmf}")
        logging.debug(f"[{band.upper()}] PMF explicitly set to {pmf}.")

    # 3. 鎻愪氦鏇存敼
    router.commit()

    logging.info(f"[{band.upper()}] Security mode '{security_mode}' with password and encryption='{encryption}' configured.")


# def configure_and_verify_ap_country_code(router, country_code="US"):
#     """
#     閰嶇疆璺敱鍣ㄧ殑鍥藉鐮?(Country Code)锛屽苟楠岃瘉璁剧疆缁撴灉銆?
#     濡傛灉璁剧疆鎴愬姛锛岃繑鍥炲綋鍓?AP 鍦?2.4G 鍜?5G 棰戞鏀寔鐨勪俊閬撳垪琛ㄣ€?
#
#     Args:
#         router: AsusTelnetNvramControl 瀹炰緥锛堝凡杩炴帴锛夈€?
#         country_code (str): 鐩爣鍥藉鐮侊紝渚嬪 'US', 'CN', 'JP'銆?
#
#     Returns:
#         dict: 鍖呭惈楠岃瘉缁撴灉鍜屾敮鎸佷俊閬撶殑瀛楀吀銆?
#               {
#                   'country_code_set': bool, # 鍥藉鐮佹槸鍚︽垚鍔熻缃?
#                   'verified_country_code': str, # 楠岃瘉鍚庤鍙栫殑瀹為檯鍥藉鐮?
#                   '2g_channels': list[int], # 2.4G 鏀寔鐨勪俊閬撳垪琛?
#                   '5g_channels': list[int]  # 5G 鏀寔鐨勪俊閬撳垪琛?
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
#     # === Step 1: 璁剧疆鍥藉鐮?===
#     try:
#         # 浣跨敤 router 瀵硅薄鐨?API 璁剧疆鍥藉鐮?
#         # router.telnet_write(f"nvram set wl_country_code={country_code}")
#         # if country_code == "US":
#         #     router.telnet_write(f"nvram set wl0_country_code={country_code}")
#         #     router.telnet_write(f"nvram set wl1_country_code={country_code}")
#         # router.commit() # nvram commit & restart_wireless
#         router.change_country_v2(country_code)
#         logging.info(f"Country code set to '{country_code}' via UI setting")
#         time.sleep(180) # 绛夊緟鏃犵嚎鏈嶅姟瀹屽叏鍚姩
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
#             logging.info(f"鉁?Country code verified as '{verified_cc2}'. "
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
    # 鐩存帴璋冪敤 router 瀵硅薄鐨勬柟娉曪紙澶氭€侊級
    lookup_country = dut_country_code if dut_country_code is not None else country_code
    result = router.configure_and_verify_country_code(
        country_code=country_code,
        dut_country_code=dut_country_code  # 鈫?蹇呴』浼狅紒
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

