"""openwrt uci wl controlThis module is part of the arrisRouter package."""
from __future__ import annotations
import logging
import re, time
from typing import Optional, Union, Dict, Any, List
from .RouterControl import ConfigError
from testing.tool.connect_tool.transports.ssh_tool import ssh_tool


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
        # TH 泰国
        "TH": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # ID 印度尼西亚
        "ID": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]},
        # VN 越南
        "VN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # SG 新加坡
        "SG": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # KZ 哈萨克斯坦
        "KZ": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # TR 土耳其
        "TR": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # OM 阿曼
        "OM": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # SA 沙特阿拉伯
        "SA": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
               },
        # EG 埃及
        "EG": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64]},
        # NG 尼日利亚
        "NG": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [52, 56, 60, 64, 149, 153, 157, 161]},
        # ZA 南非
        "ZA": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # UY 乌拉圭
        "UY": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]},
        # PE 秘鲁
        "PE": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # CO 哥伦比亚
        "CO": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # CR 哥斯达黎加
        "CR": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},

        # NL 荷兰
        "NL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # IT 意大利
        "IT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # PL 波兰
        "PL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RO 罗马尼亚
        "RO": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RO 葡萄牙
        "PT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # SE 瑞典
        "SE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RS 塞尔维亚
        "RS": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        # UA 乌克兰
        "UA": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        #CL:智利
        "CL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]
        },
        # EC 厄瓜多尔
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

        # 关键修改：移除立即的设备发现，但保留原有设计原则
        # 不再在__init__中立即触发SSH连接
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

    # --- 新增：保持原有设计原则的辅助方法 ---

    def discover_devices(self) -> List[str]:
        """
        显式发现WiFi设备（应该在测试开始时调用一次）
        保持原有设计原则：一次发现，全局使用

        Returns:
            设备名称列表
        """
        # 如果已经全局初始化，直接返回
        if OpenWrtWlControl._initialized:
            if OpenWrtWlControl.RADIO_2G and OpenWrtWlControl.RADIO_5G:
                return [OpenWrtWlControl.RADIO_2G, OpenWrtWlControl.RADIO_5G]

        try:
            # 发现设备
            devices = self._discover_wifi_devices()

            if len(devices) >= 2:
                # 设置全局类变量
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
        """确保全局设备信息已初始化（在需要设备信息的方法中调用）"""
        if not OpenWrtWlControl._initialized:
            # 自动尝试初始化
            self.discover_devices()

        if OpenWrtWlControl.RADIO_2G is None or OpenWrtWlControl.RADIO_5G is None:
            raise RuntimeError("WiFi devices not discovered. Call discover_devices() first.")

    # --- 新增方法：兼容华硕路由器API ---
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

    # --- Existing Wireless Configuration Methods (修改为需要时检查)---
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

    # --- 新增方法：兼容华硕路由器API ---
    def set_2g_wireless(self, mode: str) -> None:
        """
        Compatibility method for Asus API.
        On OpenWrt, wireless mode is often controlled by 'htmode' and driver.
        For 'auto', we assume it's already handled by the default config.
        """
        self._ensure_globals_initialized()
        logging.info(f"Ignoring set_2g_wireless('{mode}') on OpenWrt (not applicable).")
        # 如果未来需要更精细的控制，可以在这里实现
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
        # 检查类变量是否已初始化
        self._ensure_globals_initialized()

        try:
            # 直接使用类变量
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
                    f"✅ Country code '{country_code}' set. "
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
        """内部方法：实际发现WiFi设备（不直接对外暴露）"""
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
            return []  # 或 raise ConfigError(...)

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
            return False  # or {} — see note below

        # 去重：保留每个 band 最近一次（从后往前取第一次）
        seen_bands = set()
        unique_entries = []
        for band, num in reversed(found_entries):
            if band not in seen_bands:
                seen_bands.add(band)
                unique_entries.append((band, num))
        unique_entries.reverse()

        # 打印结果
        for band, num in unique_entries:
            band_name = "2.4G" if band == 0 else "5G/6G" if band == 1 else f"Band{band}"
            logging.info(f"[Channel List Detected] {band_name} (BandIdx={band}): {num} channels")

        return True

    @classmethod
    def reset_globals(cls):
        """重置全局状态（用于测试或重新初始化）"""
        cls.RADIO_2G = None
        cls.RADIO_5G = None
        cls._initialized = False
        logging.info("Global WiFi device state reset")
