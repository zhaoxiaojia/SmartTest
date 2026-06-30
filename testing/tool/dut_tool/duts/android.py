import os
import re
import signal
from testing.tool.dut_tool import command_batch as subprocess
import threading
import time
from collections import Counter
from typing import Optional
from xml.dom import minidom

import _io
import pytest

from testing.tool.dut_tool.duts.base import BaseDut
from testing.tool.dut_tool.features.device_ui import UiautomatorTool
from testing.tool.dut_tool.features.wifi import WifiConnectParams
from tools.logging import smart_log


def connect_again(func):
    """
    Connect again.

    -------------------------
    It executes external commands via Python's subprocess module.

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

    def inner(self, *args, **kwargs):
        """
        Inner.

        -------------------------
        It executes external commands via Python's subprocess module.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if ':5555' in self.serialnumber:
            self.command_runner.run(f'adb connect {self.serialnumber}', shell=True)
        self.wait_devices()
        result = func(self, *args, **kwargs)
        if ':5555' in self.serialnumber:
            text = f"{getattr(result, 'stdout', '') or ''}\n{getattr(result, 'stderr', '') or ''}".lower()
            if (
                "device offline" in text
                or ("offline" in text and "error:" in text)
                or ("device" in text and "not found" in text)
                or "no devices/emulators found" in text
            ):
                smart_log(
                    f"adb offline detected; reconnect serial={self.serialnumber}",
                    level="warning",
                    domain="dut",
                    source="android",
                )
                self.command_runner.run(f'adb disconnect {self.serialnumber}', shell=True)
                self.command_runner.run(f'adb connect {self.serialnumber}', shell=True)
                self.wait_devices()
                return func(self, *args, **kwargs)
        return result

    return inner


