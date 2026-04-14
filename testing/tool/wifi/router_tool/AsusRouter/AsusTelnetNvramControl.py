"""
Asus telnet nvram control

This module is part of the AsusRouter package.
"""

from __future__ import annotations

import logging,re
import time
from typing import List, Optional, Union

from ..RouterControl import ConfigError
from .AsusBaseControl import AsusBaseControl
from testing.tool.connect_tool.transports.telnet_tool import TelnetSession
from ..router_telnet_control import TelnetVerifier
from ..RouterControl import REGION_CHANNEL_MAP, RouterTools


class AsusTelnetNvramControl(AsusBaseControl):
    """
        Asus telnet nvram control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    CHANNEL_2 = ['auto', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14']
    CHANNEL_2_CHANSPEC_MAP = {
        'auto': '0',
        '1': '1l',
        '2': '2l',
        '3': '3l',
        '4': '4l',
        '5': '5l',
        '6': '6l',
        '7': '7u',
        '8': '8u',
        '9': '9u',
        '10': '10u',
        '11': '11u',
        '12': '12u',
        '13': '13u',
        '14': '14',
    }

    MODE_PARAM = {
        'Open System': 'openowe',
        'Shared Key': 'shared',
        'WPA2-Personal': 'psk2',
        'WPA3-Personal': 'sae',
        'WPA/WPA2-Personal': 'pskpsk2',
        'WPA2/WPA3-Personal': 'psk2sae',
    }

    WL1_BANDWIDTH_MAP = {
        '20MHZ': ('0', '20'),
        '40MHZ': ('1', '40'),
        '80MHZ': ('2', '80'),
        '20/40/80MHZ': ('2', '80'),
        '20/40MHZ': ('1', '40'),
        '20/40/80/160MHZ': ('3', '80'),
    }

    WIRELESS_2 = ['auto', '11n', '11g', '11b', '11ax', 'Legacy']
    WIRELESS_5 = ['auto', '11a', '11n', '11ac', '11ax', 'Legacy']
    BANDWIDTH_2 = ['20/40', '20', '40',]
    
    TELNET_PORT = 23
    TELNET_USER = 'admin'

    def __init__(self, router_key: str, *, display: bool = True, address: str | None = None,
                 prompt: bytes = b':/tmp/home/root#') -> None:
        """
            Init
                Parameters
                ----------
                router_key : object
                    Description of parameter 'router_key'.
                display : object
                    Flag indicating whether the browser should run in visible mode.
                address : object
                    The router's login address or IP address; if None, a default is used.
                prompt : object
                    Description of parameter 'prompt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super().__init__(router_key, display=display, address=address)
        self.host = self.address
        self.port = self.TELNET_PORT
        self.prompt = prompt
        self.telnet: TelnetSession | None = None
        self._is_logged_in = False
        self._wl0_channel: str = 'auto'
        self._wl0_bandwidth: str | None = None
        self._last_wl0_chanspec: str | None = None
        self._wl1_channel: str | None = 'auto'
        self._wl1_chanspec_suffix: str | None = '80'
        self._last_wl1_chanspec: str | None = None
        self._wl1_bandwidth_map = dict(self.WL1_BANDWIDTH_MAP)
        logging.info(
            "AsusTelnetNvramControl init: router=%s host=%s prompt=%s",
            self.router_info,
            self.host,
            self.prompt,
        )
        if self.router_info in {'asus_88u', 'asus_88u_pro', 'asus_86u',}:
            self._wl1_bandwidth_map.update({
                '20MHZ': ('1', '20'),
                '40MHZ': ('2', '40'),
                '80MHZ': ('3', '80'),
                '20/40/80MHZ': ('0', '80'),
                '20/40/80/160MHZ': ('0', '80'),
            })

    def _login(self) -> None:
        """
            Login
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._is_logged_in = False
        logging.info("Telnet login start: host=%s port=%s", self.host, self.port)

        if self.telnet is not None:
            try:
                self.telnet.close()
            except Exception:
                pass
        self.telnet = TelnetSession(self.host, self.port, timeout=10)

        try:
            try:
                self.telnet.open()
            except TimeoutError as exc:
                raise RuntimeError(
                    f"Telnet connect timeout: {self.host}:{self.port}. "
                    f"Check router IP (e.g. config_basic.yaml -> router.address) and that telnet is enabled."
                ) from exc
            except OSError as exc:
                raise RuntimeError(
                    f"Telnet connect error: {self.host}:{self.port}: {exc}. "
                    f"Check router IP (e.g. config_basic.yaml -> router.address) and network reachability."
                ) from exc

            login_banner = self.telnet.read_until(b"login:", timeout=10)
            if not login_banner.endswith(b"login:"):
                raise RuntimeError(f"Telnet login prompt not found: {login_banner!r}")
            self.telnet.write(self.TELNET_USER.encode("ascii") + b"\n")

            password_banner = self.telnet.read_until(b"Password:", timeout=10)
            if not password_banner.endswith(b"Password:"):
                raise RuntimeError(f"Telnet password prompt not found: {password_banner!r}")
            self.telnet.write(str(self.xpath["passwd"]).encode("ascii") + b"\n")

            post_login = self.telnet.read_until(self.prompt, timeout=10)
            if not post_login.endswith(self.prompt):
                raise RuntimeError(f"Telnet login failed; prompt not reached: {post_login!r}")
        except Exception:
            self._is_logged_in = False
            if self.telnet is not None:
                try:
                    self.telnet.close()
                except Exception:
                    pass
            self.telnet = None
            raise

        self._is_logged_in = True
        logging.info("Telnet login success")

    def _ensure_connection(self) -> None:
        """
            Ensure connection
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if (
            not self._is_logged_in
            or self.telnet is None
            or not getattr(self.telnet, "is_connected", lambda: False)()
        ):
            logging.info("Telnet reconnect required (logged_in=%s)", self._is_logged_in)
            self._login()

    def telnet_write(
        self,
        cmd: Union[str, bytes],
        *,
        wait_prompt: bool = False,
        timeout: int = 30,
        retry_once: bool = True,
    ) -> None:
        """
            Telnet write
                Logs informational or debugging messages for tracing execution.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                cmd : object
                    Description of parameter 'cmd'.
                wait_prompt : object
                    Description of parameter 'wait_prompt'.
                timeout : object
                    Maximum time in seconds to wait for a condition to be satisfied.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._ensure_connection()
        if isinstance(cmd, str):
            data = (cmd + '\n').encode('ascii', errors='ignore')
        else:
            data = cmd + (b'' if cmd.endswith(b'\n') else b'\n')

        logging.info("Executing: %r", cmd)
        try:
            assert self.telnet is not None
            self.telnet.write(data)
            if wait_prompt:
                self.telnet.read_until(self.prompt, timeout=timeout)
        except Exception as exc:
            self._is_logged_in = False
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
                self.telnet_write(cmd, wait_prompt=wait_prompt, timeout=timeout, retry_once=False)
                return
            raise RuntimeError(f"Telnet command failed: {exc}") from exc

    def _ensure_prompt_ready(self) -> None:
        """
            Ensure prompt is ready before issuing a new batch of commands.
        """
        try:
            logging.info("Telnet ensure prompt ready")
            self.telnet_write('', wait_prompt=True, timeout=5)
        except Exception:
            self._is_logged_in = False
            logging.info("Telnet prompt ready failed, relogin")
            self._login()

    @staticmethod
    def _normalize_bandwidth(width: str) -> str:
        """
            Normalize bandwidth
                Parameters
                ----------
                width : object
                    Description of parameter 'width'.
                Returns
                -------
                str
                    Description of the returned value.
        """
        return width.replace(' ', '').upper()

    def _get_wl0_chanspec(self) -> str:
        """
            Get wl0 chanspec
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                str
                    Description of the returned value.
        """
        channel = self._wl0_channel or 'auto'
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        if self._wl0_bandwidth == '40':
            return self.CHANNEL_2_CHANSPEC_MAP[channel]
        return '0' if channel == 'auto' else channel

    def _update_wl0_chanspec(self, *, force: bool = False) -> None:
        """
            Update wl0 chanspec
                Parameters
                ----------
                force : object
                    Description of parameter 'force'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        chanspec = self._get_wl0_chanspec()
        if not force and chanspec == self._last_wl0_chanspec:
            return
        self.telnet_write(f'nvram set wl0_chanspec={chanspec};')
        self._last_wl0_chanspec = chanspec

    def _get_wl1_40mhz_chanspec(self, channel: str) -> str:
        """
            Get wl1 40mhz chanspec
                Parameters
                ----------
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                str
                    Description of the returned value.
        """
        if channel == 'auto':
            return '0'
        try:
            index = self.CHANNEL_5.index(channel)
        except ValueError as exc:
            raise ConfigError('channel element error') from exc
        suffix = 'l' if (index - 1) % 2 == 0 else 'u'
        return f'{channel}{suffix}'

    def _update_wl1_chanspec(self, *, force: bool = False) -> None:
        """
            Update wl1 chanspec
                Parameters
                ----------
                force : object
                    Description of parameter 'force'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        suffix = self._wl1_chanspec_suffix
        if not suffix:
            return
        channel = self._wl1_channel or 'auto'
        if suffix == '40':
            chanspec = self._get_wl1_40mhz_chanspec(channel)
        else:
            channel_value = '0' if channel == 'auto' else channel
            chanspec = f'{channel_value}/{suffix}'
        if not force and chanspec == self._last_wl1_chanspec:
            return
        self.telnet_write(f'nvram set wl1_chanspec={chanspec};')
        self._last_wl1_chanspec = chanspec

    def quit(self) -> None:
        """
            Quit
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        try:
            if self.telnet is not None:
                if self._is_logged_in:
                    try:
                        self.telnet_write('exit')
                    except Exception:
                        logging.exception('Telnet exit command failed')
                self.telnet.close()
        except Exception as exc:
            logging.error("Telnet quit failed: %s", exc)
        finally:
            self.telnet = None
            self._is_logged_in = False

    def set_2g_ssid(self, ssid: str) -> None:
        """
            Set 2g SSID
                Parameters
                ----------
                ssid : object
                    Wi‑Fi network SSID used for association.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl0_ssid={ssid};')

    def set_5g_ssid(self, ssid: str) -> None:
        """
            Set 5g SSID
                Parameters
                ----------
                ssid : object
                    Wi‑Fi network SSID used for association.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl1_ssid={ssid};')

    def set_2g_wireless(self, mode: str) -> None:
        """
            Set 2g wireless
                Parameters
                ----------
                mode : object
                    Wireless mode to configure on the router (e.g. 11n, 11ax).
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = {
            'auto': 'nvram set wl0_11ax=1;nvram set wl0_nmode_x=0;',
            '11n': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=1;',
            '11g': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=5;',
            '11b': 'nvram set wl0_11ax=0;nvram set wl0_nmode_x=6;',
            '11ax': 'nvram set wl0_11ax=1;nvram set wl0_nmode_x=0',
            'Legacy': 'nvram set wl0_he_features=0;nvram set wl0_nmode_x=2;',
        }
        if mode not in self.WIRELESS_2:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_5g_wireless(self, mode: str) -> None:
        """
            Set 5g wireless
                Parameters
                ----------
                mode : object
                    Wireless mode to configure on the router (e.g. 11n, 11ax).
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = {
            'auto': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=0;',
            '11a': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=7;',
            '11n': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=1;',
            '11ac': 'nvram set wl1_11ax=0;nvram set wl1_nmode_x=0;', #3
            '11ax': 'nvram set wl1_11ax=1;nvram set wl1_nmode_x=9;',
            'Legacy': 'nvram set wl1_he_features=0;nvram set wl1_nmode_x=2;',
        }
        if mode not in self.WIRELESS_5:
            raise ConfigError('wireless element error')
        self.telnet_write(cmd[mode])

    def set_2g_password(self, passwd: str) -> None:
        """
            Set 2g password
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl0_wpa_psk={passwd};')

    def set_5g_password(self, passwd: str) -> None:
        """
            Set 5g password
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl1_wpa_psk={passwd};')

    def set_2g_authentication(self, method: str) -> None:
        """
            Set 2g authentication
                Parameters
                ----------
                method : object
                    Description of parameter 'method'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = 'nvram set wl0_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_2g_wep_encrypt('None')

    def set_5g_authentication(self, method: str) -> None:
        """
            Set 5g authentication
                Parameters
                ----------
                method : object
                    Description of parameter 'method'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        cmd = 'nvram set wl1_auth_mode_x={};'
        mode_list = self.AUTHENTICATION_METHOD if method != 'Legacy' else self.AUTHENTICATION_METHOD_LEGCY
        if method not in mode_list:
            raise ConfigError('security protocol method element error')
        self.telnet_write(cmd.format(self.MODE_PARAM[method]))
        if method == 'Open System':
            self.set_5g_wep_encrypt('None')

    def set_2g_channel(self, channel: Union[str, int]) -> None:
        """
            Set 2g channel
                Parameters
                ----------
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                None
                    This function does not return a value.
        """
        channel = str(channel)
        if channel not in self.CHANNEL_2:
            raise ConfigError('channel element error')
        self._wl0_channel = channel
        self._update_wl0_chanspec(force=True)

    def set_2g_bandwidth(self, width: str) -> None:
        """
            Set 2g bandwidth
                Parameters
                ----------
                width : object
                    Description of parameter 'width'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        # ===== 新增：清理输入，移除空格和 "MHz" =====
        width = width.replace(" ", "").replace("MHz", "")

        if width not in self.BANDWIDTH_2:
            raise ConfigError('bandwidth element error')
        normalized_width = self._normalize_bandwidth(width)
        if normalized_width != self._wl0_bandwidth:
            self._wl0_bandwidth = normalized_width
            self._update_wl0_chanspec(force=True)
        self.telnet_write(f'nvram set wl0_bw={self.BANDWIDTH_2.index(width)};')

    def set_5g_channel_bandwidth(
            self,
            *,
            bandwidth: str | None = None,
            channel: Union[str, int, None] = None,
    ) -> None:
        """
            Set 5g channel bandwidth
                Parameters
                ----------
                bandwidth : object
                    Channel bandwidth (e.g. 20 MHz, 40 MHz, 80 MHz) when configuring wireless settings.
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                None
                    This function does not return a value.
        """
        needs_update = False
        if channel is not None:
            channel = str(channel)
            if channel not in self.CHANNEL_5:
                raise ConfigError('channel element error')
            if channel != self._wl1_channel:
                self._wl1_channel = channel
                needs_update = True
        if bandwidth is not None:
            normalized_width = self._normalize_bandwidth(bandwidth)
            mapping = self._wl1_bandwidth_map.get(normalized_width)
            if mapping is None:
                raise ConfigError('bandwidth element error')
            bw_value, suffix = mapping
            if suffix != self._wl1_chanspec_suffix:
                self._wl1_chanspec_suffix = suffix
                needs_update = True
            if needs_update:
                self._update_wl1_chanspec(force=True)
                needs_update = False
            self.telnet_write(f'nvram set wl1_bw={bw_value};')
        elif needs_update:
            self._update_wl1_chanspec(force=True)

    def set_2g_wep_encrypt(self, encrypt: str) -> None:
        """
            Set 2g wep encrypt
                Parameters
                ----------
                encrypt : object
                    Description of parameter 'encrypt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt element error')
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(f'nvram set wl0_wep_x={index};nvram set w1_wep_x={index};')

    def set_5g_wep_encrypt(self, encrypt: str) -> None:
        """
            Set 5g wep encrypt
                Parameters
                ----------
                encrypt : object
                    Description of parameter 'encrypt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if encrypt not in self.WEP_ENCRYPT:
            raise ConfigError('wep encrypt element error')
        index = '1' if '64' in encrypt else '2'
        index = '0' if encrypt == 'None' else index
        self.telnet_write(f'nvram set wl1_wep_x={index};nvram set w1_wep_x={index};')

    def set_2g_wep_passwd(self, passwd: str) -> None:
        """
            Set 2g wep passwd
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl0_key1={passwd};')

    def set_5g_wep_passwd(self, passwd: str) -> None:
        """
            Set 5g wep passwd
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.telnet_write(f'nvram set wl1_key1={passwd};')

    def commit(self) -> None:
        """
            Commit
                Pauses execution for a specified duration to allow operations to complete.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._update_wl1_chanspec()
        self.telnet_write('nvram set wl0_radio=1;', wait_prompt=False)
        self.telnet_write('nvram set wl1_radio=1;', wait_prompt=False)
        self.telnet_write('nvram commit;', wait_prompt=True, timeout=60)
        self.telnet_write('restart_wireless &', wait_prompt=False)
        output = self._wait_restart_wireless_output(timeout=180, idle_window=3)
        logging.info(
            "===== restart_wireless output begin =====\n%s\n===== restart_wireless output end =====",
            output,
        )

    def _wait_restart_wireless_output(self, *, timeout: int, idle_window: int) -> str:
        """
            Wait for ``restart_wireless &`` background output to finish.

            The router typically prints output for a while after ``restart_wireless &``.
            We drain output until it becomes idle for ``idle_window`` seconds and we
            observed the expected markers; otherwise raise.
        """
        self._ensure_connection()
        assert self.telnet is not None

        required_primary = "restart wireless..."
        required_any = (
            "Failed to connect to hostapd",
            "radio_iflist[0]:",
            "primary_iflist:",
            "filtered_iflist:",
            "WAN bonding is already disabled",
        )

        buf = b""
        max_buf = 128 * 1024
        start = time.time()
        last_activity = start
        seen_primary = False
        seen_any = False

        while time.time() - start < timeout:
            chunk = self.telnet.read_some(4096, timeout=1)
            if chunk:
                buf += chunk
                if len(buf) > max_buf:
                    buf = buf[-max_buf:]
                last_activity = time.time()
                text = buf.decode("utf-8", errors="ignore")
                if required_primary in text:
                    seen_primary = True
                if any(token in text for token in required_any):
                    seen_any = True
                continue

            if seen_primary and seen_any and time.time() - last_activity >= idle_window:
                break

        if not (seen_primary and seen_any):
            raise RuntimeError(
                f"restart_wireless output timeout (seen_primary={seen_primary} seen_any={seen_any})"
            )

        # Re-draw prompt (manual users press Enter after output finishes).
        try:
            self.telnet.write(b"\n")
            self.telnet.read_until(self.prompt, timeout=10)
        except EOFError as exc:
            self._is_logged_in = False
            raise RuntimeError(f"Telnet disconnected while waiting for prompt: {exc}") from exc

        return buf.decode("utf-8", errors="ignore").strip()

    def change_setting(self, router) -> bool:
        """
            Change setting
                Pauses execution for a specified duration to allow operations to complete.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                bool
                    Description of the returned value.
        """
        logging.info("Router change_setting start: band=%s ssid=%s", router.band, router.ssid)
        self._ensure_prompt_ready()
        try:
            if router.ssid:
                if '2' in router.band:
                    self.set_2g_ssid(router.ssid)
                    self.set_5g_ssid(router.ssid + "_bat")
                else:
                    self.set_5g_ssid(router.ssid)
                    self.set_2g_ssid(router.ssid + "_bat")

            if router.wireless_mode:
                if '2' in router.band:
                    self.set_2g_wireless(router.wireless_mode)
                else:
                    self.set_5g_wireless(router.wireless_mode)

            if router.password:
                if '2' in router.band:
                    self.set_2g_password(router.password)
                else:
                    self.set_5g_password(router.password)

            if router.security_mode:
                if '2' in router.band:
                    self.set_2g_authentication(router.security_mode)
                else:
                    self.set_5g_authentication(router.security_mode)

            channel_5g: Union[str, int, None] = None
            if router.channel:
                if '2' in router.band:
                    self.set_2g_channel(router.channel)
                else:
                    channel_5g = router.channel

            if router.bandwidth:
                if '2' in router.band:
                    self.set_2g_bandwidth(router.bandwidth)
                else:
                    self.set_5g_channel_bandwidth(bandwidth=router.bandwidth, channel=channel_5g)
            elif channel_5g is not None:
                self.set_5g_channel_bandwidth(channel=channel_5g)

            self.commit()
            time.sleep(3)
            logging.info('Router setting done')
            return True
        finally:
            logging.info("Router change_setting cleanup: quit telnet")
            self.quit()
    
    def set_hidden_ssid(self, hide_2g: bool = False, hide_5g: bool = False) -> None:
        """
        Hiddle 2.4G or 5G SSID

        Parameters
        ----------
        hide_2g : bool
            True means 2.4G SSID（AX86U_24G）
        hide_5g : bool
            True means 5G SSID（AX86U_5G）
        """
        # hiddle: wlX_closed
        logging.info(f"set_hidden_ssid called with hide_2g={hide_2g}, hide_5g={hide_5g}")
        self.telnet_write(f"nvram set wl0_closed={'1' if hide_2g else '0'};")
        self.telnet_write(f"nvram set wl1_closed={'1' if hide_5g else '0'};")

        # commit
        self.telnet_write("nvram commit;", wait_prompt=True, timeout=60)

        # restart wireless
        self.telnet_write("restart_wireless &", wait_prompt=False)

        # wait restart_wireless
        output = self._wait_restart_wireless_output(timeout=180, idle_window=3)
        logging.info(
            "===== restart_wireless output (hidden SSID applied) begin =====\n%s\n===== end =====",
            output,
        )

    def set_wep_mode_dual_band(
            self,
            key_type: str = '64-bit',
            wep_key: Optional[str] = None,
            bands: List[str] = ['2g', '5g']
    ) -> None:
        """
        Configure both 2.4GHz and/or 5GHz Wi-Fi in WEP Shared Key mode.

        Args:
            key_type: '64-bit' or '128-bit'
            wep_key: WEP key (10 hex chars for 64-bit, 26 for 128-bit)
            bands: List of bands to configure, e.g., ['2g'], ['5g'], or ['2g', '5g']
        """
        logging.info(f"🔧 Setting WEP mode ({key_type}) on bands: {bands}")

        # Validate inputs
        crypto_map = {'64-bit': 'wep64', '128-bit': 'wep128'}
        if key_type not in crypto_map:
            raise ValueError(f"Unsupported key type: {key_type}. Use '64-bit' or '128-bit'")

        expected_len = 10 if key_type == '64-bit' else 26
        if wep_key and len(wep_key) != expected_len:
            raise ValueError(f"WEP key must be {expected_len} hex characters for {key_type}")

        # Map bands to nvram prefixes
        band_map = {
            '2g': 'wl0',
            '5g': 'wl1'
        }

        # Apply configuration to selected bands
        for band in bands:
            if band not in band_map:
                logging.warning(f"Skipping unsupported band: {band}")
                continue

            prefix = band_map[band]
            logging.info(f"  → Configuring {band.upper()} ({prefix})")

            self.telnet_write(f'nvram set {prefix}_auth_mode_x=shared;')
            self.telnet_write(f'nvram set {prefix}_wep=enabled;')
            self.telnet_write(f'nvram set {prefix}_crypto={crypto_map[key_type]};')
            if wep_key:
                self.telnet_write(f'nvram set {prefix}_wep_key={wep_key};')

        # Commit and restart wireless
        self.telnet_write('nvram commit;')
        self.telnet_write('service restart_wireless;')

        logging.info("✅ Dual-band WEP configuration completed")

    def set_pmf(self, band: str, mode: str) -> None:
        """
        Set PMF mode for the specified band and immediately commit & apply.
        This function always commits the change and restarts wireless service.
        """
        # --- 参数校验 ---
        band_map = {'2g': 'wl0', '5g': 'wl1'}
        wl_prefix = band_map.get(band.lower())
        if wl_prefix is None:
            raise ConfigError(f"Invalid band: {band}. Use '2g' or '5g'.")

        pmf_map = {
            '0': '0', 'disabled': '0',
            '1': '1', 'optional': '1',
            '2': '2', 'required': '2'
        }
        nvram_value = pmf_map.get(mode.lower())
        if nvram_value is None:
            raise ConfigError(f'Invalid PMF mode: {mode}. Use "disabled", "optional", or "required".')

        nvram_key = f'{wl_prefix}_pmf'
        radio_key = f'{wl_prefix}_radio'

        try:
            self.telnet_write(f'nvram set {nvram_key}={nvram_value}')
            self.telnet_write(f'nvram set {radio_key}=1')
            self.telnet_write('nvram commit')
            self.telnet_write('restart_wireless')

            logging.info(f"PMF for {band} set to '{mode}' and applied successfully.")
        except Exception as e:
            logging.error(f"Failed to set and commit PMF for {band}: {e}")
            raise

        self.telnet.close()
        self._logged_in = False
        time.sleep(10)

    def configure_and_verify_country_code(router, country_code="US",  dut_country_code="US" ):
        """
        配置路由器的国家码 (Country Code)，并验证设置结果。
        如果设置成功，返回当前 AP 在 2.4G 和 5G 频段支持的信道列表。

        Args:
            router: AsusTelnetNvramControl 实例（已连接）。
            country_code (str): 目标国家码，例如 'US', 'CN', 'JP'。

        Returns:
            dict: 包含验证结果和支持信道的字典。
                  {
                      'country_code_set': bool, # 国家码是否成功设置
                      'verified_country_code': str, # 验证后读取的实际国家码
                      '2g_channels': list[int], # 2.4G 支持的信道列表
                      '5g_channels': list[int]  # 5G 支持的信道列表
                  }
        """

        result = {
            'country_code_set': False,
            'verified_country_code': "",
            '2g_channels': [],
            '5g_channels': []
        }

        try:
            host = router.host
            password = str(router.xpath["passwd"])
        except (AttributeError, KeyError) as e:
            logging.error(f"Failed to extract router credentials: {e}")
            return result
        lookup_country = dut_country_code if dut_country_code is not None else country_code
        upper_lookup_cc = lookup_country.upper()

        # === Step 1: 设置国家码 ===
        try:
            # 使用 router 对象的 API 设置国家码
            # router.telnet_write(f"nvram set wl_country_code={country_code}")
            # if country_code == "US":
            #     router.telnet_write(f"nvram set wl0_country_code={country_code}")
            #     router.telnet_write(f"nvram set wl1_country_code={country_code}")
            # router.commit() # nvram commit & restart_wireless
            router.change_country_v2(country_code)
            logging.info(f"Country code set to '{country_code}' via UI setting")
            time.sleep(180) # 等待无线服务完全启动
            router.close_browser()
        except Exception as e:
            logging.error(f"Failed to set country code '{country_code}': {e}")
            return result

        session = None

        try:
            with TelnetVerifier(host=host, password=password) as tv:
                # Verify country code
                # verified_cc = tv.run_command(f"nvram get wl_country_code").strip()
                # verified_cc2 = tv.run_command(f"wl -i eth6 country").strip()
                raw_cc = tv.run_command(f"nvram get wl_country_code")
                verified_cc = re.sub(r'\s+', '', raw_cc)
                raw_cc2 = tv.run_command(f"wl -i eth6 country")

                cc2_match = re.search(r'^([A-Z]{2})', raw_cc2)
                if cc2_match:
                    verified_cc2 = cc2_match.group(1)
                else:
                    verified_cc2 = re.sub(r'\s+', '', raw_cc2.split()[0] if raw_cc2.split() else "")

                logging.info(f"Country code set to  {verified_cc2}")
                expected_driver_code = RouterTools.UI_TO_DRIVER_COUNTRY_MAP.get(country_code, country_code)
                if country_code == 'EU':
                    if verified_cc2 not in ('E0', 'DE'):
                        error_msg = f"EU region expected 'E0' or 'DE', got '{verified_cc2}'"
                        logging.error(error_msg)
                        raise RuntimeError(error_msg)
                elif verified_cc2 != expected_driver_code:
                    error_msg = f"Driver country code mismatch: expected '{expected_driver_code}', got '{verified_cc2}'"
                    logging.error(error_msg)
                    raise RuntimeError(error_msg)

                if verified_cc != country_code:
                    logging.warning(f"NVRAM country code ('{verified_cc}') differs from driver ('{verified_cc2}')")
                result['verified_country_code'] = verified_cc2

                # Wait some minutes to makesure channel list takes affect, Get channel lists
                time.sleep(100)
                if upper_lookup_cc in REGION_CHANNEL_MAP:
                    chan_map = REGION_CHANNEL_MAP[upper_lookup_cc]
                    result['2g_channels'] = chan_map['2g']
                    result['5g_channels'] = chan_map['5g']
                    logging.info(f"✅ Channel lists loaded from data file: 2.4G={result['2g_channels']}")
                else:
                    logging.warning(f"⚠️ Country code {upper_lookup_cc} not found in channel data.")

                result['country_code_set'] = True
                logging.info(f"✅ Country code verified as '{verified_cc2}'. "
                             f"2.4G Channels: {result['2g_channels']}, "
                             f"5G Channels: {result['5g_channels']}")

        except Exception as e:
            logging.error(f"Verification failed: {e}", exc_info=True)
            raise

        return result
