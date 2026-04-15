from __future__ import annotations

import asyncio
import logging
import time
from threading import Thread

from testing.tool.dut_tool.duts.base import BaseDut
from testing.tool.dut_tool.features.wifi import WifiConnectParams
from testing.tool.dut_tool.transports.telnet_tool import telnet_tool
from testing.tool.dut_tool.transports.telnet_tool import TelnetSession
from testing.tool.dut_tool.transports.serial_tool import SerialShellExecutor
from testing.tool.network_tool.wpa import WpaSupplicantManager


class linux(BaseDut):
    def __init__(self, *, serial=None, telnet=None) -> None:
        super().__init__()
        self.serial = serial
        self.serial_tool = serial
        #self.shell = SerialShellExecutor(serial) if serial is not None else None
        self.shell = None
        self.telnet = telnet
        self.wpa = WpaSupplicantManager(self.shell if self.shell is not None else self.telnet)
        self.dut_ip = ""
        logging.info(f"[LINUX DUT] __init__ called. Received serial={serial}, telnet={telnet}")
        if telnet is not None:
            self.dut_ip = telnet.dut_ip

    def checkoutput(self, cmd, wildcard=""):
        if self.shell is not None:
            self.shell.write(cmd)
            return self.shell.recv()
        return self.telnet.checkoutput(cmd, wildcard=wildcard)

    def wait_reconnect_sync(self, timeout: int = 30, interval: float = 1.0) -> bool:
        return self.telnet.wait_reconnect_sync(timeout=timeout, interval=interval)

    async def telnet_client(self, command):
        return await self.telnet.telnet_client(command)

    def _wifi_connect_impl(self, params: WifiConnectParams) -> bool:
        security = (params.security or "").strip().lower()
        if "open" in security or security in {"none", "open system", ""}:
            auth_type = "open"
            psk = ""
        elif "wpa3" in security or "sae" in security:
            auth_type = "sae"
            psk = params.password
        else:
            auth_type = "psk"
            psk = params.password

        ip = self.wpa.connect(
            params.ssid,
            auth_type=auth_type,
            psk=psk,
            iface="wlan0",
            state_timeout=params.timeout_s,
        )
        if not ip:
            return False
        self.dut_ip = ip
        self.telnet = telnet_tool(self.dut_ip)
        return True

    def _wifi_scan_impl(self, ssid: str, *, attempts: int, scan_wait: int, interval: float) -> bool:
        for _ in range(attempts):
            if self.wpa.scan_has_ssid(ssid, iface="wlan0", scan_wait=scan_wait):
                return True
            time.sleep(interval)
        return False

    def _wifi_forget_impl(self):
        self.wpa.forget(iface="wlan0")
        return None

    def _run_iperf_server_on_device(self, command: str, *, start_background, extend_logs, encoding: str):
        def telnet_iperf():
            logging.info(f"server telnet command: {command}")
            session = TelnetSession(self.dut_ip, port=23)
            try:
                session.open()
                session.write(command.encode("ascii") + b"\n")
                while True:
                    try:
                        chunk = session.read_until(b"\n", timeout=1)
                    except EOFError:
                        break
                    except asyncio.TimeoutError:
                        # No output yet; keep polling without killing the thread.
                        continue
                    except Exception as exc:
                        logging.debug("iperf server telnet read failed: %s", exc)
                        break
                    if not chunk:
                        continue
                    line = chunk.decode(encoding, "ignore").strip()
                    if line:
                        extend_logs(self.iperf_server_log_list, [line], "iperf server telnet:")
            finally:
                try:
                    session.close()
                except Exception:
                    pass

        Thread(target=telnet_iperf, daemon=True).start()
        return None

    def _run_iperf_client_on_device(self, command: str, *, run_blocking, encoding: str):
        logging.info(f"client telnet command: {command}")

        async def _run_telnet_client():
            await asyncio.wait_for(self.telnet_client(command), timeout=self.iperf_wait_time)

        try:
            asyncio.run(_run_telnet_client())
        except asyncio.TimeoutError:
            logging.warning(f"client telnet command timeout after {self.iperf_wait_time}s")
        return None

    def _iperf_client_post_delay_seconds(self) -> int:
        return 5

