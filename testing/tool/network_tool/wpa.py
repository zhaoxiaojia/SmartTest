"""
WPA helpers.

This module hosts the core wpa_supplicant control logic. Product/platform
wrappers should delegate to this module rather than duplicating the same
control flows.
"""

from __future__ import annotations

import logging
import re
import time


class WpaSupplicantManager:
    def __init__(self, executor, ui_signature: str | None = None, script_signature: str | None = None) -> None:
        self.executor = executor
        self.ui_signature = ui_signature or "/etc/wpa-supp.conf"
        self.script_signature = script_signature or "/tmp/wpa_supplicant.conf"
        self.process_list: list[dict[str, str]] = []

    def refresh_process_list(self):
        self.process_list.clear()
        self.executor.write("ps -A -o pid,args | grep 'wpa_supplicant'")
        ps_out = self.executor.recv()
        for line in ps_out.splitlines():
            line = line.strip()
            if not line or "grep" in line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            pid, cmdline = parts
            if self.ui_signature and self.ui_signature in cmdline:
                proc_type = "ui"
            elif self.script_signature and self.script_signature in cmdline:
                proc_type = "script"
            else:
                proc_type = "unknown"
            self.process_list.append({"pid": pid, "cmdline": cmdline, "type": proc_type})

    def kill_by_type(self, proc_type):
        self.refresh_process_list()
        killed = []
        for proc in self.process_list:
            if proc["type"] != proc_type:
                continue
            self.executor.write(f"kill {proc['pid']}")
            killed.append(proc)
            logging.info("[KILL] %s: PID=%s CMD=%s", proc_type, proc["pid"], proc["cmdline"])
            time.sleep(0.5)
        if not killed:
            logging.info("No %s wpa_supplicant to kill", proc_type)

    def restart_ui_wpa(self, proc_type):
        self.kill_by_type("script")
        for proc in self.process_list:
            if proc["type"] != proc_type:
                continue
            cmd = proc["cmdline"]
            self.executor.write(cmd + " &")
            logging.info("[RESTART] %s: %s", proc_type, cmd)
            time.sleep(1)

    def restart_interface(self, iface="wlan0"):
        self.executor.write(f"ip link set {iface} down")
        time.sleep(0.5)
        self.executor.write(f"ip link set {iface} up")
        time.sleep(1)

    def make_ctrl_dir(self, path="/tmp/wpa_supplicant"):
        self.executor.write(f"mkdir -p {path}")
        time.sleep(0.2)

    def _wpa_cli(self, iface: str, cmd: str, ctrl_dir: str = "/tmp/wpa_supplicant") -> str:
        self.executor.write(f"wpa_cli -p {ctrl_dir} -i {iface} {cmd}")
        return self.executor.recv()

    @staticmethod
    def _sh_single_quote(value: str) -> str:
        return "'" + value.replace("'", "'\\''") + "'"

    def create_network_block(
        self,
        ssid: str,
        auth_type: str = "psk",
        psk: str | None = None,
        eap: str | None = None,
        identity: str | None = None,
        password: str | None = None,
        key_mgmt: str | None = None,
        proto: str | None = None,
        ieee80211w: int | None = None,
        pairwise: str | None = None,
        group: str | None = None,
        pmf: int | None = None,
        priority: int | None = None,
    ) -> str:
        lines: list[str] = ["network={", f'    ssid="{ssid}"']
        auth = (auth_type or "").lower()
        if auth in {"open", "none"}:
            lines.append("    key_mgmt=NONE")
        elif auth in {"psk", "wpa-psk", "wpa2-psk"}:
            lines.append(f'    psk="{psk or ""}"')
        elif auth in {"sae", "wpa3"}:
            lines.append("    key_mgmt=SAE")
            lines.append(f'    psk="{psk or ""}"')
        elif auth in {"eap", "wpa-eap", "enterprise"}:
            lines.append("    key_mgmt=WPA-EAP")
            if eap:
                lines.append(f"    eap={eap}")
            if identity:
                lines.append(f'    identity="{identity}"')
            if password:
                lines.append(f'    password="{password}"')

        if key_mgmt:
            lines.append(f"    key_mgmt={key_mgmt}")
        if proto:
            lines.append(f"    proto={proto}")
        if ieee80211w is not None:
            lines.append(f"    ieee80211w={ieee80211w}")
        if pairwise:
            lines.append(f"    pairwise={pairwise}")
        if group:
            lines.append(f"    group={group}")
        if pmf is not None:
            lines.append(f"    pmf={pmf}")
        if priority is not None:
            lines.append(f"    priority={priority}")
        lines.append("}")
        return "\n".join(lines)

    def create_conf(
        self,
        ssid: str,
        auth_type: str = "psk",
        psk: str | None = None,
        eap: str | None = None,
        identity: str | None = None,
        password: str | None = None,
        key_mgmt: str | None = None,
        proto: str | None = None,
        ieee80211w: int | None = None,
        pairwise: str | None = None,
        group: str | None = None,
        pmf: int | None = None,
        priority: int | None = None,
        *,
        ap_scan: int = 1,
        ctrl_interface: str = "/tmp/wpa_supplicant",
        ctrl_interface_group: int = 0,
        conf_path: str = "/tmp/wpa_supplicant.conf",
    ) -> str:
        network_block = self.create_network_block(
            ssid,
            auth_type=auth_type,
            psk=psk,
            eap=eap,
            identity=identity,
            password=password,
            key_mgmt=key_mgmt,
            proto=proto,
            ieee80211w=ieee80211w,
            pairwise=pairwise,
            group=group,
            pmf=pmf,
            priority=priority,
        )
        wpa_conf = (
            f"ap_scan={ap_scan}\n"
            f"ctrl_interface={ctrl_interface}\n"
            f"ctrl_interface_group={ctrl_interface_group}\n"
            f"{network_block}\n"
        )
        lines = wpa_conf.splitlines()
        if not lines:
            self.executor.write(f"rm -f {conf_path}")
            time.sleep(0.2)
            return conf_path

        self.executor.write(f"rm -f {conf_path}")
        time.sleep(0.1)
        self.executor.write(f"echo {self._sh_single_quote(lines[0])} > {conf_path}")
        time.sleep(0.05)
        for line in lines[1:]:
            self.executor.write(f"echo {self._sh_single_quote(line)} >> {conf_path}")
            time.sleep(0.05)
        time.sleep(0.2)
        return conf_path

    def start_wpa_supplicant(self, iface="wlan0", conf="/tmp/wpa_supplicant.conf", debug: bool = False):
        log_flag = "-dd" if debug else ""
        self.executor.write(f"wpa_supplicant -B -i {iface} -c {conf} {log_flag}".strip())
        time.sleep(1)

    def wait_for_state(
        self,
        iface="wlan0",
        target_state="COMPLETED",
        timeout: int = 60,
        *,
        ctrl_dir: str = "/tmp/wpa_supplicant",
        interval_s: int = 5,
    ) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self._wpa_cli(iface, "status", ctrl_dir=ctrl_dir)
            if status and f"wpa_state={target_state}" in status:
                return True
            time.sleep(interval_s)
        return False

    def run_udhcpc(self, iface="wlan0"):
        self.executor.write(f"udhcpc -i {iface} -n -q")
        time.sleep(3)

    def get_ip_address(self, iface="wlan0") -> str:
        self.executor.write(f"ifconfig {iface} | grep 'inet '")
        info = self.executor.recv()
        match = re.search(r"inet\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)", info)
        return match.group(1) if match else ""

    def status_check(self, iface="wlan0"):
        ip = self.get_ip_address(iface=iface)
        return ip or None

    @staticmethod
    def _parse_network_id(output: str) -> str:
        normalized = (
            output.replace("/r/n", "\n")
            .replace("/n", "\n")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )
        match = re.search(r"CTRL-EVENT-NETWORK-ADDED\s+(\d+)", normalized)
        if match:
            return match.group(1)
        for line in normalized.splitlines():
            token = line.strip()
            if token.isdigit():
                return token
        match = re.search(r"\b(\d+)\b", normalized)
        if match:
            return match.group(1)
        raise ValueError("Failed to parse wpa_cli network id")

    def _forget_all_networks_cli(self, iface: str) -> None:
        _ = self._wpa_cli(iface, "disconnect", ctrl_dir="")
        out = self._wpa_cli(iface, "remove_network all", ctrl_dir="")
        logging.info(self._wpa_cli(iface, "list_networks", ctrl_dir=""))
        self._wpa_cli(iface, "save_config", ctrl_dir="")


    def _connect_via_cli(
        self,
        ssid: str,
        *,
        auth_type: str,
        psk: str | None,
        iface: str,
        dhcp: bool,
        state_timeout: int,
        scan_wait: int,
    ):
        self._forget_all_networks_cli(iface)
        _ = self._wpa_cli(iface, "scan", ctrl_dir="")
        time.sleep(scan_wait)
        _ = self._wpa_cli(iface, "scan_results", ctrl_dir="")

        net_id = self._parse_network_id(self._wpa_cli(iface, "add_network", ctrl_dir=""))
        _ = self._wpa_cli(iface, f"set_network {net_id} ssid '\"{ssid}\"'", ctrl_dir="")

        auth = (auth_type or "").strip().lower()
        if auth in {"open", "none"}:
            _ = self._wpa_cli(iface, f"set_network {net_id} key_mgmt NONE", ctrl_dir="")
        elif auth in {"sae", "wpa3"}:
            _ = self._wpa_cli(iface, f"set_network {net_id} key_mgmt SAE", ctrl_dir="")
            _ = self._wpa_cli(iface, f"set_network {net_id} ieee80211w 2", ctrl_dir="")
            _ = self._wpa_cli(iface, f"set_network {net_id} sae_password '\"{psk or ''}\"'", ctrl_dir="")
        else:
            _ = self._wpa_cli(iface, f"set_network {net_id} psk '\"{psk or ''}\"'", ctrl_dir="")

        _ = self._wpa_cli(iface, f"enable_network {net_id}", ctrl_dir="")
        status_out = self._wpa_cli(iface, "status", ctrl_dir="")
        logging.info("[DBG_ONN_WPA] status after enable:\n%s", status_out.strip())
        list_out = self._wpa_cli(iface, "list_networks", ctrl_dir="")
        logging.info("[DBG_ONN_WPA] list_networks:\n%s", list_out.strip())
        # _ = self._wpa_cli(iface, "reassociate", ctrl_dir="")
        # ok = self.wait_for_state(iface=iface, target_state="COMPLETED", timeout=state_timeout, ctrl_dir="")
        # if not ok:
        #     return None
        _ = self._wpa_cli(iface, "save_config", ctrl_dir="")
        if dhcp:
            self.executor.write(f"udhcpc -i {iface} -n -t 20 -T 3")
            udhcpc_out = self.executor.recv()
            logging.info("[DBG_ONN_WPA] udhcpc output:\n%s", udhcpc_out.strip())

        ip = self.status_check(iface=iface)
        logging.info("[DBG_ONN_WPA] status_check ip=%s", ip or "")
        return ip

    def _connect_via_conf(
        self,
        ssid: str,
        *,
        auth_type: str,
        psk: str | None,
        eap: str | None,
        identity: str | None,
        password: str | None,
        key_mgmt: str | None,
        proto: str | None,
        ieee80211w: int | None,
        pairwise: str | None,
        group: str | None,
        pmf: int | None,
        priority: int | None,
        iface: str,
        dhcp: bool,
        wait_connect: int,
        max_retry: int,
        retry_interval: int,
        state_timeout: int,
    ):
        for attempt in range(1, max_retry + 1):
            logging.info("Attempt %d to connect %s", attempt, ssid)
            try:
                self.kill_by_type("ui")
                self.kill_by_type("unknown")
                ctrl_dir = "/tmp/wpa_supplicant"
                self.make_ctrl_dir(ctrl_dir)
                conf_path = self.create_conf(
                    ssid,
                    auth_type,
                    psk,
                    eap,
                    identity,
                    password,
                    key_mgmt,
                    proto,
                    ieee80211w,
                    pairwise,
                    group,
                    pmf,
                    priority,
                    ctrl_interface=ctrl_dir,
                )

                self.executor.write(f"test -s {conf_path} && echo OK || echo FAIL")
                verify_out = self.executor.recv().strip()
                if "OK" not in verify_out:
                    logging.error(
                        "wpa conf write failed: %s (verify=%s)",
                        conf_path,
                        verify_out,
                    )
                    continue

                self.start_wpa_supplicant(iface=iface, debug=False)
                time.sleep(wait_connect)
                reconn_out = self._wpa_cli(iface, "reconnect", ctrl_dir=ctrl_dir).strip()
                status_out = self._wpa_cli(iface, "status", ctrl_dir=ctrl_dir).strip()
                if reconn_out:
                    logging.info("wpa_cli reconnect: %s", reconn_out)
                if status_out:
                    logging.info("wpa_cli status: %s", status_out.replace("\n", " | "))
                ok = self.wait_for_state(
                    iface=iface,
                    target_state="COMPLETED",
                    timeout=state_timeout,
                    ctrl_dir=ctrl_dir,
                )
                if ok:
                    if dhcp:
                        self.run_udhcpc(iface=iface)
                    logging.info("Attempt %d connection succeeded", attempt)
                    time.sleep(3)
                    self.restart_ui_wpa("ui")
                    return self.status_check(iface=iface)
                status_out = self._wpa_cli(iface, "status", ctrl_dir=ctrl_dir).strip()
                if status_out:
                    logging.info("wpa_cli status (timeout): %s", status_out.replace("\n", " | "))
                logging.warning(
                    "Attempt %d connection failed, retrying in %d seconds...",
                    attempt,
                    retry_interval,
                )
                time.sleep(retry_interval)
                self.kill_by_type("script")
            except Exception as exc:
                logging.error("Attempt %d raised error: %s", attempt, exc)
                time.sleep(retry_interval)
        logging.error("Connection to %s failed after multiple attempts", ssid)
        time.sleep(3)
        self.restart_ui_wpa("ui")
        return None

    def scan_has_ssid(
        self,
        ssid: str,
        *,
        iface: str = "wlan0",
        scan_wait: int = 3,
        ctrl_dir: str = "/tmp/wpa_supplicant",
    ) -> bool:
        _ = self._wpa_cli(iface, "scan", ctrl_dir=ctrl_dir)
        time.sleep(scan_wait)
        out = self._wpa_cli(iface, "scan_results", ctrl_dir=ctrl_dir)
        return ssid in out

    def forget(self, iface: str = "wlan0", ctrl_dir: str = "/tmp/wpa_supplicant") -> None:
        _ = self._wpa_cli(iface, "disconnect", ctrl_dir=ctrl_dir)
        self.kill_by_type("script")
        self.restart_ui_wpa("ui")

    def connect(
        self,
        ssid: str,
        *,
        mode: str = "supplicant",
        auth_type: str = "psk",
        psk: str | None = None,
        eap: str | None = None,
        identity: str | None = None,
        password: str | None = None,
        key_mgmt: str | None = None,
        proto: str | None = None,
        ieee80211w: int | None = None,
        pairwise: str | None = None,
        group: str | None = None,
        pmf: int | None = None,
        priority: int | None = None,
        iface: str = "wlan0",
        dhcp: bool = True,
        wait_connect: int = 5,
        max_retry: int = 3,
        retry_interval: int = 5,
        state_timeout: int = 60,
        scan_wait: int = 3,
    ):
        if mode == "cli":
            return self._connect_via_cli(
                ssid,
                auth_type=auth_type,
                psk=psk,
                iface=iface,
                dhcp=dhcp,
                state_timeout=state_timeout,
                scan_wait=scan_wait,
            )

        return self._connect_via_conf(
            ssid,
            auth_type=auth_type,
            psk=psk,
            eap=eap,
            identity=identity,
            password=password,
            key_mgmt=key_mgmt,
            proto=proto,
            ieee80211w=ieee80211w,
            pairwise=pairwise,
            group=group,
            pmf=pmf,
            priority=priority,
            iface=iface,
            dhcp=dhcp,
            wait_connect=wait_connect,
            max_retry=max_retry,
            retry_interval=retry_interval,
            state_timeout=state_timeout,
        )
