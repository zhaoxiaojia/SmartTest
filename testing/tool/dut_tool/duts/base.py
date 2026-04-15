import logging
import os
import re
import time
import random
import pytest
import threading
from src.util.constants import load_config
from testing.tool.dut_tool.features.device_ui import DeviceUiFeature
from testing.tool.dut_tool.features.iperf import IperfFeature
from testing.tool.dut_tool.features.online_playback import OnlinePlaybackFeature
from testing.tool.dut_tool.features.settings import SettingsFeature
from testing.tool.dut_tool.features.stability import StabilityFeature
from testing.tool.dut_tool.features.wifi import WifiFeature
from testing.tool.dut_tool.features.youtube import YoutubeFeature
from testing.tool.wifi_lab_tool.ixchariot import ix
from testing.tool.dut_tool.command_batch import CommandBatch, CommandRunner, CommandExecutionError, CommandTimeoutError


class BaseDut:
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
    CMCC_MOBILE_SETTINGS_COMPONENT = "com.cmcc.jarvis/.setting.SettingActivity"
    ANDROID_TV_SETTINGS_COMPONENT = "com.android.tv.settings/.MainSettings"
    DROIDLOGIC_MORE_SETTINGS_COMPONENT = "com.droidlogic.tv.settings/.more.MorePrefFragmentActivity"
    MOBILE_TERMS_KEEP_WLAN_TAPS = ((860, 580), (900, 650))
    EXOPLAYER_DEMO_COMPONENT = "com.droidlogic.exoplayer2.demo/com.droidlogic.videoplayer.MoviePlayer"
    DEFAULT_EXOPLAYER_DEMO_VIDEO_URL = "http://192.168.8.221/bbb_sunflower_2160p_60fps_normal.mp4"
    STABILITY_APK_DOWNLOAD_URL = "http://10.28.11.79:8881/#/Public_IPTV/chao.lu/apk/an14/"
    STABILITY_APK_PACKAGES = (
        "com.droidlogic.autoreboot",
        "com.droidlogic.autoshutdown",
        "com.farcore.AutoSuspend",
    )
    DISABLE_REMOTE_CONTROL_COMMAND = "echo 0x02 > /sys/class/remote0/amremote0/protocol"
    ENABLE_BLUETOOTH_HCI_LOGGING_COMMANDS = (
        "device_config put bluetooth INIT_logging_debug_enabled_for_all true",
        "setprop persist.bluetooth.btsnoopenable true",
        "setprop persist.bluetooth.btsnooplogmode full",
        "setprop persist.bluetooth.btsnoopsize 0x7ffffff",
        "setprop persist.bluetooth.btsnoopsize 1048576000",
        "setprop persist.bluetooth.btsnooppath /data/misc/bluetooth/logs/btsnoop_hci.log",
    )
    CONNECTED_BLUETOOTH_MAC_COMMAND = (
        'dumpsys bluetooth_manager | grep -B1 "Connected: true" | '
        'grep "Peer:" | awk \'{print $2}\''
    )

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
        self.iperf = IperfFeature(self)
        self.iperf_test_time, self.pair = self.iperf._parse_iperf_params(self.iperf_client_cmd)
        self.iperf_wait_time = self.iperf._calculate_iperf_wait_time(self.iperf_test_time)
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
        self.ui = DeviceUiFeature(self)
        self.wifi = WifiFeature(self)
        self.settings = SettingsFeature(self)
        self.online_playback = OnlinePlaybackFeature(self)
        self.youtube = YoutubeFeature(self)
        self.stability = StabilityFeature(self)
        if self.rvr_tool == 'iperf':
            cmds = f"{self.iperf_server_cmd} {self.iperf_client_cmd}"
            self.test_tool = 'iperf3' if 'iperf3' in cmds else 'iperf'
            self.tool_path = iperf_cfg.get('path', '')
            self._current_udp_mode = self.iperf._is_udp_command(self.iperf_client_cmd) or self.iperf._is_udp_command(
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

    def __getattr__(self, name: str):
        ui = self.__dict__.get("ui")
        if ui is not None:
            try:
                return object.__getattribute__(ui, name)
            except AttributeError:
                pass
        raise AttributeError(f"{self.__class__.__name__!s} object has no attribute {name!r}")

    # Capability methods owned by DUT.

    def keyevent(self, keycode):
        return self._keyevent_impl(keycode)

    def _keyevent_impl(self, keycode):
        raise NotImplementedError

    def home(self):
        return self._home_impl()

    def _home_impl(self):
        raise NotImplementedError

    def back(self):
        return self._back_impl()

    def _back_impl(self):
        raise NotImplementedError

    def app_switch(self):
        return self._app_switch_impl()

    def _app_switch_impl(self):
        raise NotImplementedError

    def tap(self, x, y):
        return self._tap_impl(x, y)

    def _tap_impl(self, x, y):
        raise NotImplementedError

    def swipe(self, x_start, y_start, x_end, y_end, duration):
        return self._swipe_impl(x_start, y_start, x_end, y_end, duration)

    def _swipe_impl(self, x_start, y_start, x_end, y_end, duration):
        raise NotImplementedError

    def text(self, text):
        return self._text_impl(text)

    def _text_impl(self, text):
        raise NotImplementedError

    def start_activity(self, packageName, activityName, intentname=""):
        return self._start_activity_impl(packageName, activityName, intentname=intentname)

    def _start_activity_impl(self, packageName, activityName, *, intentname=""):
        raise NotImplementedError

    def app_stop(self, app_name):
        return self._app_stop_impl(app_name)

    def _app_stop_impl(self, app_name):
        raise NotImplementedError

    def reboot(self):
        return self._reboot_impl()

    def _reboot_impl(self):
        self.checkoutput("reboot")
        return None

    def expand_logcat_capacity(self):
        return self._expand_logcat_capacity_impl()

    def _expand_logcat_capacity_impl(self):
        raise NotImplementedError

    def clear_logcat(self):
        return self._clear_logcat_impl()

    def _clear_logcat_impl(self):
        raise NotImplementedError

    def save_logcat(self, filepath, tag=""):
        return self._save_logcat_impl(filepath, tag=tag)

    def _save_logcat_impl(self, filepath, *, tag=""):
        raise NotImplementedError

    def stop_save_logcat(self, log, filepath):
        return self._stop_save_logcat_impl(log, filepath)

    def _stop_save_logcat_impl(self, log, filepath):
        raise NotImplementedError

    def filter_logcat_pid(self):
        return self._filter_logcat_pid_impl()

    def _filter_logcat_pid_impl(self):
        raise NotImplementedError

    def kill_logcat_pid(self):
        return self._kill_logcat_pid_impl()

    def _kill_logcat_pid_impl(self):
        raise NotImplementedError

    def dmesg(self):
        return self.checkoutput(self.DMESG_COMMAND)

    def clear_dmesg(self):
        return self.checkoutput(self.CLEAR_DMESG_COMMAND)

    def wifi_enable(self):
        return self.checkoutput(self.SVC_WIFI_ENABLE)

    def wifi_disable(self):
        return self.checkoutput(self.SVC_WIFI_DISABLE)

    def bluetooth_enable(self):
        return self.checkoutput(self.SVC_BLUETOOTH_ENABLE)

    def bluetooth_disable(self):
        return self.checkoutput(self.SVC_BLUETOOTH_DISABLE)

    def get_country_code(self):
        return self.checkoutput(self.GET_COUNTRY_CODE)

    def set_country_code(self, country_code: str):
        return self.checkoutput(self.SET_COUNTRY_CODE_FORMAT.format(country_code))

    # Feature compatibility shims.
    # These keep the old flat DUT API alive while new code migrates to
    # dut.ui / dut.wifi / dut.iperf / dut.settings / dut.online_playback / dut.youtube / dut.stability composition.

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
        return self.wifi.connect(
            ssid=ssid,
            password=password,
            security=security,
            hidden=hidden,
            lan=lan,
            timeout_s=timeout_s,
        )

    def wifi_scan(
        self,
        ssid: str,
        *,
        attempts: int = 10,
        scan_wait: int = 10,
        interval: float = 1,
    ) -> bool:
        return self.wifi.scan(
            ssid,
            attempts=attempts,
            scan_wait=scan_wait,
            interval=interval,
        )

    def wifi_wait_ip(self, cmd: str = "", target=".", lan: bool = True, timeout_s: int = 60):
        return self.wifi.wait_ip(cmd=cmd, target=target, lan=lan, timeout_s=timeout_s)

    def wifi_forget(self):
        return self.wifi.forget()

    def _is_performance_debug_enabled(self) -> bool:
        return self.iperf._is_performance_debug_enabled()

    def kill_iperf(self):
        return self.iperf.kill_iperf()

    def push_iperf(self):
        return self.iperf.push_iperf()

    def run_iperf(self, command, adb):
        return self.iperf.run_iperf(command, adb)

    def get_logcat(self):
        return self.iperf.get_logcat()

    def get_pc_ip(self):
        return self.iperf.get_pc_ip()

    def get_dut_ip(self):
        return self.iperf.get_dut_ip()

    def accept_mobile_terms_keep_wlan_enabled(self):
        return self.settings.accept_mobile_terms_keep_wlan_enabled()

    def open_mobile_settings(self):
        return self.settings.open_mobile_settings()

    def open_android_tv_settings(self):
        return self.settings.open_android_tv_settings()

    def open_more_settings(self):
        return self.settings.open_more_settings()

    def play_exoplayer_demo_video(self, url: str = ""):
        return self.online_playback.play_exoplayer_demo_video(url=url)

    def playback_youtube(self, sleep_time=60, seek=False, seek_time=3, video_id: str = ""):
        return self.youtube.playback(
            sleep_time=sleep_time,
            seek=seek,
            seek_time=seek_time,
            video_id=video_id,
        )

    def get_stability_apk_download_url(self) -> str:
        return self.stability.get_stability_apk_download_url()

    def list_stability_apk_packages(self) -> list[str]:
        return self.stability.list_stability_apk_packages()

    def disable_remote_control(self):
        return self.stability.disable_remote_control()

    def enable_bluetooth_hci_logging(self) -> list[str]:
        return self.stability.enable_bluetooth_hci_logging()

    def get_connected_bluetooth_mac_addresses(self) -> list[str]:
        return self.stability.get_connected_bluetooth_mac_addresses()

    def run_device_shell(self, command: str):
        return self.checkoutput(command)

    def run_host_shell(self, command: str):
        return self.checkoutput_term(command)

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
            owner_cls = args[0].__class__ if args else BaseDut
            owner_cls.count += 1
            logging.info(f"Test Step {owner_cls.count}:")
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
        # 銆愭柊澧炪€戦噸缃姸鎬佸苟鍚姩鍚庡彴 RSSI 閲囨牱
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
        logging.info(f"[DEBUG] About to call perf.get_rx_rate with:")
        logging.info(f"  - router_info: {router_info}")
        logging.info(f"  - type: {type}")
        logging.info(f"  - self.iperf_client_cmd: {getattr(self, 'iperf_client_cmd', 'N/A')}")
        logging.info(f"  - self.dut_ip: {getattr(self, 'dut_ip', 'N/A')}")

        return self.iperf.get_rx_rate(
            router_info,
            type=type,
            corner_tool=corner_tool,
            db_set=db_set,
            debug=debug,
        )

    @step
    def get_tx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        # 銆愭柊澧炪€戦噸缃姸鎬佸苟鍚姩鍚庡彴 RSSI 閲囨牱
        self._extended_rssi_result = None
        self._mcs_tx_result = None
        self._mcs_rx_result = None
        self._rssi_sampled_event.clear()
        rssi_thread = threading.Thread(
            target=self._sample_extended_rssi_after_delay,
            args=(10,),  # 10绉掑悗閲囨牱
            daemon=True  # 涓荤嚎绋嬬粨鏉燂紝瀛愮嚎绋嬭嚜鍔ㄩ攢姣?
        )
        rssi_thread.start()
        return self.iperf.get_tx_rate(
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
        # 鍒濆鍖栭粯璁ゅ€硷紙琛ㄧず鏈幏鍙栧埌锛?
        self.bcn_rssi = -1
        self.wf0_rssi = -1
        self.wf1_rssi = -1

        if self._is_performance_debug_enabled():
            # 妯℃嫙璋冭瘯妯″紡
            import random
            self.bcn_rssi = -random.randint(30, 80)
            self.wf0_rssi = self.bcn_rssi + random.randint(0, 3)
            self.wf1_rssi = self.bcn_rssi + random.randint(0, 3)
            logging.info("Debug mode: simulated extended RSSI = bcn:%d, wf0:%d, wf1:%d",
                         self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)
            return (self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)

        try:
            # Step 1: 娓呴櫎涓婁竴娆℃帴鏀惰褰?
            last_rx_info = self.checkoutput("iwpriv clear_last_rx;sleep 1;iwpriv wlan0 get_last_rx")
            logging.info(f"Last RX Info: {last_rx_info}")
            time.sleep(1)

            # Step 2: 鑾峰彇鏈€鍚庝竴娆℃帴鏀剁殑 RSSI锛堝彲閫夛紝鎸夐渶淇濈暀锛?
            # last_rx_output = self.checkoutput("iwpriv wlan0 get_last_rx")

            # Step 3: 鑾峰彇 beacon RSSI 骞惰Е鍙?dmesg 杈撳嚭
            self.checkoutput(self.CLEAR_DMESG_COMMAND)
            dmesg_output = self.checkoutput(self.CMD_WIFI_BEACON_RSSI)
            if not dmesg_output or 'bcn_rssi:' not in dmesg_output:
                dmesg_output = self.checkoutput(self.CMD_WIFI_BEACON_RSSI2)
            logging.info(f"BEACON RSSI Info: {dmesg_output}")

            if not dmesg_output.strip():
                logging.warning("No 'bcn_rssi' found in dmesg output.")
                return (self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)

            # 鏀寔涓ょ鏃ュ織鏍煎紡锛?
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
            # 淇濇寔榛樿鍊?-1

        return (self.bcn_rssi, self.wf0_rssi, self.wf1_rssi)

    def _sample_extended_rssi_after_delay(self, delay_seconds: int = 10):
        """
        鍦ㄦ寚瀹氬欢杩熷悗閲囨牱鎵╁睍 RSSI锛屽苟瀛樺偍缁撴灉銆?
        閫氬父鐢卞悗鍙扮嚎绋嬭皟鐢ㄣ€?
        """
        try:
            time.sleep(delay_seconds)
            logging.info(f"馃摙 Sampling extended RSSI after {delay_seconds}s...")

            #Get Beacon RSSI
            rssi_result = self.get_extended_rssi()
            self._extended_rssi_result = rssi_result
            logging.info(f"鉁?Extended RSSI sampled: {rssi_result}")

            #Get realtime MCS
            try:
                # 鐩存帴璋冪敤鏂规硶锛屼笉渚濊禆 @step 鎹曡幏
                mcs_tx = self.get_mcs_tx()
                self._mcs_tx_result = mcs_tx
                logging.info(f"鉁?MCS TX: {mcs_tx}")
            except Exception as e:
                logging.error(f"鉂?MCS TX failed: {e}")
                self._mcs_tx_result = "N/A"

            try:
                mcs_rx = self.get_mcs_rx()
                self._mcs_rx_result = mcs_rx
                logging.info(f"鉁?MCS RX: {mcs_rx}")
            except Exception as e:
                logging.error(f"鉂?MCS RX failed: {e}")
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
            logging.error(f"鉂?Failed to sample extended RSSI: {e}")
            self._extended_rssi_result = ("N/A", "N/A", "N/A")
            self._mcs_tx_result = "N/A"
            self._mcs_rx_result = "N/A"
            self._rssi_sampled_event.set()

    step = staticmethod(step)

