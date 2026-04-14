#!/usr/bin/env python
# encoding: utf-8
'''
@author: Yonghua.Yan
@contact: Yonghua.Yan@amlogic.com
@software: pycharm
@file: linux_control.py
@time: 2025/12/18 18:58
@desc: This file includes functions to control liunx host: ssh_connect, tcpdump capture, etc.
'''

import paramiko
import time
import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple, Union
from logging import FileHandler
from datetime import datetime


class HtmlFileHandler(FileHandler):
    """Custom HTML log handler to output logs in HTML format"""

    def __init__(self, filename: str, mode: str = 'a', encoding: Optional[str] = None, delay: bool = False):
        super().__init__(filename, mode, encoding, delay)
        self._write_html_header()

    def _write_html_header(self) -> None:
        """Write HTML file header (only when file is empty)"""
        if os.path.getsize(self.baseFilename) == 0:
            html_header = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Linux Control Tool Logs</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .log-container {{ max-width: 1200px; margin: 0 auto; background-color: #f9f9f9; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .log-header {{ text-align: center; margin-bottom: 30px; padding-bottom: 10px; border-bottom: 2px solid #eee; }}
        .log-title {{ color: #333; margin: 0; }}
        .log-time {{ color: #666; font-size: 0.9em; }}
        .log-entry {{ margin: 8px 0; padding: 8px 12px; border-radius: 4px; }}
        .INFO {{ background-color: #e3f2fd; border-left: 4px solid #2196f3; }}
        .WARNING {{ background-color: #fff8e1; border-left: 4px solid #ffc107; }}
        .ERROR {{ background-color: #ffebee; border-left: 4px solid #f44336; }}
        .DEBUG {{ background-color: #e8f5e9; border-left: 4px solid #4caf50; }}
        .log-level {{ font-weight: bold; margin-right: 10px; }}
        .log-message {{ display: inline; }}
        .log-footer {{ text-align: center; margin-top: 30px; padding-top: 10px; border-top: 2px solid #eee; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="log-container">
        <div class="log-header">
            <h1 class="log-title">Linux Control Tool Logs</h1>
            <div class="log-time">Log Creation Time: {}</div>
        </div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.stream.write(html_header)

    def emit(self, record):
        """Process log records and convert to HTML format"""
        try:
            msg = self.format(record)
            level = record.levelname
            log_time = record.asctime
            html_entry = f'        <div class="log-entry {level}">\n'
            html_entry += f'            <span class="log-level">{level}</span>\n'
            html_entry += f'            <span class="log-time">{log_time}</span>\n'
            msg_html = msg.replace("\n", "<br>")
            html_entry += f'            <div class="log-message">{msg_html}</div>\n'
            html_entry += '        </div>\n'
            self.stream.write(html_entry)
            self.flush()
        except Exception:
            self.handleError(record)


class LinuxController:
    """Linux remote control tool class providing SSH connection, command execution and packet capture functions"""

    def __init__(
            self,
            remote_host: str,
            remote_user: str,
            remote_pass: str,
            sudo_pass: str = "",
            remote_capture_file: str = "/tmp/remote_capture.pcap",
            local_save_path: str = "./local_capture.pcap",
            filter_rule: str = "",
            ssh_port: int = 22,
            transferred_capture_filename: str = "transferred_capture.pcap",
            target_band: Optional[str] = None,
            target_channel: Optional[int] = None
    ):
        """Initialize Linux controller configuration parameters"""
        # Connection configuration
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.remote_pass = remote_pass
        self.sudo_pass = sudo_pass
        self.ssh_port = ssh_port

        # Packet capture configuration
        self.remote_capture_file = Path(remote_capture_file).as_posix()
        self.local_save_path = local_save_path
        self.filter_rule = filter_rule
        self.transferred_capture_filename = Path(transferred_capture_filename).name

        # Wireless capture parameters - 移除了target_ssid参数
        self.target_band = target_band  # Should be '2.4ghz' or '5ghz'
        self.target_channel = target_channel

        # Status variables
        self.ssh: Optional[paramiko.SSHClient] = None
        self.wifi_iface: Optional[str] = None
        self.is_capturing: bool = False

        # Initialize logger
        self.logger = self._init_logger()

    def _init_logger(self) -> logging.Logger:
        """Initialize logging system (console, text, HTML multi-output)"""
        logger_name = f"linux_control_{self.remote_host}"
        logger = logging.getLogger(logger_name)

        if logger.handlers:  # Avoid adding handlers repeatedly
            return logger

        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        html_formatter = logging.Formatter("%(message)s")

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        # Text file handler
        txt_file_handler = FileHandler(
            f"linux_control_{self.remote_host}.log",
            mode='w',
            encoding="utf-8"
        )
        txt_file_handler.setFormatter(formatter)

        # HTML file handler
        html_file_handler = HtmlFileHandler(
            f"linux_control_{self.remote_host}.html",
            mode='w',
            encoding="utf-8"
        )
        html_file_handler.setFormatter(html_formatter)

        logger.addHandler(console_handler)
        logger.addHandler(txt_file_handler)
        logger.addHandler(html_file_handler)

        return logger

    def create_ssh_client(self) -> bool:
        """Create SSH client connection"""
        if self.ssh is not None:
            self.logger.warning("SSH connection already exists, no need to recreate")
            return True

        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=self.remote_host,
                port=self.ssh_port,
                username=self.remote_user,
                password=self.remote_pass,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            self.logger.info(f"Successfully established SSH connection -> {self.remote_host}:{self.ssh_port}")
            return True
        except paramiko.AuthenticationException:
            self.logger.error("SSH authentication failed, please check username and password")
        except paramiko.SSHException as e:
            self.logger.error(f"SSH protocol error: {str(e)}")
        except Exception as e:
            self.logger.error(f"SSH connection failed: {str(e)}")
        self.ssh = None
        return False

    def close_ssh_client(self) -> None:
        """Close SSH connection"""
        if self.ssh:
            try:
                self.ssh.close()
                self.logger.info("SSH connection closed")
            except Exception as e:
                self.logger.warning(f"Error closing SSH connection: {str(e)}")
            finally:
                self.ssh = None

    def run_remote_command(
            self,
            command: str,
            ignore_non_zero: bool = False,
            timeout: int = 30
    ) -> Tuple[bool, str]:
        """Execute remote command (with timeout control and error handling)"""
        if not self.ssh:
            self.logger.error("No SSH connection established, cannot execute command")
            return False, "SSH connection not established"

        # Build command with sudo
        final_cmd = f"printf '{self.sudo_pass}\\n' | sudo -S {command}" if self.sudo_pass else f"sudo {command}"

        try:
            stdin, stdout, stderr = self.ssh.exec_command(final_cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace").strip()
            error = stderr.read().decode("utf-8", errors="replace").strip()

            if exit_code != 0:
                if ignore_non_zero:
                    self.logger.warning(f"Command returned non-zero status (ignored): {final_cmd},提示: {error}")
                    return True, output
                self.logger.error(f"Command execution failed: {final_cmd}, error: {error}")
                return False, error

            self.logger.debug(f"Command executed successfully: {final_cmd}, output: {output}")
            return True, output
        except paramiko.SSHException as e:
            self.logger.error(f"SSH command execution error: {final_cmd}, reason: {str(e)}")
            return False, str(e)
        except Exception as e:
            self.logger.error(f"Command execution exception: {final_cmd}, exception: {str(e)}")
            return False, str(e)

    def get_remote_wifi_interface(self) -> Optional[str]:
        """Automatically identify WiFi network card name of remote host"""
        if not self.ssh:
            self.logger.error("No SSH connection established, cannot get network interface information")
            return None

        # Prefer iw dev to identify WiFi interface
        cmd = "iw dev | grep -o 'Interface [a-zA-Z0-9]*' | awk '{print $2}'"
        success, output = self.run_remote_command(cmd, ignore_non_zero=True, timeout=10)

        if success and output:
            interfaces = [iface.strip() for iface in output.splitlines() if iface.strip()]
            if interfaces:
                self.wifi_iface = interfaces[0]
                self.logger.info(f"Automatically identified WiFi interface: {self.wifi_iface}")
                return self.wifi_iface


        self.logger.error("No valid WiFi interface found, please check wireless network card configuration")
        self.wifi_iface = None
        return None

    def _configure_wifi_channel(self) -> bool:
        """Configure WiFi channel based on target_band and target_channel"""
        if not self.wifi_iface:
            self.logger.error("No WiFi interface available for channel configuration")
            return False

        if not self.target_channel:
            self.logger.warning("No target channel specified, using current channel")
            return True

        # Validate channel based on band
        if self.target_band == "2.4ghz" and not (1 <= self.target_channel <= 14):
            self.logger.error(f"Invalid 2.4GHz channel: {self.target_channel} (must be 1-14)")
            return False

        if self.target_band == "5ghz" and not (36 <= self.target_channel <= 165):
            self.logger.error(f"Invalid 5GHz channel: {self.target_channel} (typically 36-165)")
            return False

        # Set wireless channel
        cmd = f"iwconfig {self.wifi_iface} channel {self.target_channel}"
        success, output = self.run_remote_command(cmd, timeout=10)
        if success:
            self.logger.info(f"Successfully set channel to {self.target_channel} on {self.wifi_iface}")
            return True

        self.logger.error(f"Failed to set channel {self.target_channel}: {output}")
        return False

    def start_remote_capture(self) -> bool:
        """Start remote WiFi packet capture with Band and Channel configuration"""
        if not self.ssh:
            self.logger.error("No SSH connection established, cannot start packet capture")
            return False

        # If capturing, stop first
        if self.is_capturing:
            self.logger.warning("Packet capture is already running, will stop existing process first")
            self.stop_remote_capture()
            time.sleep(2)

        # Get WiFi interface
        if not self.get_remote_wifi_interface():
            return False

        # Prepare monitoring environment
        prepare_cmds = [
            ("pkill -9 tcpdump", True),  # Clean up residual processes
            ("airmon-ng check kill >/dev/null 2>&1", True),  # Silently close interfering processes
            (f"ip link set {self.wifi_iface} down", False),
            (f"airmon-ng start {self.wifi_iface} >/dev/null 2>&1", False)
        ]

        for cmd, ignore_error in prepare_cmds:
            self.logger.debug(f"Executing preparation command: {cmd}")
            success, output = self.run_remote_command(cmd, ignore_non_zero=ignore_error, timeout=15)
            if not success:
                self.logger.error(f"Packet capture preparation failed: {cmd}, output: {output}")
                return False

        # Configure channel if specified
        if not self._configure_wifi_channel():
            return False

        # Wait for interface mode switch and channel configuration
        time.sleep(3)

        # Build filter expression using only user filter (移除了SSID过滤相关代码)
        filter_part = f"-f '{self.filter_rule}'" if self.filter_rule else ""

        # Start packet capture process
        capture_cmd = (
            f"nohup tcpdump -i {self.wifi_iface} -w {self.remote_capture_file} "
            f"{filter_part} -U >/dev/null 2>&1 &"
        )
        self.logger.debug(f"Starting capture command: {capture_cmd}")
        success, _ = self.run_remote_command(capture_cmd, timeout=10)

        # Verify capture process
        if success:
            time.sleep(2)  # Wait for process initialization
            check_cmd = f"pgrep -f 'tcpdump -i {self.wifi_iface}'"
            check_success, pid = self.run_remote_command(check_cmd, ignore_non_zero=True, timeout=5)

            if check_success and pid.strip():
                capture_info = [
                    f"Interface: {self.wifi_iface}",
                    f"Save path: {self.remote_capture_file}",
                    f"PID: {pid.strip()}"
                ]
                if self.target_band:
                    capture_info.append(f"Band: {self.target_band}")
                if self.target_channel:
                    capture_info.append(f"Channel: {self.target_channel}")

                self.is_capturing = True
                self.logger.info(f"Remote packet capture started -> {', '.join(capture_info)}")
                return True
            self.logger.error("No running tcpdump detected after starting capture process")
            return False

        self.logger.error("Failed to start tcpdump packet capture")
        return False

    def stop_remote_capture(self) -> None:
        """Stop remote packet capture and restore network card to normal mode"""
        if not self.ssh:
            self.logger.warning("No SSH connection established, cannot stop packet capture")
            return

        if not self.is_capturing:
            self.logger.warning("No running packet capture task")
            return

        # Restore network interface
        stop_cmds = []
        if self.wifi_iface:
            stop_cmds = [
                ("pkill tcpdump", True),
                (f"airmon-ng stop {self.wifi_iface} >/dev/null 2>&1", False),
                ("systemctl restart NetworkManager", False)
            ]
        else:
            stop_cmds = [("pkill tcpdump", True)]

        for cmd, ignore_error in stop_cmds:
            self.run_remote_command(cmd, ignore_non_zero=ignore_error, timeout=15)

        self.is_capturing = False
        status_msg = f"Restored interface: {self.wifi_iface}" if self.wifi_iface else ""
        self.logger.info(f"Remote packet capture stopped -> {status_msg}")

    def download_capture_file(self, use_transferred_name: bool = False) -> bool:
        """Download remote packet capture file to local"""
        if not self.ssh:
            self.logger.error("No SSH connection established, cannot download file")
            return False

        try:
            sftp = self.ssh.open_sftp()

            # Check remote file
            try:
                remote_stat = sftp.stat(self.remote_capture_file)
                if remote_stat.st_size == 0:
                    self.logger.error(f"Remote capture file is empty: {self.remote_capture_file}")
                    sftp.close()
                    return False
            except FileNotFoundError:
                self.logger.error(f"Remote capture file does not exist: {self.remote_capture_file}")
                sftp.close()
                return False

            # Determine local save path
            if use_transferred_name:
                local_dir = os.path.dirname(self.local_save_path)
                save_path = os.path.join(local_dir,
                                         self.transferred_capture_filename) if local_dir else self.transferred_capture_filename
            else:
                save_path = self.local_save_path

            # Ensure local directory exists
            Path(os.path.dirname(save_path)).mkdir(parents=True, exist_ok=True)

            # Download file
            sftp.get(self.remote_capture_file, save_path)
            sftp.close()

            # Verify local file
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                file_size = os.path.getsize(save_path) / 1024
                self.logger.info(
                    f"Capture file downloaded successfully -> Local path: {save_path}, "
                    f"Size: {file_size:.2f}KB"
                )
                return True

            self.logger.error("Local file download failed (file is empty or does not exist)")
            return False

        except Exception as e:
            self.logger.error(f"SFTP download failed: {str(e)}")
            return False

    def rename_remote_capture_file(self) -> bool:
        """Rename remote packet capture file"""
        if not self.ssh:
            self.logger.error("No SSH connection established, cannot rename file")
            return False

        remote_dir = Path(self.remote_capture_file).parent.as_posix()
        new_remote_path = f"{remote_dir}/{self.transferred_capture_filename}"
        cmd = f"mv {self.remote_capture_file} {new_remote_path}"
        success, output = self.run_remote_command(cmd, timeout=10)

        # Verify renaming result
        if success:
            try:
                sftp = self.ssh.open_sftp()
                sftp.stat(new_remote_path)
                sftp.close()
                self.remote_capture_file = new_remote_path
                self.logger.info(f"Remote capture file renamed to: {new_remote_path}")
                return True
            except FileNotFoundError:
                self.logger.error(f"Renamed file does not exist: {new_remote_path}")
        else:
            self.logger.error(f"Failed to rename remote file: {output}")
        return False

    def clean_remote_files(self) -> None:
        """Clean up packet capture temporary files on remote host"""
        if self.ssh:
            remote_dir = Path(self.remote_capture_file).parent.as_posix()
            cleanup_cmd = (
                f"rm -f {self.remote_capture_file} "
                f"{os.path.join(remote_dir, self.transferred_capture_filename)}"
            )
            self.run_remote_command(
                cleanup_cmd,
                ignore_non_zero=True,
                timeout=10
            )
            self.logger.info(f"Cleaned up remote temporary files: {self.transferred_capture_filename}")
        else:
            self.logger.warning("No SSH connection established, cannot clean up remote files")

    def __del__(self) -> None:
        """Destructor: Ensure resource release"""
        if self.is_capturing:
            self.stop_remote_capture()
        self.close_ssh_client()


# # Example usage
# if __name__ == "__main__":
#     config = {
#         "remote_host": "192.168.50.18",
#         "remote_user": "dell",
#         "remote_pass": "123456",
#         "sudo_pass": "123456",
#         "local_save_path": "./local_capture.pcap",
#         "transferred_capture_filename": "tcid111.pcap",
#         "target_band": "2.4ghz",  # 无线频段参数
#         "target_channel": 9  # 信道参数
#     }
#
#     controller = LinuxController(** config)
#     try:
#         if not controller.create_ssh_client():
#             raise Exception("Failed to establish SSH connection, exiting program")
#
#         if not controller.start_remote_capture():
#             raise Exception("Failed to start packet capture, exiting program")
#
#         capture_duration = 60
#         print(f"Starting packet capture, will last {capture_duration} seconds...")
#         time.sleep(capture_duration)
#
#         controller.stop_remote_capture()
#
#         if not controller.rename_remote_capture_file():
#             raise Exception("Failed to rename remote file")
#
#         if not controller.download_capture_file(use_transferred_name=True):
#             raise Exception("Failed to download capture file")
#
#         controller.clean_remote_files()
#
#     except Exception as e:
#         print(f"Program error: {str(e)}")
#     finally:
#         controller.close_ssh_client()
