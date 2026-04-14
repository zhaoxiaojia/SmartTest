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


class WifiMixin:
    def wifi_connect(
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
        return self._wifi_connect_impl(params)

    def wifi_scan(
        self,
        ssid: str,
        *,
        attempts: int = 10,
        scan_wait: int = 10,
        interval: float = 1,
    ) -> bool:
        return self._wifi_scan_impl(
            ssid,
            attempts=attempts,
            scan_wait=scan_wait,
            interval=interval,
        )

    def wifi_wait_ip(self, cmd: str = "", target=".", lan: bool = True, timeout_s: int = 60):
        return self._wifi_wait_ip_impl(cmd=cmd, target=target, lan=lan, timeout_s=timeout_s)

    def wifi_forget(self):
        return self._wifi_forget_impl()

    def _wifi_connect_impl(self, params: WifiConnectParams) -> bool:
        raise NotImplementedError

    def _wifi_scan_impl(
        self,
        ssid: str,
        *,
        attempts: int,
        scan_wait: int,
        interval: float,
    ) -> bool:
        raise NotImplementedError

    # def _wifi_wait_ip_impl(self, cmd: str, target, lan: bool):
    #     if lan and (not target):
    #         if not self.ip_target:
    #             _ = self.pc_ip
    #         target = self.ip_target
    #
    #     step = 0
    #     while True:
    #         time.sleep(3)
    #         step += 1
    #         info = self.checkoutput("ifconfig wlan0")
    #         ip_address_matches = re.findall(r"inet addr:(\d+\.\d+\.\d+\.\d+)", info, re.S)
    #         if not ip_address_matches:
    #             ip_address_matches = re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", info, re.S)
    #         ip_address = ip_address_matches[0] if ip_address_matches else ""
    #
    #         if target in ip_address:
    #             self.dut_ip = ip_address
    #             break
    #
    #         if step % 3 == 0:
    #             if cmd:
    #                 _ = self.checkoutput(cmd)
    #
    #         if step > 6:
    #             assert False, f"Can't catch the address:{target} "
    #
    #     return True, ip_address

    def _wifi_wait_ip_impl(self, cmd: str, target, lan: bool, timeout_s: int = 60):
        """
        Wait for the DUT to acquire an IP address.

        Args:
            cmd: Command to run periodically during waiting.
            target: The expected IP address or subnet (e.g., "192.168.1.").
            lan: If True, use the cached PC IP as the target.
            timeout_s: Maximum time to wait in seconds. Default is 60.
        """
        if lan and (not target):
            if not self.ip_target:
                _ = self.pc_ip
            target = self.ip_target

        start_time = time.time()
        step = 0
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_s:
                # 获取最后一次的 ifconfig 输出用于诊断
                last_info = self.checkoutput("ifconfig wlan0")
                raise RuntimeError(
                    f"Timeout ({timeout_s}s) waiting for DUT IP. "
                    f"Target: '{target}'. Last ifconfig output:\n{last_info}"
                )

            time.sleep(3)
            step += 1
            info = self.checkoutput("ifconfig wlan0")
            ip_address_matches = re.findall(r"inet addr:(\d+\.\d+\.\d+\.\d+)", info, re.S)
            if not ip_address_matches:
                ip_address_matches = re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", info, re.S)
            ip_address = ip_address_matches[0] if ip_address_matches else ""

            if target in ip_address:
                self.dut_ip = ip_address
                return True, ip_address

            if step % 3 == 0 and cmd:
                _ = self.checkoutput(cmd)

    def _wifi_forget_impl(self):
        raise NotImplementedError
