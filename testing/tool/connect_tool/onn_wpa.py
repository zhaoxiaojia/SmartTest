from __future__ import annotations

import logging
import re
import time

from testing.tool.network_tool.wpa import WpaSupplicantManager


class onn_wpa(WpaSupplicantManager):
    def __init__(self, executor) -> None:
        super().__init__(executor, ui_signature="", script_signature="")

    def _wpa_cli(self, iface: str, cmd: str, ctrl_dir: str = "/tmp/wpa_supplicant") -> str:
        _ = ctrl_dir
        self.executor.write(f"wpa_cli -i {iface} {cmd}")
        out = self.executor.recv()
        output = out.strip()
        logging.info("wpa_cli output: %s", output)
        return out

    def kill_by_type(self, proc_type):
        _ = proc_type
        return None

    def restart_ui_wpa(self, proc_type):
        _ = proc_type
        return None

    def get_ip_address(self, iface="wlan0") -> str:
        self.executor.write(f"ifconfig {iface} | grep 'inet '")
        info = self.executor.recv()
        match = re.search(r"inet\\s+(?:addr:)?(\\d+\\.\\d+\\.\\d+\\.\\d+)", info)
        return match.group(1) if match else ""

    def wait_for_state(
        self,
        iface="wlan0",
        target_state="COMPLETED",
        timeout: int = 60,
        *,
        ctrl_dir: str = "/tmp/wpa_supplicant",
        interval_s: int = 5,
    ) -> bool:
        return super().wait_for_state(
            iface=iface,
            target_state=target_state,
            timeout=timeout,
            ctrl_dir="",
            interval_s=interval_s,
        )

    def connect(
        self,
        ssid: str,
        *,
        auth_type: str = "psk",
        psk: str | None = None,
        iface: str = "wlan0",
        dhcp: bool = True,
        state_timeout: int = 60,
        scan_wait: int = 3,
        **_,
    ):
        self._forget_all_networks_cli(iface)

        logging.info("[DBG_ONN_WPA] reboot after forget")
        self.executor.write("reboot")
        time.sleep(5)
        if not self.executor.wait_for_device(timeout=state_timeout):
            raise RuntimeError("ADB device did not come back after reboot")
        time.sleep(20)
        self.executor.write("setenforce 0")
        logging.info(self._wpa_cli(iface, "list_networks", ctrl_dir=""))
        self._wpa_cli(iface, "scan", ctrl_dir="")
        time.sleep(scan_wait)
        self._wpa_cli(iface, "scan_results", ctrl_dir="")

        net_id = self._parse_network_id(self._wpa_cli(iface, "add_network", ctrl_dir=""))
        self._wpa_cli(iface, f"set_network {net_id} ssid '\"{ssid}\"'", ctrl_dir="")

        auth = (auth_type or "").strip().lower()
        if auth in {"open", "none"}:
            self._wpa_cli(iface, f"set_network {net_id} key_mgmt NONE", ctrl_dir="")
        elif auth in {"sae", "wpa3"}:
            self._wpa_cli(iface, f"set_network {net_id} key_mgmt SAE", ctrl_dir="")
            self._wpa_cli(iface, f"set_network {net_id} ieee80211w 2", ctrl_dir="")
            self._wpa_cli(iface, f"set_network {net_id} sae_password '\"{psk or ''}\"'", ctrl_dir="")
        else:
            self._wpa_cli(iface, f"set_network {net_id} psk '\"{psk or ''}\"'", ctrl_dir="")

        self._wpa_cli(iface, f"enable_network {net_id}", ctrl_dir="")
        self._wpa_cli(iface, f"reassociate", ctrl_dir="")
        self._wpa_cli(iface, "save_config", ctrl_dir="")
        if dhcp:
            self.executor.write(f"udhcpc -i {iface} -n -t 20 -T 3")
            udhcpc_out = self.executor.recv()
            logging.info("[DBG_ONN_WPA] udhcpc output:\n%s", udhcpc_out.strip())

        ip = self.status_check(iface=iface)
        logging.info("[DBG_ONN_WPA] status_check ip=%s", ip or "")
        return ip