class android(BaseDut):
    """
    ADB.

    -------------------------
    It runs shell commands on the target device using ADB helpers and captures the output.
    It executes external commands via Python's subprocess module.
    It logs information for debugging or monitoring purposes.
    It ensures the device has root privileges when required.
    It remounts the device's file system with write permissions.
    It sends key events to the device using ADB.
    It simulates user input on the device's screen (tap, swipe, or text entry).
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """

    ADB_S = 'adb -s '
    DUMP_FILE = '\\view.xml'
    OSD_VIDEO_LAYER = 'osd+video'

    def __init__(self, serialnumber="", logdir="", *, prepare=True):
        """
        Init.

        -------------------------
        It ensures the device has root privileges when required.
        It remounts the device's file system with write permissions.

        -------------------------
        Parameters
        -------------------------
        serialnumber : Any
            The ADB serial number identifying the target device.
        logdir : Any
            Path to the directory where logs will be stored.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        super().__init__()
        self.serialnumber = serialnumber
        self.logdir = logdir or os.path.join(os.getcwd(), 'results')
        self.timer = None
        self.live = False
        self.lock = threading.Lock()
        self.p_config_wifi = ''
        if self.serialnumber and prepare:
            self.root()
            self.remount()

    def _wifi_connect_impl(self, params: WifiConnectParams) -> bool:
        self.forget()
        return bool(
            self._android_connect_wifi(
                params.ssid,
                params.password,
                params.security,
                params.hidden,
                params.lan,
            )
        )

    def _wifi_scan_impl(self, ssid: str, *, attempts: int, scan_wait: int, interval: float) -> bool:
        cmd = f"cmd wifi start-scan;sleep {scan_wait};cmd wifi list-scan-results"
        for _ in range(attempts):
            info = self.checkoutput(cmd)
            smart_log(info, level="info")
            if ssid in info:
                return True
            time.sleep(interval)
        return False

    def _wifi_forget_impl(self):
        list_networks_cmd = "cmd wifi list-networks"
        output = self.checkoutput(list_networks_cmd)
        if "No networks" in output:
            smart_log("has no wifi connect", level="debug")
            return None

        network_ids = re.findall(r"\n(\d+)\s", output)
        for net_id in network_ids:
            forget_wifi_cmd = "cmd wifi forget-network {}".format(int(net_id))
            output1 = self.checkoutput(forget_wifi_cmd)
            if "successful" in output1:
                smart_log(f"Network id {net_id} closed", level="info")
        return None

    def push_iperf(self):
        if self.checkoutput('[ -e /system/bin/iperf ] && echo yes || echo no').strip() != 'yes':
            path = os.path.join(os.getcwd(), 'res/iperf')
            self.push(path, '/system/bin')
            self.checkoutput('chmod a+x /system/bin/iperf')
        return None

    def _run_iperf_server_on_device(self, command: str, *, start_background, extend_logs, encoding: str):
        cmd_parts = command.split()
        cmd_list = ["adb", "-s", self.serialnumber, "shell", *cmd_parts]
        return start_background(cmd_list, "server adb command:")

    def _run_iperf_client_on_device(self, command: str, *, run_blocking, encoding: str):
        cmd_parts = command.split()
        cmd_list = ["adb", "-s", self.serialnumber, "shell", *cmd_parts]
        run_blocking(cmd_list, "client adb command:")
        return None

    def _iperf_client_post_delay_seconds(self) -> int:
        return 0
    def set_status_on(self):
        """
        Set status on.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with self.lock:
            if self.live:
                return
            self.live = True
            smart_log('Adb status is on', level="debug")

    def set_status_off(self):
        """
        Set status off.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with self.lock:
            if not self.live:
                return
            self.live = False
            smart_log('Adb status is Off', level="debug")

    def _u_impl(self, *, type="u2"):
        """
        U.

        -------------------------
        Parameters
        -------------------------
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self._u = UiautomatorTool(self.serialnumber, type)
        return self._u

    def _keyevent_impl(self, keycode):
        """
        Keyevent.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It sends key events to the device using ADB.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        keycode : Any
            Key code representing the button to press.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if isinstance(keycode, int):
            keycode = str(keycode)
        self.checkoutput_term(self.adb_command("shell input keyevent", keycode))
        time.sleep(0.5)

    def send_event(self, key, hold=3):
        """
        Send event.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        key : Any
            Key identifier for sending input events.
        hold : Any
            Time in seconds to hold the key pressed.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput(
            f'sendevent /dev/input/event5 4 4 786501;sendevent /dev/input/event5 1 {key} 1;sendevent  /dev/input/event5 0 0 0;')
        time.sleep(hold)
        self.checkoutput(
            f'sendevent /dev/input/event5 4 4 786501;sendevent /dev/input/event5 1 {key} 0;sendevent  /dev/input/event5 0 0 0;')

    def _home_impl(self):
        """
        Home.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.keyevent("KEYCODE_HOME")

    def enter(self):
        """
        Enter.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.keyevent("KEYCODE_ENTER")

    def root(self):
        """
        Root.

        -------------------------
        It executes external commands via Python's subprocess module.
        It ensures the device has root privileges when required.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.command_runner.run('adb root', shell=True)

    def remount(self):
        """
        Remount.

        -------------------------
        It executes external commands via Python's subprocess module.
        It remounts the device's file system with write permissions.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.command_runner.run('adb remount', shell=True)

    def _reboot_impl(self):
        """
        Reboot.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_shell('reboot')
        self.wait_devices()

    def _back_impl(self):
        """
        Back.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.keyevent("KEYCODE_BACK")

    def _app_switch_impl(self):
        """
        App switch.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.keyevent("KEYCODE_APP_SWITCH")

    def _app_stop_impl(self, app_name):
        """
        App stop.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        app_name : Any
            Name of the application package.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        smart_log("Stop app(%s)" % app_name, level="info")
        self.checkoutput("am force-stop %s" % app_name)

    def clear_app_data(self, app_name):
        """
        Clear app data.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        app_name : Any
            Name of the application package.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput(f"pm clear {app_name}")

    def _expand_logcat_capacity_impl(self):
        """
        Expand logcat capacity.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput("logcat -G 40m")
        self.checkoutput("renice -n -50 `pidof logd`")

    def delete(self, times=1):
        """
        Delete.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Parameters
        -------------------------
        times : Any
            Number of repetitions for the action.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        remain = times
        batch = 64
        while remain > 0:
            self.keyevent("67 " * batch)
            remain -= batch

    def _tap_impl(self, x, y):
        """
        Tap.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It simulates user input on the device's screen (tap, swipe, or text entry).

        -------------------------
        Parameters
        -------------------------
        x : Any
            Horizontal coordinate on the device screen.
        y : Any
            Vertical coordinate on the device screen.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("shell input tap", x, y))

    def _swipe_impl(self, x_start, y_start, x_end, y_end, duration):
        """
        Swipe.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It simulates user input on the device's screen (tap, swipe, or text entry).

        -------------------------
        Parameters
        -------------------------
        x_start : Any
            Starting horizontal coordinate for a swipe gesture.
        y_start : Any
            Starting vertical coordinate for a swipe gesture.
        x_end : Any
            Ending horizontal coordinate for a swipe gesture.
        y_end : Any
            Ending vertical coordinate for a swipe gesture.
        duration : Any
            Duration of the swipe gesture in milliseconds.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("shell input swipe", x_start, y_start, x_end, y_end, duration))

    def _text_impl(self, text):
        """
        Text.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It simulates user input on the device's screen (tap, swipe, or text entry).

        -------------------------
        Parameters
        -------------------------
        text : Any
            Text to input into the device.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if isinstance(text, int):
            text = str(text)
        self.checkoutput_term(self.adb_command("shell input text", text))

    def _clear_logcat_impl(self):
        """
        Clear logcat.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("logcat -b all -c"))

    def _save_logcat_impl(self, filepath, *, tag=''):
        """
        Save logcat.

        -------------------------
        It executes external commands via Python's subprocess module.

        -------------------------
        Parameters
        -------------------------
        filepath : Any
            Path of the file on the host machine where data should be saved.
        tag : Any
            Logcat tag used for filtering output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        filepath = self.logdir + '/' + filepath
        logcat_file = open(filepath, 'w')
        base_cmd = self.adb_command("shell logcat -v time", tag)
        if tag and ("grep -E" not in tag) and ("all" not in tag):
            tag = f'-s {tag}'
            log = self.command_runner.popen(
                self.adb_command("shell logcat -v time", tag).split(),
                stdout=logcat_file,
                stderr=subprocess.STDOUT,
            )
        else:
            log = self.command_runner.popen(
                base_cmd,
                shell=True,
                stdout=logcat_file,
                stderr=subprocess.STDOUT,
            )
        return log, logcat_file

    def _stop_save_logcat_impl(self, log, filepath):
        """
        Stop save logcat.

        -------------------------
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        log : Any
            Popen object representing a running logcat process.
        filepath : Any
            Path of the file on the host machine where data should be saved.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.filter_logcat_pid()
        log.terminate()
        log.send_signal(signal.SIGINT)
        filepath.close()

    def _filter_logcat_pid_impl(self):
        """
        Filter logcat pid.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        p_lookup_logcat_thread_cmd = 'ps -e | grep logcat'
        output = self.checkoutput(p_lookup_logcat_thread_cmd)
        if 'logcat' in output:
            p_logcat_pid = re.search('(.*?) logcat', output, re.M | re.I).group(1).strip().split(" ")
            if "S" in p_logcat_pid:
                for one in p_logcat_pid:
                    if re.findall(r".*\d+", one):
                        self.checkoutput(f"kill -9 {one}")
                        break
        return output

    def _start_activity_impl(self, packageName, activityName, *, intentname=""):
        """
        Start activity.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        packageName : Any
            The ``packageName`` parameter.
        activityName : Any
            The ``activityName`` parameter.
        intentname : Any
            The ``intentname`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.app_stop(packageName)
        except Exception as e:
            ...
        command = self.adb_command("shell am start -a", intentname, "-n", packageName + "/" + activityName)
        self.checkoutput_term(command)

    def pull(self, filepath, destination):
        """
        Pull.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        filepath : Any
            Path of the file on the host machine where data should be saved.
        destination : Any
            The ``destination`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("pull", filepath, destination))

    def push(self, filepath, destination):
        """
        Push.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        filepath : Any
            Path of the file on the host machine where data should be saved.
        destination : Any
            The ``destination`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        command = self.adb_command("push", filepath, destination)
        self.checkoutput_term(command)

    def shell(self, cmd):
        """
        Shell.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("shell", cmd))

    def check_apk_exist(self, package_name):
        """
        Check apk exist.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        package_name : Any
            The ``package_name`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return True if package_name in self.checkoutput('pm list packages') else False

    def install_apk(self, apk_path):
        """
        Install apk.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        apk_path : Any
            The ``apk_path`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        apk_path = os.path.join(os.getcwd(), 'res\\' + apk_path)
        cmd = f'install -r -t {apk_path}'
        return self.checkoutput_shell(cmd)

    def uninstall_apk(self, apk_name):
        """
        Uninstall apk.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        apk_name : Any
            The ``apk_name`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        cmd = f'uninstall {apk_name}'
        output = self.checkoutput_shell(cmd)
        time.sleep(5)
        if 'Success' in output:
            smart_log('APK uninstall successful', level="info")
            return True
        else:
            smart_log('APK uninstall failed', level="info")
            return False

    def get_time(self, time=None):
        """
        Retrieve time.

        -------------------------
        Parameters
        -------------------------
        time : Any
            The ``time`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if (":" not in time[6:8]) and (":" not in time[9:11]) and (":" not in time[12:14]) and (
                ":" not in time[15:18]) and ("." not in time[15:18]):
            th = int(time[6:8])
            tm = int(time[9:11])
            ts = int(time[12:14])
            tms = int()
            if "-" not in time[15:18]:
                tms = int(time[15:18])
            return (tms + ts * 1000 + tm * 60 * 1000 + th * 3600 * 1000) / 1000

    def getprop(self, key):
        """
        Getprop.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        key : Any
            Key identifier for sending input events.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return self.checkoutput('getprop %s' % key, )

    def rm(self, flags, path):
        """
        Rm.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        flags : Any
            The ``flags`` parameter.
        path : Any
            The ``path`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("shell rm", flags, path))

    def _uiautomator_dump_impl(self, *, filepath='', uiautomator_type='u2'):
        """
        Uiautomator dump.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        filepath : Any
            Path of the file on the host machine where data should be saved.
        uiautomator_type : Any
            The ``uiautomator_type`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if not filepath:
            filepath = self.logdir
        smart_log('doing uiautomator dump', level="debug")
        if uiautomator_type == 'u2':
            xml = self.u().d2.dump_hierarchy()
        else:
            uiautomator_type = 'u1'
            xml = self.u(type=uiautomator_type).d1.dump()
        if not filepath.endswith('view.xml'):
            filepath += self.DUMP_FILE
        smart_log(filepath, level="debug")
        with open(filepath, 'w+', encoding='utf-8') as f:
            f.write(xml)
        smart_log('uiautomator dump done', level="debug")

    def get_dump_info(self):
        """
        Retrieve dump info.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        path = self.logdir + self.DUMP_FILE if os.path.exists(
            self.logdir + self.DUMP_FILE) else self.logdir + '/view.xml'
        with open(path, 'r', encoding='utf-8') as f:
            temp = f.read()
        return temp

    def expand_notifications(self):
        """
        Expand notifications.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term(self.adb_command("shell cmd statusbar expand-notifications"))

    def _screencap(self, filepath, layer="osd", app_level=28):
        """
        Screencap.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        filepath : Any
            Path of the file on the host machine where data should be saved.
        layer : Any
            The ``layer`` parameter.
        app_level : Any
            The ``app_level`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if layer == "osd":
            self.checkoutput_term(self.adb_command("shell screencap -p", filepath))
        else:
            png_type = 1
            if layer == "video" or layer == self.OSD_VIDEO_LAYER:
                if app_level > 28:
                    self.screencatch(layer)
                else:
                    if layer == "video":
                        png_type = 0
                    cmd = "pngtest " + str(png_type)
                    self.checkoutput(cmd)
            else:
                smart_log("please check the set screen layer arg", level="info")

    def screenshot(self, destination, layer="osd", app_level=28):
        """
        Screenshot.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        destination : Any
            The ``destination`` parameter.
        layer : Any
            The ``layer`` parameter.
        app_level : Any
            The ``app_level`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if layer == "osd":
            devicePath = "/sdcard/screen.png"
            destination = self.logdir + "/" + "screencap_" + destination + ".png"
        else:
            dirs = self.mkdir_temp()
            if app_level > 28:
                devicePath = dirs + "/1.bmp"
                destination = self.logdir + "/" + "screencatch_" + destination + ".bmp"
            else:
                devicePath = dirs + "/1.jpeg"
                destination = self.logdir + "/" + "pngtest_" + destination + ".jpeg"
        self._screencap(devicePath, layer, app_level)
        time.sleep(2)
        self.pull(devicePath, destination)
        time.sleep(2)
        if layer == "osd":
            self.rm("", devicePath)
        else:
            self.rm("-r", dirs)

    def continuous_screenshot(self, destination, layer="osd+video", app_level=30, screenshot_counter=3):
        """
        Continuous screenshot.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        destination : Any
            The ``destination`` parameter.
        layer : Any
            The ``layer`` parameter.
        app_level : Any
            The ``app_level`` parameter.
        screenshot_counter : Any
            The ``screenshot_counter`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        dirs = self.mkdir_temp()
        if app_level > 28 and screenshot_counter > 1 and (layer == "video" or layer == self.OSD_VIDEO_LAYER):
            self.screencatch(layer, screenshot_counter)
            time.sleep(5)
            for i in range(screenshot_counter):
                i = i + 1
                devicePath = dirs + "/" + str(i) + ".bmp"
                smart_log(devicePath, level="info")
                destination_temp = self.logdir + "/" + "screencatch_" + destination + "_" + str(i) + ".bmp"
                self.pull(devicePath, destination_temp)
                time.sleep(2)
        else:
            smart_log('you can use screenshot cmd', level="info")
        self.rm("-r", dirs)

    def screencatch(self, layer="osd+video", counter=1):
        """
        Screencatch.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        layer : Any
            The ``layer`` parameter.
        counter : Any
            The ``counter`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if layer == self.OSD_VIDEO_LAYER:
            capture_type = "1"
        else:
            capture_type = "0"
        cmd = "screencatch -m " + " -t " + capture_type + " -c " + str(counter)
        self.run_shell_cmd(cmd)

    def video_record(self, destination, app_level=28, record_time=30, sleep_time=30,
                     frame=30, bits=4000000, type=1):
        """
        Video record.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        destination : Any
            The ``destination`` parameter.
        app_level : Any
            The ``app_level`` parameter.
        record_time : Any
            The ``record_time`` parameter.
        sleep_time : Any
            The ``sleep_time`` parameter.
        frame : Any
            The ``frame`` parameter.
        bits : Any
            The ``bits`` parameter.
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        destination = self.logdir + "/" + "video_record_" + destination + ".ts"
        dirs = self.mkdir_temp()
        if app_level <= 28:
            video_record = self.popen("shell tspacktest")
            time.sleep(sleep_time)
            os.kill(video_record.pid, signal.SIGTERM)
        else:
            cmd = "tspacktest -f " + str(frame) + " -b " + str(bits) + " -t " + str(type) + " -s " + str(record_time)
            self.run_shell_cmd(cmd)
        time.sleep(2)
        video = dirs + "/video.ts"
        self.pull(video, destination)
        time.sleep(5)
        self.rm("-r", dirs)

    def mkdir_temp(self):
        """
        Mkdir temp.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It ensures the device has root privileges when required.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.root()
        dirs = '/data/temp'
        temp = self.checkoutput("ls /data")
        if "temp" not in temp:
            self.checkoutput("mkdir " + dirs)
        self.checkoutput("chmod 777 " + dirs)
        return dirs

    def check_adb_status(self, waitTime=100):
        """
        Check ADB status.

        -------------------------
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        waitTime : Any
            The ``waitTime`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        i = 0
        waitCnt = waitTime / 5
        while i < waitCnt:
            command = "adb devices"
            cmd = command.split()
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            adb_devices = proc.communicate()[0].decode()
            rc = proc.returncode
            if rc == 0 and self.serialnumber in adb_devices and \
                    len(self.serialnumber) != 0:
                return True
            i = i + 1
            time.sleep(5)
            smart_log("Still waiting..", level="debug")
        return False

    def wait_and_tap(self, searchKey, attribute, times=5):
        """
        Wait for and tap.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.
        times : Any
            Number of repetitions for the action.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        for _ in range(times):
            if self.find_element(searchKey, attribute):
                self.find_and_tap(searchKey, attribute)
                return 1
            time.sleep(1)

    def wait_element(self, searchKey, attribute):
        """
        Wait for element.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        for _ in range(5):
            if self.find_element(searchKey, attribute):
                return 1
            time.sleep(1)

    def find_element(self, searchKey, attribute, extractKey=None):
        """
        Find element.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.
        extractKey : Any
            The ``extractKey`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        smart_log(f'find {searchKey}', level="info")
        filepath = os.path.join(self.logdir, self.DUMP_FILE)
        self.uiautomator_dump(filepath)
        xml_file = minidom.parse(filepath)
        itemlist = xml_file.getElementsByTagName('node')
        for item in itemlist:
            if searchKey == item.attributes[attribute].value:
                smart_log(
                    item.attributes[attribute].value if extractKey is None else item.attributes[extractKey].value, level="info")
                return item.attributes[attribute].value if extractKey is None else item.attributes[extractKey].value
        return None

    def find_pos(self, searchKey, attribute):
        """
        Find pos.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        smart_log('find_pos', level="info")
        filepath = self.logdir + self.DUMP_FILE
        self.uiautomator_dump(filepath)
        xml_file = minidom.parse(filepath)
        itemlist = xml_file.getElementsByTagName('node')
        bounds = None
        for item in itemlist:
            smart_log(f'try to find {searchKey} - {item.attributes[attribute].value}', level="debug")
            if searchKey == item.attributes[attribute].value:
                bounds = item.attributes['bounds'].value
                break
        if bounds is None:
            smart_log("attr: %s not found" % attribute, level="error")
            return -1, -1
        bounds = re.findall(r'\[(\d+)\,(\d+)\]', bounds)
        x_start, y_start = bounds[0]
        x_end, y_end = bounds[1]
        x_midpoint, y_midpoint = (int(x_start) + int(x_end)) / 2, (int(y_start) + int(y_end)) / 2
        smart_log(f'{x_midpoint} {y_midpoint}', level="info")
        return (x_midpoint, y_midpoint)

    def find_and_tap(self, searchKey, attribute):
        """
        Find and tap.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It simulates user input on the device's screen (tap, swipe, or text entry).
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        smart_log(f'find_and_tap {searchKey}', level="info")
        x_midpoint, y_midpoint = self.find_pos(searchKey, attribute)
        if (x_midpoint, y_midpoint) != (-1, -1):
            self.tap(x_midpoint, y_midpoint)
        return x_midpoint, y_midpoint

    def text_entry(self, text, searchKey, attribute, delete=64):
        """
        Text entry.

        -------------------------
        It sends key events to the device using ADB.
        It simulates user input on the device's screen (tap, swipe, or text entry).

        -------------------------
        Parameters
        -------------------------
        text : Any
            Text to input into the device.
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.
        delete : Any
            The ``delete`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        filepath = self.logdir + self.DUMP_FILE
        self.uiautomator_dump(filepath)
        xml_file = minidom.parse(filepath)
        itemlist = xml_file.getElementsByTagName('node')
        bounds = None
        for item in itemlist:
            if searchKey.upper() in item.attributes[attribute].value.upper():
                if "EditText" in item.attributes['class'].value:
                    bounds = item.attributes['bounds'].value
                    break
        if bounds is None:
            return None
        bounds = re.findall(r'\[(\d+)\,(\d+)\]', bounds)
        x_start, y_start = bounds[0]
        x_end, y_end = bounds[1]
        x_midpoint, y_midpoint = (int(x_start) + int(x_end)) / 2, (int(y_start) + int(y_end)) / 2

        self.tap(x_midpoint, y_midpoint)

        self.keyevent("KEYCODE_MOVE_END")
        self.delete(delete)

        self.text(text)

        self.keyevent("KEYCODE_ENTER")
        return x_midpoint, y_midpoint

    @classmethod
    def wait_power(cls):
        """
        Wait for power.

        -------------------------
        It executes external commands via Python's subprocess module.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        for i in range(10):
            info = subprocess.check_output("adb devices", shell=True, encoding='utf-8')
            devices = re.findall(r'\n(.*?)\s+device', info, re.S)
            if devices:
                break
            time.sleep(10)
        else:
            assert False, "Can't find any device"

    def wait_devices(self):
        """
        Wait for devices.

        -------------------------
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
    def _kill_logcat_pid_impl(self):
        """
        Kill logcat pid.

        -------------------------
        It executes external commands via Python's subprocess module.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput("killall logcat")

    def popen(self, command):
        """
        Popen.

        -------------------------
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
        cmd = self.adb_command(command)
        return self.command_runner.popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def checkoutput(self, command):
        """
        Checkoutput.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

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
        command = 'shell ' + f'"{command}"'
        return self.checkoutput_shell(command)

    @connect_again
    def checkoutput_shell(self, command):
        """
        Checkoutput shell.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

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
        command = self.adb_command(command)
        return self.checkoutput_term(command)

    @connect_again
    def adb_call(self, *parts: object, timeout: float | None = None):
        command = self.adb_command_prefix().split()
        command.extend(str(part) for part in parts if str(part).strip())
        return self.command_runner.run(command, timeout=timeout)

    def _android_connect_wifi(self, ssid: str, pwd: str, security: str, hide: bool, lan=True) -> bool:
        """
        Android connect Wi鈥慒i.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.
        pwd : Any
            The ``pwd`` parameter.
        security : Any
            The ``security`` parameter.
        hide : Any
            The ``hide`` parameter.
        lan : Any
            The ``lan`` parameter.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
        """
        command = self.CMD_WIFI_CONNECT.format(ssid, security, pwd)
        if hide:
            command += self.CMD_WIFI_HIDE

        connect_status = False
        #260209 For DFS channle maybe need over 10 minutes to gets up, need more time to try.
        for _ in range(30):
            try:
                self.checkoutput(command)
                time.sleep(15)
                if lan:
                    if not getattr(self, "ip_target", ""):
                        _ = self.pc_ip
                    target = self.ip_target
                else:
                    target = "."
                ok, _ = self.wait_ip(cmd=command, target=target, lan=lan)
                if ok:
                    connect_status = True
                    break
            except Exception as exc:  # pragma: no cover - hardware dependent
                smart_log(exc, level="info")
                connect_status = False
        return connect_status

    def check_wifi_driver(self):
        """
        Check Wi鈥慒i driver.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.clear_logcat()
        file_list = self.checkoutput("ls /vendor/lib/modules")
        if 'vlsicomm.ko' in file_list:
            smart_log('Wifi driver is exists', level="info")
            return True
        else:
            smart_log('Wifi driver is not exists', level="info")
            return False

    def get_mcs_rx(self):
        """
        Retrieve mcs rx.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            self.checkoutput(self.CLEAR_DMESG_COMMAND)
            self.checkoutput(self.MCS_RX_GET_COMMAND)
            mcs_info = self.checkoutput(self.DMESG_COMMAND)
            smart_log("mcs_rx all result: %s", mcs_info, level="info")
            result = re.findall(r'RX rate info for \w\w:\w\w:\w\w:\w\w:\w\w:\w\w:(.*?)Last received rate', mcs_info,
                                re.S)
            #smart_log("mcs_rx rate result: %s", result, level="info")
            result_list = []
            for i in result[0].split('\n'):
                if ':' in i:
                    rate = re.findall(r'(\w+\.?\/?\w+)\s+:\s+\d+\((.*?)\)', i)
                    result_list.append(rate[0])
            result_list = [(i[0], float(i[1][:-1].strip())) for i in result_list]

            result_list.sort(key=lambda x: x[1], reverse=True)
            smart_log(result_list, level="info")
            return '|'.join(['{}:{}%'.format(i[0], i[1]) for i in result_list[:3]])
        except Exception as e:
            return 'mcs_rx'

    def get_mcs_tx(self):
        """
        Retrieve mcs tx.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            self.checkoutput(self.CLEAR_DMESG_COMMAND)
            self.checkoutput(self.MCS_TX_GET_COMMAND)
            mcs_info = self.checkoutput(self.DMESG_COMMAND)
            smart_log("mcs_tx all result: %s", mcs_info, level="info")
            result = re.findall(
                #r'TX rate info for [\w:]+:\s*\n(.*?MPDUs AMPDUs AvLen trialP)',
                r'(TX rate info for [\w:]+:\s*\n(?:\s*\[.*?\]\s*\[.*?\]\s*.*\n)+?)'
                r'(?=\s*\[|\s*$)',
                mcs_info,
                re.DOTALL
            )
            mcs_distribution = self.parse_mcs_distribution_from_blocks(result)
            return mcs_distribution
        except Exception as e:
            return 'mcs_tx'

    def parse_mcs_distribution_from_blocks(self, blocks):
        """
        Input: TX rate info MCS info
        OutPut: "MCS4/2:24.8%|MCS6/2:24.8%|MCS7/2:20.7%"
        """
        from collections import defaultdict
        if not blocks:
            return "MCS_NO_BLOCK"

        last_block_str = blocks[-1]
        lines = last_block_str.strip().split('\n')

        data_lines = []
        for line in lines:
            if 'TX rate info' in line or '# type' in line:
                continue
            if line.strip() and re.search(r'\[\d+\s+T\d+', line):
                data_lines.append(line)

        mcs_skipped = defaultdict(int)

        # 鎻愬彇姣忚鐨?MCS 鍜?skipped
        for line in data_lines:
            line = line.strip()
            #smart_log(f"tx_MCS_data_line: {line}", level="info")
            if not line:
                continue
            # 鍖归厤 MCSx/y skipped
            #match = re.search(r'(MCS\d+/\d+).*\s(\d+)\s*$', line)
            match = re.search(r'(MCS\d+).*?\(\s*\d+\s*\)\s+(\d+)(?:\s+[A-Z])?$', line)
            if match:
                mcs = match.group(1)
                skipped = int(match.group(2))
                mcs_skipped[mcs] += skipped

        if not mcs_skipped:
            return "MCS_PARSE_FAIL"

        # weight = 1 / (skipped + 1)
        total_weight = 0.0
        mcs_weights = {}
        for mcs, skipped in mcs_skipped.items():
            w = 1.0 / (skipped + 1)
            mcs_weights[mcs] = w
            total_weight += w

        # to % and top3
        sorted_mcs = sorted(mcs_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        parts = [f"{mcs}:{(w / total_weight) * 100:.1f}%" for mcs, w in sorted_mcs]
        return "|".join(parts)

    def get_tx_bitrate(self):
        """
        Retrieve tx bitrate.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It ensures the device has root privileges when required.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            self.root()
            result = self.checkoutput(self.IW_LINNK_COMMAND)
            rate = re.findall(r'tx bitrate:\s+(.*?)\s+MBit\/s', result, re.S)[0]
            return rate
        except Exception as e:
            return 'Data Error'

    def wait_for_wifi_service(self, type='wlan0', recv='Link encap') -> None:
        """
        Wait for for Wi鈥慒i service.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").
        recv : Any
            The ``recv`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        count = 0
        while True:
            info = self.checkoutput(f'ifconfig {type}')
            smart_log(info, level="info")
            if recv in info:
                break
            time.sleep(10)
            count += 1
            if count > 10:
                raise EnvironmentError('Lost device')

    def wait_for_launcher(self) -> None:
        """
        Wait for for launcher.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        log = self.popen('logcat')
        while True:
            try:
                line = log.stdout.readline()
            except UnicodeDecodeError as e:
                ...
            if 'Displayed com.google.android.tvlauncher/.MainActivity' in line:
                time.sleep(1)
                smart_log('wait for launcher', level="info")
                break
        log.terminate()
        log.send_signal(signal.SIGINT)

    def enter_wifi_activity(self) -> None:
        """
        Enter Wi鈥慒i activity.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.app_stop(self.SETTING_ACTIVITY_TUPLE[0])
        smart_log('Enter wifi activity', level="info")
        self.start_activity(*self.SETTING_ACTIVITY_TUPLE)
        self.wait_element('Network & Internet', 'text')
        self.wait_and_tap('Network & Internet', 'text')
        self.uiautomator_dump()
        if 'Available networks' not in self.get_dump_info():
            self.wait_and_tap('Wi-Fi', 'text')
        self.wait_element('Wi-Fi', 'text')

    def enter_hotspot(self) -> None:
        """
        Enter hotspot.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.start_activity(*self.SETTING_ACTIVITY_TUPLE)
        self.wait_element('Network & Internet', 'text')
        self.wait_and_tap('Network & Internet', 'text')
        for i in range(8):
            self.keyevent(20)
        self.wait_and_tap('HotSpot', 'text')

    def open_hotspot(self) -> None:
        """
        Open hotspot.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.enter_hotspot()
        self.wait_element('Portable HotSpot Enabled', 'text')
        self.uiautomator_dump()
        if not re.findall(self.OPEN_INFO, self.get_dump_info(), re.S):
            self.wait_and_tap('Portable HotSpot Enabled', 'text')
            self.get_dump_info()
        times = 0
        while not re.findall(self.OPEN_INFO, self.get_dump_info(), re.S):
            time.sleep(1)
            self.uiautomator_dump()
            times += 1
            if times > 5:
                raise EnvironmentError("Can't open hotspot")

    def close_hotspot(self) -> None:
        """
        Close hotspot.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.kill_setting()
        self.enter_hotspot()
        self.wait_element('Portable HotSpot Enabled', 'text')
        self.uiautomator_dump()
        if re.findall(self.OPEN_INFO, self.get_dump_info(), re.S):
            self.wait_and_tap('Portable HotSpot Enabled', 'text')
            self.get_dump_info()
        times = 0
        while re.findall(self.OPEN_INFO, self.get_dump_info(), re.S):
            time.sleep(1)
            self.uiautomator_dump()
            times += 1
            if times > 5:
                raise EnvironmentError("Can't close hotspot")

    def kill_setting(self) -> None:
        """
        Kill setting.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.app_stop(self.SETTING_ACTIVITY_TUPLE[0])

    def kill_moresetting(self) -> None:
        """
        Kill moresetting.

        -------------------------
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        for i in range(5):
            self.keyevent(4)
        self.kill_setting()

    def factory_reset_ui(self):
        """
        Factory reset ui.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It sends key events to the device using ADB.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.start_activity(*self.SETTING_ACTIVITY_TUPLE)
        self.wait_and_tap('Device Preferences', 'text')
        self.wait_and_tap('About', 'text')
        self.wait_and_tap('Factory reset', 'text')
        time.sleep(1)
        self.keyevent(20)
        self.keyevent(20)
        self.keyevent(23)
        time.sleep(1)
        self.keyevent(20)
        self.keyevent(20)
        self.keyevent(23)
        time.sleep(5)
        assert self.serialnumber not in self.checkoutput_term('adb devices'), 'Factory reset fail'
        self.wait_devices()
        smart_log('device done', level="info")

    def get_wifi_cmd(self, router_info):
        """
        Retrieve Wi鈥慒i cmd.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        router_info : Any
            The ``router_info`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        type = 'wpa3' if 'WPA3' in router_info.security_mode else 'wpa2'
        # Treat several synonyms for unencrypted networks; Chinese labels removed
        unencrypted_labels = ['open', 'unencrypted', 'none', 'open system',
                              'unencrypted (allow all connections)']
        if router_info.security_mode.lower() in unencrypted_labels:
            cmd = self.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
        else:
            cmd = self.CMD_WIFI_CONNECT.format(router_info.ssid, type, router_info.password)
        # Hide SSID if the flag is set to a truthy value
        if router_info.hide_ssid in ('yes', 'true', True):
            cmd += self.CMD_WIFI_HIDE
        smart_log(f'conn wifi cmd :{cmd}', level="info")
        return cmd

