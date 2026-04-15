"""openwrt uci wl controlThis module is part of the arrisRouter package."""
from __future__ import annotations
import logging
import re, time
from typing import Optional, Union, Dict, Any, List
from .RouterControl import ConfigError
from testing.tool.dut_tool.transports.ssh_tool import ssh_tool


class OpenWrtWlControl:
    """
    OpenWrt SSH wireless control via UCI commands.
    This class provides methods to configure wireless settings on OpenWrt-based routers using UCI (Unified Configuration Interface) over SSH.
    """
    REGION_CHANNEL_MAP = {
        "US": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "CN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]
        },
        "EU": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "JP": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "IN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "KR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "AU": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "GB": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "RU": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },

        "CA": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 132, 136, 140, 144, 149, 153, 157, 161, 165]
        },
        "AE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "AR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "AT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "BR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "DE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "ES": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "FR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "HK": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "MY": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "MX": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "PH": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # TH 娉板浗
        "TH": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # ID 鍗板害灏艰タ浜?
        "ID": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]},
        # VN 瓒婂崡
        "VN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # SG 鏂板姞鍧?
        "SG": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # KZ 鍝堣惃鍏嬫柉鍧?
        "KZ": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # TR 鍦熻€冲叾
        "TR": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # OM 闃挎浖
        "OM": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # SA 娌欑壒闃挎媺浼?
        "SA": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
               },
        # EG 鍩冨強
        "EG": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64]},
        # NG 灏兼棩鍒╀簹
        "NG": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [52, 56, 60, 64, 149, 153, 157, 161]},
        # ZA 鍗楅潪
        "ZA": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # UY 涔屾媺鍦?
        "UY": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]},
        # PE 绉橀瞾
        "PE": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # CO 鍝ヤ鸡姣斾簹
        "CO": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # CR 鍝ユ柉杈鹃粠鍔?
        "CR": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},

        # NL 鑽峰叞
        "NL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # IT 鎰忓ぇ鍒?
        "IT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # PL 娉㈠叞
        "PL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RO 缃楅┈灏间簹
        "RO": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RO 钁¤悇鐗?
        "PT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # SE 鐟炲吀
        "SE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RS 濉炲皵缁翠簹
        "RS": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        # UA 涔屽厠鍏?
        "UA": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        #CL:鏅哄埄
        "CL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]
        },
        # EC 鍘勭摐澶氬皵
        "EC": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
    }

    # OpenWrt UCI identifiers
    RADIO_2G = None
    RADIO_5G = None
    BAND_LIST = ["2.4G", "5G"]
    CHANNEL_2 = ['auto', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14']
    BANDWIDTH_2 = ['20/40', '20', '40', ]
    CHANNEL_5 = []
    BANDWIDTH_5 = []
    _initialized = False

    IFACE_2G_INDEX = 0
    IFACE_5G_INDEX = 1
    SSH_PWD = "amlogic@123"

    def __init__(self, config_or_address: Union[Dict[str, Any], str]) -> None:
        self._ssh: Optional[ssh_tool] = None

        if isinstance(config_or_address, str):
            self.router_ip = config_or_address
            self.username = "root"
        elif isinstance(config_or_address, dict):
            config = config_or_address
            self.router_ip = config.get("address")
            if not self.router_ip:
                raise ValueError("Missing required 'address' in router config.")
            self.username = config.get("username", "root")
        else:
            raise TypeError("config_or_address must be a str or dict")
        self.password = self.SSH_PWD

        # 鍏抽敭淇敼锛氱Щ闄ょ珛鍗崇殑璁惧鍙戠幇锛屼絾淇濈暀鍘熸湁璁捐鍘熷垯
        # 涓嶅啀鍦╛_init__涓珛鍗宠Е鍙慡SH杩炴帴
        logging.info(f"OpenWrtWlControl initialized for router at {self.router_ip}")

    @property
    def ssh(self) -> ssh_tool:
        """Lazy-initialize and return the SSH tool instance."""
        if self._ssh is None:
            self._ssh = ssh_tool(
                host=self.router_ip,
                username=self.username,
                password=self.password
            )
        return self._ssh

    def quit(self) -> None:
        """Close the SSH session."""
        if self._ssh is not None:
            logging.info("SSH session for %s closed.", self.router_ip)
            self._ssh = None

    def _execute_command(self, cmd: str, timeout: int = 30) -> str:
        """Execute a command using the cached SSH session."""
        logging.info("Executing via SSH on %s: %r", self.router_ip, cmd)
        try:
            output = self.ssh.checkoutput(cmd)
            return output.strip()
        except Exception as exc:
            logging.error("SSH command %r failed on %s: %s", cmd, self.router_ip, exc, exc_info=True)
            raise RuntimeError(f"SSH command failed on {self.router_ip}: {exc}") from exc

    # --- 鏂板锛氫繚鎸佸師鏈夎璁″師鍒欑殑杈呭姪鏂规硶 ---

    def discover_devices(self) -> List[str]:
        """
        鏄惧紡鍙戠幇WiFi璁惧锛堝簲璇ュ湪娴嬭瘯寮€濮嬫椂璋冪敤涓€娆★級
        淇濇寔鍘熸湁璁捐鍘熷垯锛氫竴娆″彂鐜帮紝鍏ㄥ眬浣跨敤

        Returns:
            璁惧鍚嶇О鍒楄〃
        """
        # 濡傛灉宸茬粡鍏ㄥ眬鍒濆鍖栵紝鐩存帴杩斿洖
        if OpenWrtWlControl._initialized:
            if OpenWrtWlControl.RADIO_2G and OpenWrtWlControl.RADIO_5G:
                return [OpenWrtWlControl.RADIO_2G, OpenWrtWlControl.RADIO_5G]

        try:
            # 鍙戠幇璁惧
            devices = self._discover_wifi_devices()

            if len(devices) >= 2:
                # 璁剧疆鍏ㄥ眬绫诲彉閲?
                OpenWrtWlControl.RADIO_2G = devices[0]
                OpenWrtWlControl.RADIO_5G = devices[1]
                OpenWrtWlControl._initialized = True
                logging.info(f"Successfully discovered and initialized global radios: {devices}")
                return devices
            else:
                error_msg = f"Failed to discover at least 2 WiFi radios. Found: {devices}"
                logging.error(error_msg)
                raise RuntimeError(error_msg)

        except Exception as e:
            logging.error(f"Failed to discover WiFi devices: {e}")
            return []

    def _ensure_globals_initialized(self):
        """纭繚鍏ㄥ眬璁惧淇℃伅宸插垵濮嬪寲锛堝湪闇€瑕佽澶囦俊鎭殑鏂规硶涓皟鐢級"""
        if not OpenWrtWlControl._initialized:
            # 鑷姩灏濊瘯鍒濆鍖?
            self.discover_devices()

        if OpenWrtWlControl.RADIO_2G is None or OpenWrtWlControl.RADIO_5G is None:
            raise RuntimeError("WiFi devices not discovered. Call discover_devices() first.")

    # --- 鏂板鏂规硶锛氬吋瀹瑰崕纭曡矾鐢卞櫒API ---
    def set_2g_authentication(self, auth_mode: str) -> None:
        """
        Set 2.4G authentication mode.
        For OpenWrt, this maps to setting the 'encryption' field.
        Common mappings:
        - "WPA2-Personal" -> "psk2"
        - "WPA2/WPA3-Personal" -> "sae-mixed"
        """
        self._ensure_globals_initialized()
        auth_map = {
            "WPA2-Personal": "psk2",
            "WPA2/WPA3-Personal": "sae-mixed",
            "WPA3-Personal": "sae"
        }
        encryption = auth_map.get(auth_mode, "psk2")  # Default to WPA2
        self._execute_command(f"uci set wireless.@wifi-iface[{self.IFACE_2G_INDEX}].encryption='{encryption}'")

    def set_5g_authentication(self, auth_mode: str) -> None:
        """Set 5G authentication mode."""
        self._ensure_globals_initialized()
        auth_map = {
            "WPA2-Personal": "psk2",
            "WPA2/WPA3-Personal": "sae-mixed",
            "WPA3-Personal": "sae"
        }
        encryption = auth_map.get(auth_mode, "psk2")
        self._execute_command(f"uci set wireless.@wifi-iface[{self.IFACE_5G_INDEX}].encryption='{encryption}'")

    # --- Existing Wireless Configuration Methods (淇敼涓洪渶瑕佹椂妫€鏌?---
    def set_2g_ssid(self, ssid: str) -> None:
        self._ensure_globals_initialized()
        self._execute_command(f"uci set wireless.@wifi-iface[{self.IFACE_2G_INDEX}].ssid='{ssid}'")

    def set_5g_ssid(self, ssid: str) -> None:
        self._ensure_globals_initialized()
        self._execute_command(f"uci set wireless.@wifi-iface[{self.IFACE_5G_INDEX}].ssid='{ssid}'")

    def set_2g_password(self, passwd: str) -> None:
        self._ensure_globals_initialized()
        self._execute_command(f"uci set wireless.@wifi-iface[{self.IFACE_2G_INDEX}].key='{passwd}'")

    def set_5g_password(self, passwd: str) -> None:
        self._ensure_globals_initialized()
        self._execute_command(f"uci set wireless.@wifi-iface[{self.IFACE_5G_INDEX}].key='{passwd}'")

    def set_2g_channel(self, channel: Union[str, int]) -> None:
        self._ensure_globals_initialized()
        ch = str(channel)
        if ch == "auto":
            self._execute_command(f"uci set wireless.{self.RADIO_2G}.channel=auto")
        else:
            self._execute_command(f"uci set wireless.{self.RADIO_2G}.channel={ch}")

    def set_2g_bandwidth(self, width: str) -> None:
        self._ensure_globals_initialized()
        hemode_map = {"20MHZ": "HE20", "40MHZ": "HE40", "20": "HE20", "40": "HE40"}
        hemode = hemode_map.get(width.upper(), "HE20")
        self._execute_command(f"uci set wireless.{self.RADIO_2G}.hemode={hemode}")

    def set_5g_channel_bandwidth(self, *, bandwidth: str | None = None, channel: Union[str, int, None] = None) -> None:
        self._ensure_globals_initialized()
        if channel is not None:
            ch = "auto" if str(channel).lower() == "auto" else str(channel)
            self._execute_command(f"uci set wireless.{self.RADIO_5G}.channel={ch}")
        if bandwidth is not None:
            vhtmodes = {"20MHZ": "VHT20", "40MHZ": "VHT40", "80MHZ": "VHT80", "160MHZ": "VHT160", "20": "VHT20",
                        "40": "VHT40", "80": "VHT80"}
            vhtmode = vhtmodes.get(bandwidth.upper(), "VHT80")
            self._execute_command(f"uci set wireless.{self.RADIO_5G}.vhtmode={vhtmode}")

    # --- 鏂板鏂规硶锛氬吋瀹瑰崕纭曡矾鐢卞櫒API ---
    def set_2g_wireless(self, mode: str) -> None:
        """
        Compatibility method for Asus API.
        On OpenWrt, wireless mode is often controlled by 'htmode' and driver.
        For 'auto', we assume it's already handled by the default config.
        """
        self._ensure_globals_initialized()
        logging.info(f"Ignoring set_2g_wireless('{mode}') on OpenWrt (not applicable).")
        # 濡傛灉鏈潵闇€瑕佹洿绮剧粏鐨勬帶鍒讹紝鍙互鍦ㄨ繖閲屽疄鐜?
        pass

    def set_5g_wireless(self, mode: str) -> None:
        """Same as above for 5G."""
        self._ensure_globals_initialized()
        logging.info(f"Ignoring set_5g_wireless('{mode}') on OpenWrt (not applicable).")
        pass

    def set_country(self, region: str) -> None:
        self._ensure_globals_initialized()
        self._execute_command(f"uci set wireless.{self.RADIO_2G}.country='{region}'")
        self._execute_command(f"uci set wireless.{self.RADIO_5G}.country='{region}'")

    def commit(self) -> None:
        self._execute_command("uci commit wireless")
        self._execute_command("wifi reload")
        time.sleep(5)
        self._execute_command("wifi down")
        time.sleep(5)
        self._execute_command("wifi up")
        time.sleep(5)

    def set_country_code(self, country: str) -> bool:
        # 妫€鏌ョ被鍙橀噺鏄惁宸插垵濮嬪寲
        self._ensure_globals_initialized()

        try:
            # 鐩存帴浣跨敤绫诲彉閲?
            self._execute_command("/etc/init.d/log restart")  # Clear log
            for device_name in [OpenWrtWlControl.RADIO_2G, OpenWrtWlControl.RADIO_5G]:
                self._execute_command(f"uci set wireless.{device_name}.country='{country}'")
            self._execute_command(f"uci set wireless.{self.RADIO_2G}.htmode='HE20'")
            self._execute_command(f"uci set wireless.{self.RADIO_2G}.channel=1")
            self._execute_command(f"uci set wireless.{self.RADIO_5G}.htmode='HE80'")
            self._execute_command(f"uci set wireless.{self.RADIO_5G}.channel=36")
            self._execute_command("uci commit wireless")
            self._execute_command("wifi reload")
            time.sleep(5)
            self._execute_command("wifi down")
            time.sleep(5)
            self._execute_command("wifi up")
            time.sleep(60)
            channel_log = self._execute_command("logread | tail -500")
            chlists = self.extract_latest_chlist_from_log(channel_log)
            return chlists
        except Exception as e:
            logging.error(f"Failed to set country code '{country}': {e}")
            return False

    def get_country_code(self, device_name: str) -> str:
        self._ensure_globals_initialized()
        try:
            for device_name in [OpenWrtWlControl.RADIO_2G, OpenWrtWlControl.RADIO_5G]:
                output = self._execute_command(f"uci get wireless.{device_name}.country")
                return output.strip()
        except Exception as e:
            logging.debug(f"Failed to get country code for {device_name}: {e}")
            return ""

    def configure_and_verify_country_code(self, country_code: str, dut_country_code: str | None = None) -> dict:
        self._ensure_globals_initialized()

        result = {
            'country_code_set': False,
            'verified_country_code': "",
            '2g_channels': [],
            '5g_channels': []
        }
        lookup_country = dut_country_code if dut_country_code is not None else country_code
        upper_lookup_cc = lookup_country.upper()

        try:
            # Step 1: Set country code and check if BuildChannelList appears
            chlist_detected = self.set_country_code(country_code)
            time.sleep(60)

            # Step 2: Verify via UCI get
            verified_codes = [
                self.get_country_code(device)
                for device in [OpenWrtWlControl.RADIO_2G, OpenWrtWlControl.RADIO_5G]
                if self.get_country_code(device)
            ]
            verified_cc = verified_codes[0] if verified_codes else ""

            # Step 3: Determine success
            country_set_success = (verified_cc == country_code and chlist_detected is True)
            result['country_code_set'] = country_set_success
            result['verified_country_code'] = verified_cc

            # Step 4: If successful, fill in expected channels from map
            if upper_lookup_cc in self.REGION_CHANNEL_MAP:
                chan_map = self.REGION_CHANNEL_MAP[upper_lookup_cc]
                result['2g_channels'] = chan_map['2g']
                result['5g_channels'] = chan_map['5g']
                logging.info(
                    f"鉁?Country code '{country_code}' set. "
                    f"Channel lists based on DUT country '{lookup_country}': "
                    f"2.4G: {result['2g_channels']}, 5G: {result['5g_channels']}"
                )
            else:
                logging.warning(f"DUT country '{lookup_country}' not in channel map. Using empty lists.")

        except Exception as e:
            logging.error(f"OpenWrt country code config failed on {self.router_ip}: {e}", exc_info=True)
            raise

        return result

    @staticmethod
    def _parse_iw_channels(output: str) -> list[int]:
        channels = []
        for line in output.splitlines():
            if 'Channel' in line:
                try:
                    ch = int(line.split()[1])
                    channels.append(ch)
                except (IndexError, ValueError):
                    continue
        return sorted(set(channels))

    def _discover_wifi_devices(self) -> List[str]:
        """Discover Wi-Fi radio devices from the router."""
        try:
            output = self._execute_command("uci show wireless")
            if not output:
                logging.warning("No output from 'uci show wireless'.")
                return []
            device_names = re.findall(r"wireless\.([^.]+)=wifi-device", output)
            logging.info(f"Discovered WiFi device names: {device_names}")
            return device_names
        except Exception as e:
            logging.error(f"Failed to discover WiFi devices: {e}")
            return []  # 鎴?raise ConfigError(...)

    @staticmethod
    def extract_latest_chlist_from_log(log_text: str):
        """ Parse log text (e.g., output of 'logread | tail -200') and extract the latest BuildChannelList entries with BandIdx and ChListNum.
        Returns:
            dict: {band_idx: chlist_num}, e.g., {0: 11, 1: 13}
        """
        # Match lines like:
        # ... BuildChannelList() ...: BandIdx = 1, PhyMode = ..., ChListNum = 13:
        pattern = r'BuildChannelList\(\).*BandIdx\s*=\s*(\d+),.*ChListNum\s*=\s*(\d+)'
        found_entries = []
        for line in log_text.strip().splitlines():
            # logging.info(f"region change log: {line}")
            match = re.search(pattern, line)
            if match:
                band_idx = int(match.group(1))
                chlist_num = int(match.group(2))
                found_entries.append((band_idx, chlist_num))

        if not found_entries:
            return False  # or {} 鈥?see note below

        # 鍘婚噸锛氫繚鐣欐瘡涓?band 鏈€杩戜竴娆★紙浠庡悗寰€鍓嶅彇绗竴娆★級
        seen_bands = set()
        unique_entries = []
        for band, num in reversed(found_entries):
            if band not in seen_bands:
                seen_bands.add(band)
                unique_entries.append((band, num))
        unique_entries.reverse()

        # 鎵撳嵃缁撴灉
        for band, num in unique_entries:
            band_name = "2.4G" if band == 0 else "5G/6G" if band == 1 else f"Band{band}"
            logging.info(f"[Channel List Detected] {band_name} (BandIdx={band}): {num} channels")

        return True

    @classmethod
    def reset_globals(cls):
        """Reset cached global Wi-Fi device state."""
        cls.RADIO_2G = None
        cls.RADIO_5G = None
        cls._initialized = False
        logging.info("Global WiFi device state reset")

