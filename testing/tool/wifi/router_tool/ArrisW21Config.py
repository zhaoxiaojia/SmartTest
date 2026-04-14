"""arris telnet wl control
This module is part of the arrisRouter package."""

from __future__ import annotations

import logging
import re, time
from typing import Optional
from typing import Union

from .RouterControl import ConfigError
from .AsusRouter.AsusTelnetNvramControl import AsusBaseControl
from testing.tool.connect_tool.transports.telnet_tool import TelnetSession


class ArrisTelnetWlControl(AsusBaseControl):
    """arris telnet wl control for querying wireless regulatory info.

    This class provides methods to query and parse wireless interface
    information via 'wl' commands over Telnet, such as country code,
    channel, and client list.

    Parameters
    ----------
    router_key : str
        Key identifying the router in configuration.
    display : bool, optional
        Whether to run in visible mode (default: True).
    address : str | None, optional
        Router IP address; if None, uses default from config.
    prompt : bytes, optional
        Telnet shell prompt bytes (default: b':/tmp/home/root#').

    Returns
    -------
    None
    """

    TELNET_PORT = 23
    TELNET_USER = 'admin'
    TELNET_PASS = '88888888'
    WL_INTERFACES = ['wl0', 'wl1', 'wl2']  # Broadcom standard naming

    def __init__(
            self,
            router_key: str,
            *,
            display: bool = True,
            address: str | None = None,
            prompt: bytes = b"> "  # 👈 Merlin 完整 shell 的典型提示符
    ) -> None:
        super().__init__(router_key, display=display, address=address)
        if address is not None:
            self._arris_router_ip = address
        else:
            # 如果没传 address，再回退到父类的逻辑
            self._arris_router_ip = router_key

        self.xpath = {
            "user": "admin",  # 如果 Telnet 需要用户名
            "passwd": "88888888"  # 替换为您的真实密码
        }
        CORRECT_ROUTER_IP = "192.168.7.1"
        self.prompt = prompt
        self.telnet = None
        # self.telnet = TelnetSession(
        #     host=CORRECT_ROUTER_IP,  # 👈 关键：使用父类设置好的 self.address
        #     port=23,
        #     timeout=10
        # )
        self._is_logged_in  = False
        logging.info(f"ArrisTelnetWlControl init: router={router_key} host={self.address} prompt={self.prompt}")

    def _login(self) -> None:
        """ULTRA-DEBUG VERSION: Login and capture EVERYTHING."""
        self._is_logged_in = False
        target_host = self._arris_router_ip
        logging.info(f"[ULTRA-DEBUG] Starting login to {target_host}")

        if self.telnet is not None:
            try:
                self.telnet.close()
            except Exception:
                pass

        self.telnet = TelnetSession(host=target_host, port=self.TELNET_PORT, timeout=10)

        try:
            self.telnet.open()
            logging.info("[ULTRA-DEBUG] Connection opened.")

            # --- CAPTURE ALL DATA UNTIL 'Login:' ---
            logging.info("[ULTRA-DEBUG] Reading all data until 'Login:'...")
            all_data_before_login = b""
            while b"Login:" not in all_data_before_login:
                chunk = self.telnet.read_some(timeout=2)
                if not chunk:
                    break
                all_data_before_login += chunk
                if len(all_data_before_login) > 1000:
                    break
            logging.info(f"[ULTRA-DEBUG] Data before 'Login:': {all_data_before_login!r}")

            # Send username
            self.telnet.write(self.TELNET_USER.encode("ascii") + b"\n")
            time.sleep(0.5)

            # --- CAPTURE ALL DATA UNTIL 'Password:' ---
            logging.info("[ULTRA-DEBUG] Reading all data until 'Password:'...")
            all_data_before_password = b""
            while b"Password:" not in all_data_before_password:
                chunk = self.telnet.read_some(timeout=2)
                if not chunk:
                    break
                all_data_before_password += chunk
                if len(all_data_before_password) > 1000:
                    break
            logging.info(f"[ULTRA-DEBUG] Data before 'Password:': {all_data_before_password!r}")

            # Send password
            self.telnet.write(self.TELNET_PASS.encode("ascii") + b"\n")
            time.sleep(0.5)

            # --- CAPTURE ALL DATA FOR 10 SECONDS AFTER SENDING PASSWORD ---
            logging.info("[ULTRA-DEBUG] Reading all data for 10 seconds after sending password...")
            final_output = b""
            start_time = time.time()
            while (time.time() - start_time) < 10:
                chunk = self.telnet.read_some(timeout=1)
                if chunk:
                    final_output += chunk
                    logging.info(f"[ULTRA-DEBUG] Received chunk: {chunk!r}")
                else:
                    break
            logging.info(f"[ULTRA-DEBUG] FINAL OUTPUT AFTER PASSWORD: {final_output!r}")

            # Check if prompt is in the final output
            if self.prompt in final_output:
                logging.info("[ULTRA-DEBUG] SUCCESS: Prompt found!")
            else:
                raise RuntimeError(f"Prompt {self.prompt!r} NOT FOUND in final output.")

            # === 关键修复：在 try 块内完成所有设置 ===
            # 1. 先标记为已登录，避免后续操作触发重连
            self._is_logged_in = True

            # 2. 手动切换到 shell 模式
            # 注意：这里不能用 self.telnet_write，因为它会触发 _ensure_connection！
            self.telnet.write(b"sh\n")
            shell_output = self.telnet.read_until(b"# ", timeout=10)
            logging.info(f"[ULTRA-DEBUG] Shell switch output: {shell_output!r}")

            # 3. 更新提示符
            self.prompt = b"# "
            logging.info("[ULTRA-DEBUG] Switched to root shell (#).")
            logging.info("[ULTRA-DEBUG] Login successful!")

        except Exception as e:
            self._is_logged_in = False
            logging.error(f"[ULTRA-DEBUG] Login failed: {e}", exc_info=True)
            if self.telnet is not None:
                try:
                    self.telnet.close()
                except Exception:
                    pass
            self.telnet = None
            raise  # Re-raise the exception

    def set_2g_ssid(self, ssid: str) -> None:
        """Arris: Set 2.4G SSID via wl command."""
        self.telnet_write(f"wl -i wl0 ssid={ssid}")

    def set_5g_ssid(self, ssid: str) -> None:
        """Arris: Set 5G SSID via wl command."""
        self.telnet_write(f"wl -i wl1 ssid={ssid}")

    def set_2g_password(self, passwd: str) -> None:
        """Arris: Set 2.4G password (WPA2 only)."""
        self.telnet_write(f"wl -i wl0_wpa_psk={passwd}")

    def set_5g_password(self, passwd: str) -> None:
        self.telnet_write(f"wl -i wl1_wpa_psk={passwd}")

    def set_2g_channel(self, channel: Union[str, int]) -> None:
        """Arris: Set 2.4G channel."""
        channel = str(channel)
        self.telnet_write(f"wl -a wl0 down")
        if channel == "auto":
            self.telnet_write("nvram set wl0_channel_auto=1") # 0=关闭auto，1=开启auto
        else:
            self.telnet_write(f"nvram set wl0_channel={channel}")
            self.telnet_write("nvram set wl0_channel_auto=0") # 0=关闭auto，1=开启auto

    def set_2g_bandwidth(self, width: str) -> None:
        self.telnet_write(f"nvram set wl0_bandwidth={width}")

    def set_5g_channel_bandwidth(self, *, bandwidth: str | None = None, channel: Union[str, int, None] = None) -> None:
        """Arris: Set 5G channel and bandwidth."""
        cmd_parts = ["nvram set"]
        if channel is not None:
            ch = str(channel)
            cmd_parts.append(f"wl1_channel={ch}")
        if bandwidth is not None:
            # Arris 5G bandwidth mapping (example)
            bw_map = {"20MHZ": "20", "40MHZ": "40", "80MHZ": "80"}
            if bandwidth in bw_map:
                cmd_parts.append(f"wl1_bandwidth={bw_map[bandwidth]}")
        if len(cmd_parts) > 2:
            self.telnet_write(" ".join(cmd_parts))

    def set_country(self, region: str) -> None:
        self.telnet_write(f"wl -a wl0 down && wl -a wl1 down && wl -a wl2 down")
        self.telnet_write(f"wl -a wl0 country {region}")
        self.telnet_write(f"wl -a wl1 country {region}")
        self.telnet_write(f"wl -a wl2 country {region}")
        self.telnet_write(f"nvram set wl0_country={region} && nvram set wl1_country={region} && nvram set wl2_country={region}")
        self.telnet_write("nvram commit")
        self.telnet_write(f"wl -a wl0 up && wl -a wl1 up && wl -a wl2 up")


    def set_5g_password(self, passwd: str) -> None:
        self.telnet_write(f"wl -i wl1_wpa_psk={passwd}")

    def commit(self) -> None:
        self.telnet_write("nvram commit")
        self.telnet_write("wl -a wl0 up")
        self.telnet_write("wl -a wl1 up")

    def _ensure_connection(self) -> None:
        """Ensure active Telnet connection."""
        if (
            not self._is_logged_in
            or self.telnet is None
            or not getattr(self.telnet, "is_connected", lambda: False)()
        ):
            logging.info("Telnet reconnect required (logged_in=%s)", self._is_logged_in)
            self._login()

    def telnet_write(
        self,
        cmd: str,
        *,
        wait_prompt: bool = True,
        timeout: int = 30,
        retry_once: bool = True,
    ) -> str:
        """Execute command and return output.

        Parameters
        ----------
        cmd : str
            Command to execute.
        wait_prompt : bool
            Whether to wait for shell prompt after execution.
        timeout : int
            Read timeout in seconds.
        retry_once : bool
            Retry once on failure.

        Returns
        -------
        str
            Command output (stripped).
        """
        self._ensure_connection()
        data = (cmd + '\n').encode('ascii', errors='ignore')
        logging.info("Executing: %r", cmd)

        try:
            assert self.telnet is not None
            self.telnet.write(data)
            if wait_prompt:
                output = self.telnet.read_until(self.prompt, timeout=timeout)
                # Remove command echo and prompt
                lines = output.decode('utf-8', errors='ignore').splitlines()
                cleaned = '\n'.join(lines[1:-1]) if len(lines) > 2 else ''
                return cleaned.strip()
            return ""
        except Exception as exc:
            #self._is_logged_in = False
            logging.error("Telnet command %r failed: %s", cmd, exc, exc_info=True)
            if retry_once:
                logging.info("Telnet retry once: %r", cmd)
                if self.telnet is not None:
                    try:
                        self.telnet.close()
                    except Exception:
                        pass
                self.telnet = None
                self._login()
                return self.telnet_write(cmd, wait_prompt=wait_prompt, timeout=timeout, retry_once=False)
            raise RuntimeError(f"Telnet command failed: {exc}") from exc

    def get_country_code(self, interface: str = 'wl0') -> str:
        """Get current regulatory country code for given wireless interface.

        Parameters
        ----------
        interface : str
            Wireless interface name (e.g., 'wl0', 'wl1', 'wl2').

        Returns
        -------
        str
            Country code (e.g., 'US', 'KR', 'SG'), or empty string if not found.
        """
        if interface not in self.WL_INTERFACES:
            raise ConfigError(f"Invalid wireless interface: {interface}")

        output = self.telnet_write(f"wl -i {interface} country")
        if not output:
            logging.warning("Empty output from 'wl -i %s country'", interface)
            return ""

        # Parse line like: "US (US/0) United States"
        match = re.search(r'^([A-Z]{2})', output.strip())
        if match:
            country = match.group(1)
            logging.info("Detected country code on %s: %s", interface, country)
            return country

        logging.warning("Failed to parse country code from: %r", output)
        return ""

    def get_all_country_codes(self) -> dict[str, str]:
        """Get country codes for all known wireless interfaces.

        Returns
        -------
        dict
            Mapping of interface -> country code (e.g., {'wl0': 'US', 'wl1': 'US'}).
        """
        result = {}
        for iface in self.WL_INTERFACES:
            try:
                country = self.get_country_code(interface=iface)
                if country:
                    result[iface] = country
            except Exception as e:
                logging.debug("Failed to get country for %s: %s", iface, e)
        return result

    def quit(self) -> None:
        """Close Telnet session."""
        try:
            if self.telnet is not None and self._is_logged_in:
                self.telnet_write('exit', wait_prompt=False)
                self.telnet.close()
        except Exception as exc:
            logging.error("Telnet quit failed: %s", exc)
        finally:
            self.telnet = None
            self._is_logged_in = False

    def configure_and_verify_country_code(self, country_code: str) -> dict:
        """
        Arris-specific implementation of country code configuration and verification.
        This method first SETS the country code, then verifies it.

        Returns unified result dict.
        """
        result = {
            'country_code_set': False,
            'verified_country_code': "",
            '2g_channels': [],
            '5g_channels': []
        }
        try:
            # === Step 1: SET the country code ===
            self.set_country(country_code)
            #self.commit()  # Ensure changes are saved and applied

            # Optional: Wait a moment for the driver to fully apply new regulatory domain
            import time
            time.sleep(2)

            # === Step 2: VERIFY the country code ===
            cc_wl0 = self.get_country_code('wl0')
            cc_wl1 = self.get_country_code('wl1')
            verified_cc = cc_wl0 or cc_wl1
            result['verified_country_code'] = verified_cc
            result['country_code_set'] = (verified_cc == country_code)

            # === Step 3: Get available channel lists ===
            chlist_2g_str = self.telnet_write("wl -i wl0 chanspec -b")
            chlist_5g_str = self.telnet_write("wl -i wl1 chanspec -b")
            result['2g_channels'] = self._parse_chanspec_output(chlist_2g_str)
            result['5g_channels'] = self._parse_chanspec_output(chlist_5g_str)

        except Exception as e:
            logging.error(f"Arris country code configuration/verification failed: {e}", exc_info=True)
            raise  # Re-raise to let the test handle the failure

        return result

    @staticmethod
    def _parse_chanspec_output(output: str) -> list[int]:
        """Parse 'wl -i wlX chanspec -b' output into channel list."""
        for line in output.splitlines():
            if 'Chanspecs:' in line:
                return [int(ch) for ch in line.split(':')[1].split() if ch.isdigit()]
        return []
