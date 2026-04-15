from __future__ import annotations

from dataclasses import dataclass
import re
import time


@dataclass(frozen=True)
class WifiConnectParams:
    ssid: str
    password: str = ""
    security: str = ""
    hidden: bool = False
    lan: bool = True
    timeout_s: int = 90


class WifiFeature:
    def __init__(self, dut) -> None:
        self.dut = dut

    def connect(
        self,
        ssid: str,
        password: str = "",
        security: str = "",
        hidden: bool = False,
        lan: bool = True,
        *,
        timeout_s: int = 90,
    ) -> bool:
        params = WifiConnectParams(
            ssid=ssid,
            password=password,
            security=security,
            hidden=hidden,
            lan=lan,
            timeout_s=timeout_s,
        )
        return self.dut._wifi_connect_impl(params)

    def scan(
        self,
        ssid: str,
        *,
        attempts: int = 10,
        scan_wait: int = 10,
        interval: float = 1,
    ) -> bool:
        return self.dut._wifi_scan_impl(
            ssid,
            attempts=attempts,
            scan_wait=scan_wait,
            interval=interval,
        )

    def wait_ip(self, cmd: str = "", target=".", lan: bool = True, timeout_s: int = 60):
        return self._wait_ip_impl(cmd=cmd, target=target, lan=lan, timeout_s=timeout_s)

    def forget(self):
        return self.dut._wifi_forget_impl()

    def _wait_ip_impl(self, cmd: str, target, lan: bool, timeout_s: int = 60):
        if lan and (not target):
            if not self.dut.ip_target:
                _ = self.dut.pc_ip
            target = self.dut.ip_target

        start_time = time.time()
        step = 0
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_s:
                last_info = self.dut.run_device_shell("ifconfig wlan0")
                raise RuntimeError(
                    f"Timeout ({timeout_s}s) waiting for DUT IP. "
                    f"Target: '{target}'. Last ifconfig output:\n{last_info}"
                )

            time.sleep(3)
            step += 1
            info = self.dut.run_device_shell("ifconfig wlan0")
            ip_address_matches = re.findall(r"inet addr:(\d+\.\d+\.\d+\.\d+)", info, re.S)
            if not ip_address_matches:
                ip_address_matches = re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", info, re.S)
            ip_address = ip_address_matches[0] if ip_address_matches else ""

            if target in ip_address:
                self.dut.dut_ip = ip_address
                return True, ip_address

            if step % 3 == 0 and cmd:
                _ = self.dut.run_device_shell(cmd)
