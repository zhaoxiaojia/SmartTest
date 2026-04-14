import logging
import os
import re
import time
import random
import pytest
import threading
from src.util.constants import load_config
from testing.tool.wifi.ixchariot import ix
from testing.tool.connect_tool.command_batch import CommandBatch, CommandRunner, CommandExecutionError, CommandTimeoutError
from testing.tool.connect_tool.mixins.app_mixin import AppMixin
from testing.tool.connect_tool.mixins.dut_mixins import WifiMixin
from testing.tool.connect_tool.mixins.input_mixin import InputMixin
from testing.tool.connect_tool.mixins.perf_mixin import PerfMixin
from testing.tool.connect_tool.mixins.system_mixin import SystemMixin
from testing.tool.connect_tool.mixins.ui_mixin import UiAutomationMixin


class dut(WifiMixin, PerfMixin, SystemMixin, InputMixin, AppMixin, UiAutomationMixin):
    """
    Dut.

    -------------------------
    It runs shell commands on the target device using ADB helpers and captures the output.
    It executes external commands via Python's subprocess module.
    It logs information for debugging or monitoring purposes.
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """
    count = 0
    RealValue_GET_WAIT = 10
    DMESG_COMMAND = 'dmesg -S'
    CLEAR_DMESG_COMMAND = 'dmesg -c'
    DMESG_COMMAND_TAIL = 'dmesg | tail -n 35'

    SETTING_ACTIVITY_TUPLE = 'com.android.tv.settings', '.MainSettings'
    MORE_SETTING_ACTIVITY_TUPLE = 'com.droidlogic.tv.settings', '.more.MorePrefFragmentActivity'

    SKIP_OOBE = "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1"
    IW_LINNK_COMMAND = 'iw dev wlan0 link'
    IX_ENDPOINT_COMMAND = "monkey -p com.ixia.ixchariot 1"
    STOP_IX_ENDPOINT_COMMAND = "am force-stop com.ixia.ixchariot"
    CMD_WIFI_CONNECT = 'cmd wifi connect-network {} {} {}'
    CMD_WIFI_HIDE = ' -h'
    CMD_WIFI_STATUS = 'cmd wifi status'
    CMD_WIFI_START_SAP = 'cmd wifi start-softsap {} {} {} -b {}'
    CMD_WIFI_STOP_SAP = 'cmd wifi stop-softsap'
    CMD_WIFI_LIST_NETWORK = "cmd wifi list-networks |grep -v Network |awk '{print $1}'"
    CMD_WIFI_FORGET_NETWORK = 'cmd wifi forget-network {}'
    CMD_WIFI_BEACON_RSSI= 'iwpriv wlan0 get_bcn_rssi |dmesg | grep "bcn_rssi:"'
    CMD_WIFI_BEACON_RSSI2 = 'iwpriv wlan0 get_rssi |dmesg | grep "rssi:"'

    CMD_PING = 'ping -n {}'
    SVC_WIFI_DISABLE = 'svc wifi disable'
    SVC_WIFI_ENABLE = 'svc wifi enable'

    SVC_BLUETOOTH_DISABLE = 'svc bluetooth disable'
    SVC_BLUETOOTH_ENABLE = 'svc bluetooth enable'

    MCS_RX_GET_COMMAND = 'iwpriv wlan0 get_last_rx'
    MCS_RX_CLEAR_COMMAND = 'iwpriv wlan0 clear_last_rx'
    MCS_TX_GET_COMMAND = 'iwpriv wlan0 get_rate_info'
    MCS_TX_KEEP_GET_COMMAND = "'for i in `seq 1 10`;do iwpriv wlan0 get_rate_info;sleep 6;done ' & "
    POWERRALAY_COMMAND_FORMAT = './tools/powerRelay /dev/tty{} -all {}'

    GET_COUNTRY_CODE = 'iw reg get'
    SET_COUNTRY_CODE_FORMAT = 'iw reg set {}'

    OPEN_INFO = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true"'
    CLOSE_INFO = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="false"'

    PLAYERACTIVITY_REGU = 'am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity -d https://www.youtube.com/watch?v={}'
    VIDEO_TAG_LIST = [
        {'link': 'r_gV5CHOSBM', 'name': '4K Amazon'},  # 4k
        {'link': 'vX2vsvdq8nw', 'name': '4K HDR 60FPS Sniper Will Smith'},  # 4k hrd 60 fps
        {'link': '-ZMVjKT3-5A', 'name': 'NBC News (vp9)'},  # vp9
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR (ULTRA HD) (vp9)'},  # vp9
        {'link': 'b6fzbyPoNXY', 'name': 'Las Vegas Strip at Night in 4k UHD HLG HDR (vp9)'},  # vp9
        {'link': 'AtZrf_TWmSc', 'name': 'How to Convert,Import,and Edit AVCHD Files for Premiere (H264)'},  # H264
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR(ultra hd) (4k 60fps)'},  # 4k 60fps
        {'link': 'NVhmq-pB_cs', 'name': 'Mr Bean 720 25fps (720 25fps)'},
        {'link': 'bcOgjyHb_5Y', 'name': 'paid video'},
        {'link': 'rf7ft8-nUQQ', 'name': 'stress video'}
    ]

    WIFI_BUTTON_TAG = 'Available networks'

    def __init__(self):
        """
        Init.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.serialnumber = 'executer'
        self.rssi_num = -1
        self._freq_num = 0
        self.channel = 0
        cfg = load_config(refresh=True)
        rvr_cfg = cfg.get('rvr', {})
        self.rvr_tool = rvr_cfg.get('tool', 'iperf')
        iperf_cfg = rvr_cfg.get('iperf', {})
        self.iperf_server_cmd = iperf_cfg.get('server_cmd', 'iperf -s -w 2m -i 1')
        self.iperf_client_cmd = iperf_cfg.get('client_cmd', 'iperf -c {ip} -w 2m -i 1 -t 30 -P 5')
        self.iperf_test_time, self.pair = self._parse_iperf_params(self.iperf_client_cmd)
        self.iperf_wait_time = self._calculate_iperf_wait_time(self.iperf_test_time)
        self.repest_times = int(rvr_cfg.get('repeat') or 0)
        self._dut_ip = ''
        self._pc_ip = ''
        self.ip_target = ''
        self.rvr_result = None
        thr_val = rvr_cfg.get('throughput_threshold', 0)
        self.throughput_threshold = float(thr_val if thr_val != '' else 0)
        self.skip_tx = False
        self.skip_rx = False
        self.iperf_server_log_list: list[str] = []
        self._current_udp_mode = False
        encoding = 'gb2312' if getattr(pytest, "win_flag", False) else "utf-8"
        self.command_runner = CommandRunner(encoding=encoding)
        self._extended_rssi_result = None
        self._mcs_tx_result = None
        self._mcs_rx_result = None
        self._rssi_sampled_event = threading.Event()
        if self.rvr_tool == 'iperf':
            cmds = f"{self.iperf_server_cmd} {self.iperf_client_cmd}"
            self.test_tool = 'iperf3' if 'iperf3' in cmds else 'iperf'
            self.tool_path = iperf_cfg.get('path', '')
            self._current_udp_mode = self._is_udp_command(self.iperf_client_cmd) or self._is_udp_command(
                self.iperf_server_cmd
            )
            logging.info(f'test_tool {self.test_tool}')

        if self.rvr_tool == 'ixchariot':
            self.ix = ix()
            ix_cfg = rvr_cfg.get('ixchariot', {})
            self.test_tool = ix_cfg
            self.script_path = ix_cfg.get('path', '')
            logging.info(f'path {self.script_path}')
            logging.info(f'test_tool {self.test_tool}')
            self.ix.modify_tcl_script(
                "set ixchariot_installation_dir ",
                f"set ixchariot_installation_dir \"{self.script_path}\"\n",
            )

    def ping(
        self,
        interface=None,
        hostname="www.baidu.com",
        interval_in_seconds=1,
        ping_time_in_seconds=5,
        timeout_in_seconds=10,
        size_in_bytes=None,
    ):
        """Run an ICMP ping on the DUT side and return True when packet loss is acceptable."""

        if not hostname or not isinstance(hostname, str):
            logging.error("Ping checkpoint missing hostname")
            return False
        interval = max(float(interval_in_seconds or 1), 0.2)
        duration = max(float(ping_time_in_seconds or 1), interval)
        count = max(int(duration / interval), 1)
        timeout = max(int(timeout_in_seconds or 1), 1) + count

        if interface:
            if size_in_bytes:
                cmd = f"ping -i {interval:.2f} -I {interface} -c {count} -s {size_in_bytes} {hostname}"
            else:
                cmd = f"ping -i {interval:.2f} -I {interface} -c {count} {hostname}"
        else:
            if size_in_bytes:
                cmd = f"ping -i {interval:.2f} -c {count} -s {size_in_bytes} {hostname}"
            else:
                cmd = f"ping -i {interval:.2f} -c {count} {hostname}"

        logging.debug("Ping command: %s", cmd)
        try:
            output = self.checkoutput(cmd)
        except Exception as exc:  # pragma: no cover - transports differ per DUT
            logging.error("Ping command failed: %s", exc)
            return False
        if not output:
            return False

        # Inspect tracked return code/stderr to flag remote ping failures.
        last_code = getattr(self, "_last_command_returncode", 0)
        stderr_output = getattr(self, "_last_command_stderr", "")
        if last_code:
            logging.debug("Ping exit code %s stderr: %s", last_code, stderr_output.strip())
            return False

        lowered = output.lower()
        error_lowered = stderr_output.lower()
        if "unknown host" in lowered or "name or service not known" in lowered:
            logging.debug("Ping reported unknown host: %s", hostname)
            return False
        if "unknown host" in error_lowered or "name or service not known" in error_lowered:
            logging.debug("Ping stderr reported unknown host: %s", hostname)
            return False

        loss_match = re.search(r"(\d+)% packet loss", output)
        if loss_match:
            packet_loss = int(loss_match.group(1))
            logging.debug("Ping packet loss = %s%%", packet_loss)
            return packet_loss == 0

        logging.debug("Ping output unparsable:\n%s", output)
        return False

    @property
    def dut_ip(self):
        """
        Dut ip.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._dut_ip == '': self._dut_ip = self.get_dut_ip()
        return self._dut_ip

    @dut_ip.setter
    def dut_ip(self, value):
        """
        Dut ip.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._dut_ip = value

    @property
    def pc_ip(self):
        """
        Pc ip.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._pc_ip == '': self._pc_ip = self.get_pc_ip()
        self.ip_target = '.'.join(self._pc_ip.split('.')[:3])
        return self._pc_ip

    @pc_ip.setter
    def pc_ip(self, value):
        """
        Pc ip.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._pc_ip = value

    @property
    def freq_num(self):
        """
        Freq num.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return self._freq_num

    @freq_num.setter
    def freq_num(self, value):
        """
        Freq num.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._freq_num = int(value)
        self.channel = int((self._freq_num - 2412) / 5 + 1 if self._freq_num < 3000 else (self._freq_num - 5000) / 5)

    def step(func):
        """
        Step.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        func : Any
            The ``func`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        def wrapper(*args, **kwargs):
            """
            Wrapper.

            -------------------------
            It logs information for debugging or monitoring purposes.

            -------------------------
            Returns
            -------------------------
            Any
                The result produced by the function.
            """
            logging.info('-' * 80)
            dut.count += 1
            logging.info(f"Test Step {dut.count}:")
            logging.info(func.__name__)
            info = func(*args, **kwargs)

            logging.info('-' * 80)
            return info

        return wrapper

    def checkoutput_term(self, command):
        """
        Checkoutput term.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        logging.debug(f"command:{command}")
        try:
            result = self.command_runner.run(command, shell=True)
            # Track last host command status for later diagnostics.
            self._last_command_stdout = result.stdout or ""
            self._last_command_stderr = result.stderr or ""
            self._last_command_returncode = result.returncode
            return result.stdout
        except CommandTimeoutError:
            logging.info("Command timed out")
            self._last_command_stdout = ''
            self._last_command_stderr = 'Command timed out'
            self._last_command_returncode = -1
            return None
    @step
    def get_rx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        # 【新增】重置状态并启动后台 RSSI 采样
        self._extended_rssi_result = None
        self._mcs_tx_result = None
        self._mcs_rx_result = None
        self._rssi_sampled_event.clear()
        rssi_thread = threading.Thread(
            target=self._sample_extended_rssi_after_delay,
            args=(10,),
            daemon=True
        )
        rssi_thread.start()
        logging.info(f"[DEBUG] About to call super().get_tx_rate with:")
        logging.info(f"  - router_info: {router_info}")
        logging.info(f"  - type: {type}")
        logging.info(f"  - self.iperf_client_cmd: {getattr(self, 'iperf_client_cmd', 'N/A')}")
        logging.info(f"  - self.dut_ip: {getattr(self, 'dut_ip', 'N/A')}")

        return super().get_rx_rate(
            router_info,
            type=type,
            corner_tool=corner_tool,
            db_set=db_set,
            debug=debug,
        )

    @step
    def get_tx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        # 【新增】重置状态并启动后台 RSSI 采样
        self._extended_rssi_result = None
        self._mcs_tx_result = None
        self._mcs_rx_result = None
        self._rssi_sampled_event.clear()
        rssi_thread = threading.Thread(
            target=self._sample_extended_rssi_after_delay,
            args=(10,),  # 10秒后采样
            daemon=True  # 主线程结束，子线程自动销毁
        )
        rssi_thread.start()
        return super().get_tx_rate(
            router_info,
            type=type,
            corner_tool=corner_tool,
            db_set=db_set,
            debug=debug,
        )

    @step
    def get_rssi(self):
        """
        Retrieve rssi.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._is_performance_debug_enabled():
            simulated_rssi = -random.randint(40, 80)
            self.rssi_num = simulated_rssi
            self.freq_num = 0
            logging.info(
                "Database debug mode enabled, skip real RSSI query and return simulated %s dBm",
                simulated_rssi,
            )
            return self.rssi_num
        for i in range(3):
            time.sleep(3)
            rssi_info = self.checkoutput(self.IW_LINNK_COMMAND)
            logging.info(f'Get WiFi link status via command {rssi_info}')
            if 'signal' in rssi_info:
                break
        else:
            rssi_info = ''

        if 'Not connected' in rssi_info:
            self.rssi_num = -1
            assert False, "Wifi is not connected"
        try:
            self.rssi_num = int(re.findall(r'signal:\s*(-?\d+)\s+dBm', rssi_info, re.S)[0])
            self.freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
        except IndexError as e:
            self.rssi_num = -1
            self.freq_num = -1
        return self.rssi_num

    # --- MCS helpers ----------------------------------------------------

    def get_mcs_tx(self):
        """Return TX MCS/rate info if available for the DUT.

        Template method:
        - Base class owns retry + error handling + return normalization.
        - Subclasses override `_get_mcs_tx_impl()` when the command/path differs
          (e.g. Roku devices that don't support the default iwpriv commands).
        """

        return self._get_mcs_common(direction="tx")

    def get_mcs_rx(self):
        """Return RX MCS info if available for the DUT.

        See `get_mcs_tx()` for the template-method contract.
        """

        return self._get_mcs_common(direction="rx")

    def _get_mcs_common(self, *, direction: str):
        # Keep this tolerant: MCS is auxiliary metadata; throughput should still
        # be recorded even when MCS queries fail.
        impl = self._get_mcs_tx_impl if direction.lower() == "tx" else self._get_mcs_rx_impl
        for attempt in range(1, 4):
            try:
                value = impl()
            except Exception as exc:
                logging.debug("Failed to query MCS (%s) attempt=%d: %s", direction, attempt, exc)
                value = None
            if value is None:
                time.sleep(0.2)
                continue
            text = str(value).strip()
            return text if text else None
        return None

    def _get_mcs_tx_impl(self):
        """DUT-specific TX MCS implementation hook (override in subclasses)."""

        return self.checkoutput(self.MCS_TX_GET_COMMAND)

    def _get_mcs_rx_impl(self):
        """DUT-specific RX MCS implementation hook (override in subclasses)."""

        return self.checkoutput(self.MCS_RX_GET_COMMAND)

    #Get WF0/1 Beacon RSSI
    import re
    import time

    @step
    def get_extended_rssi(self):
        """
        Retrieve beacon RSSI and per-chain RSSI (wf0, wf1) using iwpriv commands.
        Sets:
            self.bcn_rssi   -> int (e.g., -30)
            self.wf0_rssi   -> int (e.g., -27)
            self.wf1_rssi   -> int (e.g., -27)
        Returns:
            tuple: (bcn_rssi, wf0_rssi, wf1_rssi)
        """
        # 初始化默认值（表示未获取到）
        self.bcn_rssi = -1
        self.wf0_rssi = -1
        self.wf1_rssi = -1

        if self._is_performance_debug_enabled():
            # 模拟调试模式
            import random
            self.bcn_rssi = -random.randint(30, 80)
            self.wf0_rssi = self.bcn_rssi + random.randint(0, 3)
            self.wf1_rssi = self.bcn_rssi + random.randint(0, 3)
            logging.info("Debug mode: simulated extended RSSI = bcn:%d, wf0:%d, wf1:%d",
                         self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)
            return (self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)

        try:
            # Step 1: 清除上一次接收记录
            last_rx_info = self.checkoutput("iwpriv clear_last_rx;sleep 1;iwpriv wlan0 get_last_rx")
            logging.info(f"Last RX Info: {last_rx_info}")
            time.sleep(1)

            # Step 2: 获取最后一次接收的 RSSI（可选，按需保留）
            # last_rx_output = self.checkoutput("iwpriv wlan0 get_last_rx")

            # Step 3: 获取 beacon RSSI 并触发 dmesg 输出
            self.checkoutput(self.CLEAR_DMESG_COMMAND)
            dmesg_output = self.checkoutput(self.CMD_WIFI_BEACON_RSSI)
            if not dmesg_output or 'bcn_rssi:' not in dmesg_output:
                dmesg_output = self.checkoutput(self.CMD_WIFI_BEACON_RSSI2)
            logging.info(f"BEACON RSSI Info: {dmesg_output}")

            if not dmesg_output.strip():
                logging.warning("No 'bcn_rssi' found in dmesg output.")
                return (self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)

            # 支持两种日志格式：
            # [76495.945681@3]  [wlan][  IWPRIV] [aml_get_rssi 1957]bcn_rssi: -30 dbm, (wf0: -27 dbm, wf1: -27 dbm)
            # [46487.239822] bcn_rssi: -25 dbm, (wf0: -23 dbm, wf1: -22 dbm)
            pattern = r"bcn_rssi:\s*(-?\d+)\s+dbm.*wf0:\s*(-?\d+)\s+dbm.*wf1:\s*(-?\d+)\s+dbm"

            match = re.search(pattern, dmesg_output, re.IGNORECASE)
            if match:
                self.bcn_rssi = int(match.group(1))
                self.wf0_rssi = int(match.group(2))
                self.wf1_rssi = int(match.group(3))
                logging.info("Extended RSSI parsed: bcn=%d, wf0=%d, wf1=%d",
                             self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)
            else:
                logging.warning("Failed to parse bcn_rssi from dmesg: %s", dmesg_output)

        except Exception as e:
            logging.error("Error in get_extended_rssi: %s", str(e))
            # 保持默认值 -1

        return (self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)

    def _sample_extended_rssi_after_delay(self, delay_seconds: int = 10):
        """
        在指定延迟后采样扩展 RSSI，并存储结果。
        通常由后台线程调用。
        """
        try:
            time.sleep(delay_seconds)
            logging.info(f"📢 Sampling extended RSSI after {delay_seconds}s...")

            #Get Beacon RSSI
            rssi_result = self.get_extended_rssi()
            self._extended_rssi_result = rssi_result
            logging.info(f"✅ Extended RSSI sampled: {rssi_result}")

            #Get realtime MCS
            try:
                # 直接调用方法，不依赖 @step 捕获
                mcs_tx = self.get_mcs_tx()
                self._mcs_tx_result = mcs_tx
                logging.info(f"✅ MCS TX: {mcs_tx}")
            except Exception as e:
                logging.error(f"❌ MCS TX failed: {e}")
                self._mcs_tx_result = "N/A"

            try:
                mcs_rx = self.get_mcs_rx()
                self._mcs_rx_result = mcs_rx
                logging.info(f"✅ MCS RX: {mcs_rx}")
            except Exception as e:
                logging.error(f"❌ MCS RX failed: {e}")
                self._mcs_rx_result = "N/A"

            self._rssi_sampled_event.set()

            #merge RSSI and MCS
            self._extended_sampling_result = {
                'rssi': rssi_result,
                'mcs_tx': mcs_tx,
                'mcs_rx': mcs_rx
            }


            self._rssi_sampled_event.set()

        except Exception as e:
            logging.error(f"❌ Failed to sample extended RSSI: {e}")
            self._extended_rssi_result = ("N/A", "N/A", "N/A")
            self._mcs_tx_result = "N/A"
            self._mcs_rx_result = "N/A"
            self._rssi_sampled_event.set()

    step = staticmethod(step)
