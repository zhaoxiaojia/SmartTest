from __future__ import annotations

import time

import time

from testing.tool.dut_tool.duts.android import android
from testing.tool.dut_tool.features.wifi import WifiConnectParams
from testing.tool.network_tool.onn_wpa import onn_wpa


class _AdbShellExecutor:
    def __init__(self, dut: android) -> None:
        self._dut = dut
        self._last_output = ""

    def write(self, command: str, *_args, **_kwargs) -> None:
        safe_command = command.replace('"', '\\"')
        out = self._dut.checkoutput(safe_command) or ""
        err = getattr(self._dut, "_last_command_stderr", "") or ""
        self._last_output = out if not err else (out + "\n" + err).strip()

    def recv(self) -> str:
        return self._last_output

    def wait_for_device(self, timeout: int = 60) -> bool:
        deadline = time.time() + timeout
        serial = self._dut.serialnumber
        while time.time() < deadline:
            result = self._dut.command_runner.run("adb devices", shell=True)
            output = result.stdout or ""
            if f"{serial}\tdevice" in output:
                return True
            time.sleep(3)
        return False


class onn_dut(android):
    def __init__(self, serialnumber: str = "", logdir: str = "") -> None:
        super().__init__(serialnumber=serialnumber, logdir=logdir)
        _ = self.checkoutput("setenforce 0")
        self.wpa = onn_wpa(_AdbShellExecutor(self))

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
        self.dut_ip = ip or ""
        return bool(ip)

    def _wifi_scan_impl(self, ssid: str, *, attempts: int, scan_wait: int, interval: float) -> bool:
        for _ in range(attempts):
            _ = self.wpa._wpa_cli("wlan0", "scan", ctrl_dir="")
            time.sleep(scan_wait)
            out = self.wpa._wpa_cli("wlan0", "scan_results", ctrl_dir="")
            if ssid in out:
                return True
            time.sleep(interval)
        return False

    def _wifi_forget_impl(self):
        self.wpa._forget_all_networks_cli("wlan0")
        return None

