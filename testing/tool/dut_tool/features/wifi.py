from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import re
import time

from tools.logging import smart_log


@dataclass(frozen=True)
class WifiConnectParams:
    ssid: str
    password: str = ""
    security: str = ""
    hidden: bool = False
    lan: bool = True
    timeout_s: int = 90


CMD_CONNECT = "cmd wifi connect-network {} {} {}"
CMD_HIDE = " -h"


def connect(dut, params: WifiConnectParams) -> bool:
    forget(dut)
    command = connect_command(params.ssid, params.password, params.security, params.hidden)
    connect_status = False
    for _ in range(30):
        try:
            dut.run_device_shell(command)
            time.sleep(15)
            if params.lan:
                if not getattr(dut, "ip_target", ""):
                    _ = dut.pc_ip
                target = dut.ip_target
            else:
                target = "."
            ok, _ = dut.wait_ip(cmd=command, target=target, lan=params.lan, timeout_s=params.timeout_s)
            if ok:
                connect_status = True
                break
        except Exception as exc:  # pragma: no cover - hardware dependent
            smart_log(exc, level="info")
            connect_status = False
    return connect_status


def scan(dut, ssid: str, *, attempts: int, scan_wait: int, interval: float) -> bool:
    command = f"cmd wifi start-scan;sleep {scan_wait};cmd wifi list-scan-results"
    for _ in range(attempts):
        info = dut.run_device_shell(command)
        smart_log(info, level="info")
        if ssid in info:
            return True
        time.sleep(interval)
    return False


def forget(dut):
    output = dut.run_device_shell("cmd wifi list-networks")
    if "No networks" in output:
        smart_log("has no wifi connect", level="debug")
        return None

    network_ids = re.findall(r"\n(\d+)\s", output)
    for net_id in network_ids:
        output = dut.run_device_shell(f"cmd wifi forget-network {int(net_id)}")
        if "successful" in output:
            smart_log(f"Network id {net_id} closed", level="info")
    return None


def connect_command(ssid: str, password: str, security: str, hidden: bool) -> str:
    command = CMD_CONNECT.format(ssid, security, password)
    if hidden:
        command += CMD_HIDE
    return command


def check_driver(dut) -> bool:
    dut.clear_logcat()
    file_list = dut.run_device_shell("ls /vendor/lib/modules")
    if "vlsicomm.ko" in file_list:
        smart_log("Wifi driver is exists", level="info")
        return True
    smart_log("Wifi driver is not exists", level="info")
    return False


def get_mcs_rx(dut) -> str:
    try:
        dut.run_device_shell(dut.CLEAR_DMESG_COMMAND)
        dut.run_device_shell(dut.MCS_RX_GET_COMMAND)
        mcs_info = dut.run_device_shell(dut.DMESG_COMMAND)
        smart_log("mcs_rx all result: %s", mcs_info, level="info")
        result = re.findall(r"RX rate info for \w\w:\w\w:\w\w:\w\w:\w\w:\w\w:(.*?)Last received rate", mcs_info, re.S)
        result_list = []
        for line in result[0].split("\n"):
            if ":" in line:
                rate = re.findall(r"(\w+\.?\/?\w+)\s+:\s+\d+\((.*?)\)", line)
                result_list.append(rate[0])
        result_list = [(item[0], float(item[1][:-1].strip())) for item in result_list]
        result_list.sort(key=lambda item: item[1], reverse=True)
        smart_log(result_list, level="info")
        return "|".join(["{}:{}%".format(item[0], item[1]) for item in result_list[:3]])
    except Exception:
        return "mcs_rx"


def get_mcs_tx(dut) -> str:
    try:
        dut.run_device_shell(dut.CLEAR_DMESG_COMMAND)
        dut.run_device_shell(dut.MCS_TX_GET_COMMAND)
        mcs_info = dut.run_device_shell(dut.DMESG_COMMAND)
        smart_log("mcs_tx all result: %s", mcs_info, level="info")
        result = re.findall(
            r"(TX rate info for [\w:]+:\s*\n(?:\s*\[.*?\]\s*\[.*?\]\s*.*\n)+?)"
            r"(?=\s*\[|\s*$)",
            mcs_info,
            re.DOTALL,
        )
        return parse_mcs_distribution_from_blocks(result)
    except Exception:
        return "mcs_tx"


def parse_mcs_distribution_from_blocks(blocks) -> str:
    if not blocks:
        return "MCS_NO_BLOCK"

    last_block_str = blocks[-1]
    lines = last_block_str.strip().split("\n")
    data_lines = []
    for line in lines:
        if "TX rate info" in line or "# type" in line:
            continue
        if line.strip() and re.search(r"\[\d+\s+T\d+", line):
            data_lines.append(line)

    mcs_skipped = defaultdict(int)
    for line in data_lines:
        line = line.strip()
        if not line:
            continue
        match = re.search(r"(MCS\d+).*?\(\s*\d+\s*\)\s+(\d+)(?:\s+[A-Z])?$", line)
        if match:
            mcs = match.group(1)
            skipped = int(match.group(2))
            mcs_skipped[mcs] += skipped

    if not mcs_skipped:
        return "MCS_PARSE_FAIL"

    total_weight = 0.0
    mcs_weights = {}
    for mcs, skipped in mcs_skipped.items():
        weight = 1.0 / (skipped + 1)
        mcs_weights[mcs] = weight
        total_weight += weight

    sorted_mcs = sorted(mcs_weights.items(), key=lambda item: item[1], reverse=True)[:3]
    return "|".join([f"{mcs}:{(weight / total_weight) * 100:.1f}%" for mcs, weight in sorted_mcs])


def get_tx_bitrate(dut) -> str:
    try:
        dut.root()
        result = dut.run_device_shell(dut.IW_LINNK_COMMAND)
        return re.findall(r"tx bitrate:\s+(.*?)\s+MBit\/s", result, re.S)[0]
    except Exception:
        return "Data Error"


def wait_for_service(dut, interface="wlan0", recv="Link encap") -> None:
    count = 0
    while True:
        info = dut.run_device_shell(f"ifconfig {interface}")
        smart_log(info, level="info")
        if recv in info:
            break
        time.sleep(10)
        count += 1
        if count > 10:
            raise EnvironmentError("Lost device")
