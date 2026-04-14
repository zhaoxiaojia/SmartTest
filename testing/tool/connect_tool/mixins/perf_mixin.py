from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import shutil
from testing.tool.connect_tool import command_batch as subprocess
import time
from dataclasses import dataclass
from threading import Thread
from typing import Optional, Sequence

import pytest

from testing.tool.connect_tool.command_batch import (
    CommandBatch,
    CommandExecutionError,
    CommandTimeoutError,
    CommandRunner,
)
from testing.tool.wifi.ixchariot import ix
from testing.tool.wifi.router_tool.router_performance import handle_expectdata
from src.util.constants import is_database_debug_enabled


@dataclass
class IperfMetrics:
    throughput_mbps: Optional[float]
    latency_ms: Optional[float] = None
    packet_loss: Optional[str] = None

    def formatted_throughput(self) -> Optional[str]:
        if self.throughput_mbps is None:
            return None
        return f"{self.throughput_mbps:.1f}"


class PerfMixin:
    IPERF_KILL = "killall -9 {}"
    IPERF_WIN_KILL = "taskkill /im {}.exe -f"

    def _is_performance_debug_enabled(self) -> bool:
        if not is_database_debug_enabled():
            return False
        selected = getattr(pytest, "selected_test_types", set())
        return any(kind in {"RVR", "RVO", "PERFORMANCE"} for kind in selected)

    @staticmethod
    def _parse_iperf_params(cmd: str) -> tuple[int, int]:
        t_match = re.search(r"-t\s+(\d+)", cmd)
        p_match = re.search(r"-P\s+(\d+)", cmd)
        test_time = int(t_match.group(1)) if t_match else 30
        pair = int(p_match.group(1)) if p_match else 1
        return test_time, pair

    @staticmethod
    def _is_udp_command(cmd: str) -> bool:
        return bool(re.search(r"(^|\s)-u(\s|$)", cmd))

    @staticmethod
    def _calculate_iperf_wait_time(test_time: int) -> int:
        safe_time = max(test_time, 1)
        buffer = max(15, min(120, safe_time // 2))
        return safe_time + buffer

    @staticmethod
    def _convert_bandwidth_to_mbps(value: float, unit: str) -> Optional[float]:
        unit = unit.lower()
        if "bits/sec" not in unit:
            return None
        if unit.startswith("g"):
            return value * 1000
        if unit.startswith("m"):
            return value
        if unit.startswith("k"):
            return value / 1000
        if unit.startswith("bits"):
            return value / 1_000_000
        return None

    @staticmethod
    def _sanitize_iperf_line(text: str) -> str:
        if not text:
            return ""
        without_ansi = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", without_ansi)
        return cleaned.strip()

    @staticmethod
    def _extract_udp_metrics(line: str) -> Optional[IperfMetrics]:
        sanitized = PerfMixin._sanitize_iperf_line(line)
        jitter_match = re.search(r"(\d+(?:\.\d+)?)\s*ms", sanitized, re.IGNORECASE)
        loss_match = re.search(r"(\d+\s*/\s*\d+\s*\(\s*\d+(?:\.\d+)?\s*%?\s*\))", sanitized)
        if not jitter_match or not loss_match:
            return None
        bandwidth_match = re.search(r"(\d+(?:\.\d+)?)\s*([KMG]?bits/sec)", sanitized, re.IGNORECASE)
        throughput = None
        if bandwidth_match:
            throughput = PerfMixin._convert_bandwidth_to_mbps(
                float(bandwidth_match.group(1)), bandwidth_match.group(2)
            )
        packet_loss = re.sub(r"\s+", "", loss_match.group(1))
        try:
            jitter = float(jitter_match.group(1))
        except ValueError:
            jitter = None
        return IperfMetrics(throughput, jitter, packet_loss)

    @staticmethod
    def _format_result_row(values):
        def normalize(value: Optional[object]) -> str:
            if value is None:
                return ""
            text = str(value)
            if not text:
                return ""
            if any(ch in text for ch in {",", '"', "\n", "\r"}):
                escaped = text.replace('"', '""')
                return f'"{escaped}"'
            return text

        return ",".join(normalize(value) for value in values)

    def _build_throughput_result_values(
        self,
        router_info,
        corner: str,
        protocol: str,
        direction: str,
        db_set: str,
        mcs_value: Optional[str],
        throughput_values: Sequence[Optional[str]],
        expect_rate,
        bcn_rssi: str,
        wf0_rssi: str,
        wf1_rssi: str,
        latency_value,
        packet_loss_value,
    ):
        def _first_token(text: str) -> str:
            return text.split()[0] if text else text

        values = [
            self.serialnumber,
            "Throughput",
            _first_token(router_info.wireless_mode),
            _first_token(router_info.band),
            _first_token(router_info.bandwidth),
            "Rate_Adaptation",
            router_info.channel,
            corner,
            protocol,
            direction,
            "NULL",
            db_set,
            self.rssi_num,
            mcs_value if mcs_value else "NULL",
        ]
        for entry in throughput_values:
            values.append("" if entry is None else entry)

        values.append(expect_rate)
        values.extend([
            bcn_rssi,
            wf0_rssi,
            wf1_rssi,
        ])
        values.extend([
            latency_value,
            packet_loss_value,
        ])

        return values

    def _normalize_throughput_cells(self, entries: list[str]) -> list[str]:
        total_runs = max(1, int(self.repest_times))
        sanitized = entries[:total_runs]
        while len(sanitized) < total_runs:
            sanitized.append("")
        return [entry if entry is not None else "" for entry in sanitized]

    def kill_iperf(self):
        if self._is_performance_debug_enabled():
            logging.info("Database debug mode enabled, skip killing iperf processes")
            return
        commands: list[str] = []
        commands.append(self.IPERF_WIN_KILL.format(self.test_tool))
        dut_kill_cmd = self.IPERF_KILL.format(self.test_tool)
        logging.info(f"DUT kill iperf command: {dut_kill_cmd}")
        try:
            _ = self.checkoutput(dut_kill_cmd)
        except Exception as e:
            logging.warning(e)
        try:
            self._run_host_commands(commands)
        except Exception as e:
            logging.warning(e)

    def _run_host_commands(self, commands: Sequence[str]) -> None:
        batch = CommandBatch(self.command_runner)
        for cmd in commands:
            batch.add(cmd, shell=True, ignore_error=True)
        try:
            batch.run()
        except CommandExecutionError:
            logging.debug("Host command batch reported an execution error", exc_info=True)
        except CommandTimeoutError:
            logging.debug("Host command batch reported a timeout", exc_info=True)

    def push_iperf(self):
        return None

    def _run_iperf_server_on_device(self, command: str, *, start_background, extend_logs, encoding: str):
        raise NotImplementedError

    def _run_iperf_client_on_device(self, command: str, *, run_blocking, encoding: str):
        raise NotImplementedError

    def _iperf_client_post_delay_seconds(self) -> int:
        return 0

    def run_iperf(self, command, adb):
        encoding = "gbk" if pytest.win_flag else "utf-8"
        use_adb = bool(adb)
        self._current_udp_mode = self._is_udp_command(command)

        def _extend_logs(target_list: list[str], lines, label: str | None = None):
            if not lines:
                return
            if isinstance(lines, str):
                iterable = lines.splitlines()
            else:
                iterable = lines
            for line in iterable:
                if line is None:
                    continue
                text = line.rstrip("\r\n") if isinstance(line, str) else str(line)
                if text:
                    target_list.append(text)
                    if label:
                        logging.info("%s %s", label, text)

        def _read_output(proc, stream, target_list: list[str], label: str):
            if not stream:
                return
            with stream:
                for line in iter(stream.readline, ""):
                    if line:
                        _extend_logs(target_list, [line], label)

        def _start_background(cmd_list, desc):
            process = self.command_runner.popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=encoding,
                errors="ignore",
            )
            Thread(
                target=_read_output,
                args=(process, process.stdout, self.iperf_server_log_list, f"{desc} stdout"),
                daemon=True,
            ).start()
            Thread(
                target=_read_output,
                args=(process, process.stderr, [], f"{desc} stderr"),
                daemon=True,
            ).start()
            return process

        def _run_blocking(cmd_list, desc: str):
            process = self.command_runner.popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=encoding,
                errors="ignore",
            )
            stdout, stderr = process.communicate(timeout=self.iperf_wait_time)
            if stderr:
                logging.warning(stderr.strip())
            if stdout:
                logging.debug(stdout.strip())
            logging.info("%s process return code: %s", desc, process.returncode)

        def _build_cmd_list():
            cmd_parts = command.split()
            if not use_adb and cmd_parts:
                exe = cmd_parts[0]
                if not any(sep in exe for sep in ("/", "\\")):
                    resolved = shutil.which(exe)
                    if not resolved:
                        tool_path = getattr(self, "tool_path", "") or ""
                        if tool_path:
                            candidate = os.path.join(tool_path, exe)
                            if os.name == "nt" and not candidate.lower().endswith(".exe"):
                                candidate_exe = candidate + ".exe"
                                if os.path.isfile(candidate_exe):
                                    candidate = candidate_exe
                            if os.path.isfile(candidate):
                                cmd_parts[0] = candidate
            return cmd_parts

        if "-s" in command:
            self.iperf_server_log_list = []
            if use_adb:
                return self._run_iperf_server_on_device(
                    command,
                    start_background=_start_background,
                    extend_logs=_extend_logs,
                    encoding=encoding,
                )
            return _start_background(_build_cmd_list(), "server pc command:")

        if use_adb:
            return self._run_iperf_client_on_device(
                command,
                run_blocking=_run_blocking,
                encoding=encoding,
            )
        return _run_blocking(_build_cmd_list(), "client pc command:")

    def _parse_iperf_log(self, server_lines: list[str]):
        def _analyse_lines(lines: list[str]) -> tuple[Optional[float], Optional[IperfMetrics], int, bool]:
            interval_pattern = re.compile(r"(\d+(?:\.\d*)?)\s*-\s*(\d+(?:\.\d*)?)\s*sec", re.IGNORECASE)
            interval_throughput: dict[tuple[str, str], dict[str, float]] = {}
            summary_interval_key: Optional[tuple[str, str]] = None
            sum_interval_values: list[float] = []
            udp_metrics_local: Optional[IperfMetrics] = None
            has_summary_line = False

            for raw_line in lines:
                line = PerfMixin._sanitize_iperf_line(raw_line)
                if not line:
                    continue
                if "[SUM]" not in line and self.pair != 1:
                    metrics = self._extract_udp_metrics(line)
                    if metrics:
                        udp_metrics_local = metrics
                        self._current_udp_mode = True
                    continue
                metrics = self._extract_udp_metrics(line)
                if metrics:
                    udp_metrics_local = metrics
                    self._current_udp_mode = True
                interval_match = interval_pattern.search(line)
                if not interval_match:
                    continue
                interval_key = (interval_match.group(1), interval_match.group(2))
                try:
                    start_time = float(interval_match.group(1))
                    end_time = float(interval_match.group(2))
                except (TypeError, ValueError):
                    start_time = end_time = 0.0
                bandwidth_match = re.search(r"(\d+(?:\.\d+)?)\s*([KMG]?bits/sec)", line, re.IGNORECASE)
                if not bandwidth_match:
                    continue
                throughput = self._convert_bandwidth_to_mbps(
                    float(bandwidth_match.group(1)), bandwidth_match.group(2)
                )
                if throughput is None:
                    continue

                lower_line = line.lower()
                role = "none"
                if "receiver" in lower_line:
                    role = "receiver"
                elif "sender" in lower_line:
                    role = "sender"

                role_map = interval_throughput.setdefault(interval_key, {})
                role_map[role] = throughput

                duration = end_time - start_time
                if start_time < 0.5 and duration > 1.5:
                    summary_interval_key = interval_key
                    has_summary_line = True
                elif "[SUM]" in line:
                    sum_interval_values.append(throughput)

            has_receiver = any("receiver" in role_map for role_map in interval_throughput.values())
            values: list[float] = []
            for role_map in interval_throughput.values():
                chosen: Optional[float] = None
                if has_receiver:
                    chosen = role_map.get("receiver") or role_map.get("none")
                else:
                    chosen = role_map.get("none") or role_map.get("sender")
                if chosen is not None:
                    values.append(chosen)

            summary_value: Optional[float] = None
            if summary_interval_key is not None:
                role_map = interval_throughput.get(summary_interval_key, {})
                if has_receiver:
                    summary_value = role_map.get("receiver") or role_map.get("none")
                else:
                    summary_value = role_map.get("none") or role_map.get("sender")

            if summary_value is not None:
                throughput_value = summary_value
            elif sum_interval_values:
                throughput_value = sum(sum_interval_values) / len(sum_interval_values)
            elif values:
                throughput_value = sum(values) / len(values)
            elif udp_metrics_local and udp_metrics_local.throughput_mbps is not None:
                throughput_value = udp_metrics_local.throughput_mbps
            else:
                throughput_value = None

            return throughput_value, udp_metrics_local, len(values), has_summary_line

        server_value, server_udp_metrics, server_count, server_has_summary = _analyse_lines(server_lines)

        preferred_value = server_value
        preferred_udp = server_udp_metrics

        line_count = server_count
        expected_intervals_raw = getattr(self, "iperf_test_time", 0) or 0
        expected_intervals = int(expected_intervals_raw) if expected_intervals_raw else 0
        if not server_has_summary:
            if line_count:
                if expected_intervals and line_count < expected_intervals:
                    logging.warning(
                        "iperf output only produced %d intervals (expected %d)",
                        line_count,
                        expected_intervals,
                    )
            else:
                logging.warning("iperf output did not contain interval lines")
        throughput_result = preferred_value if preferred_value is not None else None

        if preferred_udp:
            preferred_udp.throughput_mbps = throughput_result
            return preferred_udp

        return IperfMetrics(throughput_result)

    def get_logcat(self):
        expected_intervals_raw = getattr(self, "iperf_test_time", 0) or 0
        expected_intervals = int(expected_intervals_raw) if expected_intervals_raw else 0
        if expected_intervals:
            interval_pattern = re.compile(r"(\d+(?:\.\d*)?)\s*-\s*(\d+(?:\.\d*)?)\s*sec", re.IGNORECASE)
            wait_deadline = time.time() + min(5.0, max(1.0, expected_intervals * 0.1))
            has_summary = False
            while time.time() < wait_deadline:
                snapshot = list(self.iperf_server_log_list)
                sum_intervals: set[tuple[str, str]] = set()
                for text in snapshot:
                    sanitized = PerfMixin._sanitize_iperf_line(text)
                    if not sanitized:
                        continue
                    match = interval_pattern.search(sanitized)
                    if not match:
                        continue
                    start, end = match.group(1), match.group(2)
                    if "[SUM]" not in sanitized:
                        continue
                    sum_intervals.add((start, end))
                    if not has_summary:
                        try:
                            start_f = float(start)
                            end_f = float(end)
                        except (TypeError, ValueError):
                            continue
                        if end_f - start_f >= max(1.0, expected_intervals - 1):
                            has_summary = True
                current_sum_count = len(sum_intervals)
                if has_summary:
                    break
                if expected_intervals and current_sum_count >= expected_intervals:
                    break
                time.sleep(0.1)
        server_lines = list(self.iperf_server_log_list)
        if not server_lines:
            logging.warning("iperf server log list is empty; no data captured")
        result = self._parse_iperf_log(server_lines)
        self.iperf_server_log_list.clear()
        if result is None:
            return None
        if result.throughput_mbps is not None:
            result.throughput_mbps = round(result.throughput_mbps, 1)
        if result.latency_ms is not None:
            result.latency_ms = round(result.latency_ms, 3)
        return result

    def get_pc_ip(self):
        if pytest.win_flag:
            ipconfig_info = self.checkoutput_term("ipconfig").strip()
            pc_ip = re.findall(r"IPv4.*?(\d+\.\d+\.\d+\.\d+)", ipconfig_info, re.S)[0]
        else:
            ifconfig_info = self.checkoutput_term("ifconfig")
            pc_ip = re.findall(r"inet\s+(\d+\.\d+\.\d+\.\d+)", ifconfig_info, re.S)[0]
        if not pc_ip:
            assert False, "Can't get pc ip"
        return pc_ip

    def get_dut_ip(self):
        dut_info = self.checkoutput("ifconfig wlan0")
        dut_ip_matches = re.findall(r"inet addr:(\d+\.\d+\.\d+\.\d+)", dut_info, re.S)
        if not dut_ip_matches:
            dut_ip_matches = re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", dut_info, re.S)
        dut_ip = dut_ip_matches[0] if dut_ip_matches else ""
        if not dut_ip:
            assert False, "Can't get dut ip"
        return dut_ip

    def get_rx_rate(self, router_info, type="TCP", corner_tool=None, db_set="", debug=False):
        router_cfg = {
            router_info.band: {
                "mode": router_info.wireless_mode,
                "security_mode": router_info.security_mode,
                "bandwidth": router_info.bandwidth,
            }
        }
        chip_info = getattr(pytest, "chip_info", None)
        expect_rate = handle_expectdata(router_cfg, router_info.band, "DL", chip_info)
        for attr in ('bcn_rssi', 'wf0_rssi', 'wf1_rssi'):
            if not hasattr(self, attr):
                setattr(self, attr, "")

        if self.skip_rx:
            corner = corner_tool.get_turntanle_current_angle() if corner_tool else ""
            throughput_cells = self._normalize_throughput_cells(["0"])
            values = self._build_throughput_result_values(
                router_info,
                corner,
                type,
                "DL",
                db_set,
                None,
                throughput_cells,
                expect_rate,
                getattr(self, 'bcn_rssi', ""),
                getattr(self, 'wf0_rssi', ""),
                getattr(self, 'wf1_rssi', ""),
                None,
                None,
            )
            return ",".join([cell for cell in throughput_cells if cell]) or "0"

        rx_metrics_list: list[IperfMetrics] = []
        self.rvr_result = None
        mcs_rx = None

        database_debug = self._is_performance_debug_enabled()
        debug_enabled = debug or database_debug
        if debug_enabled:
            simulated = round(random.uniform(100, 200), 2)
            rx_metrics_list.append(IperfMetrics(simulated))
            mcs_rx = "DEBUG"
        else:
            desired_runs = max(1, int(self.repest_times))
            for _attempt in range(desired_runs + 2):
                rx_result = 0
                mcs_rx = 0
                try:
                    if self.rvr_tool in ("iperf", "iperf3"):
                        self.kill_iperf()
                        terminal = self.run_iperf(self.tool_path + self.iperf_server_cmd, self.serialnumber)
                        time.sleep(1)
                        client_cmd = self.iperf_client_cmd.replace("{ip}", self.dut_ip)
                        self.run_iperf(client_cmd, "")
                        delay = self._iperf_client_post_delay_seconds()
                        if delay:
                            time.sleep(delay)
                        rx_result = self.get_logcat()
                        self.rvr_result = None
                        if terminal:
                            terminal.terminate()
                    elif self.rvr_tool == "ixchariot":
                        ix.ep1 = self.pc_ip
                        ix.ep2 = self.dut_ip
                        ix.pair = self.pair
                        rx_result = ix.run_rvr()
                except subprocess.TimeoutExpired:
                    logging.warning("iperf RX timed out; record 0 and continue retry")
                    rx_result = None

                if rx_result is False:
                    if self.rvr_tool == "ixchariot":
                        self.checkoutput(self.STOP_IX_ENDPOINT_COMMAND)
                        time.sleep(1)
                        self.checkoutput(self.IX_ENDPOINT_COMMAND)
                        time.sleep(3)
                    continue

                time.sleep(3)
                if isinstance(rx_result, IperfMetrics):
                    metrics = rx_result
                else:
                    try:
                        throughput = float(rx_result) if rx_result is not None else None
                    except Exception:
                        throughput = None
                    metrics = IperfMetrics(throughput)
                if not rx_metrics_list and metrics.throughput_mbps is None:
                    continue
                mcs_rx = self.get_mcs_rx()
                rx_metrics_list.append(metrics)
                if len(rx_metrics_list) >= desired_runs:
                    break

        if rx_metrics_list:
            first = rx_metrics_list[0].throughput_mbps
            rx_val = float(first) if first is not None else 0
            if rx_val < self.throughput_threshold:
                self.skip_rx = True

        throughput_entries: list[str] = []
        for metric in rx_metrics_list:
            formatted = metric.formatted_throughput()
            if formatted is not None:
                throughput_entries.append(formatted)
        throughput_cells = self._normalize_throughput_cells(throughput_entries)
        if not throughput_entries:
            throughput_cells = ["0"] * len(throughput_cells)
        latency_value = rx_metrics_list[-1].latency_ms if rx_metrics_list else None
        packet_loss_value = rx_metrics_list[-1].packet_loss if rx_metrics_list else None
        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ""
        values = self._build_throughput_result_values(
            router_info,
            corner,
            type,
            "DL",
            db_set,
            mcs_rx,
            throughput_cells,
            expect_rate,
            getattr(self, 'bcn_rssi', ""),
            getattr(self, 'wf0_rssi', ""),
            getattr(self, 'wf1_rssi', ""),
            latency_value,
            packet_loss_value,
        )
        formatted = self._format_result_row(values)
        return ",".join([cell for cell in throughput_cells if cell]) or "0"

    def get_tx_rate(self, router_info, type="TCP", corner_tool=None, db_set="", debug=False):
        router_cfg = {
            router_info.band: {
                "mode": router_info.wireless_mode,
                "security_mode": router_info.security_mode,
                "bandwidth": router_info.bandwidth,
            }
        }
        chip_info = getattr(pytest, "chip_info", None)
        expect_rate = handle_expectdata(router_cfg, router_info.band, "UL", chip_info)
        for attr in ('bcn_rssi', 'wf0_rssi', 'wf1_rssi'):
            if not hasattr(self, attr):
                setattr(self, attr, "")

        if self.skip_tx:
            corner = corner_tool.get_turntanle_current_angle() if corner_tool else ""
            throughput_cells = self._normalize_throughput_cells(["0"])
            values = self._build_throughput_result_values(
                router_info,
                corner,
                type,
                "UL",
                db_set,
                None,
                throughput_cells,
                expect_rate,
                getattr(self, 'bcn_rssi', ""),
                getattr(self, 'wf0_rssi', ""),
                getattr(self, 'wf1_rssi', ""),
                None,
                None,
            )
            return ",".join([cell for cell in throughput_cells if cell]) or "0"

        tx_metrics_list: list[IperfMetrics] = []
        self.rvr_result = None
        mcs_tx = None

        database_debug = self._is_performance_debug_enabled()
        debug_enabled = debug or database_debug
        if debug_enabled:
            simulated = round(random.uniform(100, 200), 2)
            tx_metrics_list.append(IperfMetrics(simulated))
            mcs_tx = "DEBUG"
        else:
            desired_runs = max(1, int(self.repest_times))
            for _attempt in range(desired_runs + 2):
                tx_result = 0
                mcs_tx = 0
                try:
                    if self.rvr_tool in ("iperf", "iperf3"):
                        self.kill_iperf()
                        time.sleep(1)
                        terminal = self.run_iperf(self.iperf_server_cmd, "")
                        time.sleep(1)
                        client_cmd = self.iperf_client_cmd.replace("{ip}", self.pc_ip)
                        self.run_iperf(self.tool_path + client_cmd, self.serialnumber)
                        delay = self._iperf_client_post_delay_seconds()
                        if delay:
                            time.sleep(delay)
                        time.sleep(3)
                        tx_result = self.get_logcat()
                        self.rvr_result = None
                        if terminal:
                            terminal.terminate()
                    elif self.rvr_tool == "ixchariot":
                        ix.ep1 = self.dut_ip
                        ix.ep2 = self.pc_ip
                        ix.pair = self.pair
                        tx_result = ix.run_rvr()
                except subprocess.TimeoutExpired:
                    logging.warning("iperf TX timed out; record 0 and continue retry")
                    tx_result = None

                if tx_result is False:
                    if self.rvr_tool == "ixchariot":
                        self.checkoutput(self.STOP_IX_ENDPOINT_COMMAND)
                        time.sleep(1)
                        self.checkoutput(self.IX_ENDPOINT_COMMAND)
                        time.sleep(3)
                    continue

                mcs_tx = self.get_mcs_tx()
                if isinstance(tx_result, IperfMetrics):
                    metrics = tx_result
                else:
                    try:
                        throughput = float(tx_result) if tx_result is not None else None
                    except Exception:
                        throughput = None
                    metrics = IperfMetrics(throughput)
                if not tx_metrics_list and metrics.throughput_mbps is None:
                    continue
                tx_metrics_list.append(metrics)
                if len(tx_metrics_list) >= desired_runs:
                    break

        if tx_metrics_list:
            first = tx_metrics_list[0].throughput_mbps
            tx_val = float(first) if first is not None else 0
            if tx_val < self.throughput_threshold:
                self.skip_tx = True

        throughput_entries: list[str] = []
        for metric in tx_metrics_list:
            formatted = metric.formatted_throughput()
            if formatted is not None:
                throughput_entries.append(formatted)
        throughput_cells = self._normalize_throughput_cells(throughput_entries)
        if not throughput_entries:
            throughput_cells = ["0"] * len(throughput_cells)
        latency_value = tx_metrics_list[-1].latency_ms if tx_metrics_list else None
        packet_loss_value = tx_metrics_list[-1].packet_loss if tx_metrics_list else None
        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ""
        values = self._build_throughput_result_values(
            router_info,
            corner,
            type,
            "UL",
            db_set,
            mcs_tx,
            throughput_cells,
            expect_rate,
            getattr(self, 'bcn_rssi', ""),
            getattr(self, 'wf0_rssi', ""),
            getattr(self, 'wf1_rssi', ""),
            latency_value,
            packet_loss_value,
        )
        formatted = self._format_result_row(values)
        return ",".join([cell for cell in throughput_cells if cell]) or "0"
