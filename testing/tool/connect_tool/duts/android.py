import logging
import os
import re
import signal
from testing.tool.connect_tool import command_batch as subprocess
import threading
import time
from collections import Counter
from typing import Optional
from xml.dom import minidom

import _io
import pytest

from testing.tool.connect_tool.mixins.dut_mixins import WifiConnectParams
from testing.tool.connect_tool.duts.linux import linux
from testing.tool.connect_tool.transports.uiautomator_tool import UiautomatorTool


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
        return func(self, *args, **kwargs)

    return inner


class android(linux):
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

    def __init__(self, serialnumber="", logdir=""):
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
        if self.serialnumber:
            self.root()
            self.remount()

    def _wifi_connect_impl(self, params: WifiConnectParams) -> bool:
        self.wifi_forget()
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
            logging.info(info)
            if ssid in info:
                return True
            time.sleep(interval)
        return False

    def _wifi_forget_impl(self):
        list_networks_cmd = "cmd wifi list-networks"
        output = self.checkoutput(list_networks_cmd)
        if "No networks" in output:
            logging.debug("has no wifi connect")
            return None

        network_ids = re.findall(r"\n(\d+)\s", output)
        for net_id in network_ids:
            forget_wifi_cmd = "cmd wifi forget-network {}".format(int(net_id))
            output1 = self.checkoutput(forget_wifi_cmd)
            if "successful" in output1:
                logging.info(f"Network id {net_id} closed")
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
            logging.debug('Adb status is on')

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
            logging.debug('Adb status is Off')

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

    def get_uuid(self):
        """
        Retrieve  UUID.

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
        return self.checkoutput("ls /storage/ |awk '{print $1}' |head -n 1")

    def get_uuids(self):
        """
        Retrieve uuids.

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
        return self.checkoutput("ls /storage/ |awk '{print $1}'")[1].split("\n")

    def get_uuid_size(self):
        """
        Retrieve  UUID size.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        uuid = self.get_uuid()
        logging.info(f'uuid {uuid}')
        size = self.checkoutput(f"df -h |grep {uuid}|cut -f 3 -d ' '").strip()[:-1]
        return int(float(size))

    def get_uuid_avail_size(self):
        """
        Retrieve  UUID avail size.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        uuid = self.get_uuid()
        size = self.checkoutput(f"df -h |grep {uuid}|cut -f 7 -d ' '").strip()[:-1]
        unit = re.findall(r'[A-Za-z]', self.checkoutput(f"df -h |grep {uuid}|cut -f 7 -d ' '"))
        if len(size) == 0:
            size = self.checkoutput(f"df -h |grep {uuid}|cut -f 8 -d ' '").strip()[:-1]
            unit = re.findall(r'[A-Za-z]', self.checkoutput(f"df -h |grep {uuid}|cut -f 8 -d ' '"))
            if len(size) == 0:
                size = 0
                return size
        if unit[0] == 'G':
            size = int(float(size)) * 1024
        elif unit[0] == 'K':
            size = int(float(size)) / 1024
        return int(float(size))

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
        self.checkoutput_term(self.ADB_S + self.serialnumber +
                              " shell input keyevent " + keycode)
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
        logging.info("Stop app(%s)" % app_name)
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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " shell input tap " + str(x) + " " + str(y))

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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " shell input swipe " + str(x_start) +
                              " " + str(y_start) + " " + str(x_end) + " " + str(y_end) + " " + str(duration))

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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " shell input text " + text)

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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " logcat -b all -c")

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
        base_cmd = f"adb -s {self.serialnumber} shell logcat -v time {tag}"
        if tag and ("grep -E" not in tag) and ("all" not in tag):
            tag = f'-s {tag}'
            log = self.command_runner.popen(
                f"adb -s {self.serialnumber} shell logcat -v time {tag}".split(),
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
        command = self.ADB_S + self.serialnumber + " shell am start -a " + intentname + " -n " + packageName + "/" + activityName
        logging.info(command)
        self.checkoutput_term(self.ADB_S + self.serialnumber +
                              " shell am start -a " + intentname + " -n " + packageName + "/" + activityName)

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
        self.checkoutput_term(self.ADB_S + self.serialnumber +
                              " pull " + filepath + " " + destination)

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
        logging.info(self.ADB_S + self.serialnumber +
                     " push " + filepath + " " + destination)
        self.checkoutput_term(self.ADB_S + self.serialnumber +
                              " push " + filepath + " " + destination)

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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " shell " + cmd)

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
        logging.info(cmd)
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
        logging.info(cmd)
        output = self.checkoutput_shell(cmd)
        time.sleep(5)
        logging.info(output)
        if 'Success' in output:
            logging.info('APK uninstall successful')
            return True
        else:
            logging.info('APK uninstall failed')
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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " shell rm " + flags + " " + path)

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
        logging.debug('doing uiautomator dump')
        if uiautomator_type == 'u2':
            xml = self.u().d2.dump_hierarchy()
        else:
            uiautomator_type = 'u1'
            xml = self.u(type=uiautomator_type).d1.dump()
        if not filepath.endswith('view.xml'):
            filepath += self.DUMP_FILE
        logging.debug(filepath)
        with open(filepath, 'w+', encoding='utf-8') as f:
            f.write(xml)
        logging.debug('uiautomator dump done')

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
        self.checkoutput_term(self.ADB_S + self.serialnumber + " shell cmd statusbar expand-notifications")

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
            self.checkoutput_term(self.ADB_S + self.serialnumber + " shell screencap -p " + filepath)
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
                logging.info("please check the set screen layer arg")

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
                logging.info(devicePath)
                destination_temp = self.logdir + "/" + "screencatch_" + destination + "_" + str(i) + ".bmp"
                self.pull(devicePath, destination_temp)
                time.sleep(2)
        else:
            logging.info('you can use screenshot cmd')
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
        logging.info(cmd)
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
            logging.info(cmd)
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
            logging.debug("Still waiting..")
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
        logging.info(f'find {searchKey}')
        filepath = os.path.join(self.logdir, self.DUMP_FILE)
        self.uiautomator_dump(filepath)
        xml_file = minidom.parse(filepath)
        itemlist = xml_file.getElementsByTagName('node')
        for item in itemlist:
            if searchKey == item.attributes[attribute].value:
                logging.info(
                    item.attributes[attribute].value if extractKey is None else item.attributes[extractKey].value)
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
        logging.info('find_pos')
        filepath = self.logdir + self.DUMP_FILE
        self.uiautomator_dump(filepath)
        xml_file = minidom.parse(filepath)
        itemlist = xml_file.getElementsByTagName('node')
        bounds = None
        for item in itemlist:
            logging.debug(f'try to find {searchKey} - {item.attributes[attribute].value}')
            if searchKey == item.attributes[attribute].value:
                bounds = item.attributes['bounds'].value
                break
        if bounds is None:
            logging.error("attr: %s not found" % attribute)
            return -1, -1
        bounds = re.findall(r'\[(\d+)\,(\d+)\]', bounds)
        x_start, y_start = bounds[0]
        x_end, y_end = bounds[1]
        x_midpoint, y_midpoint = (int(x_start) + int(x_end)) / 2, (int(y_start) + int(y_end)) / 2
        logging.info(f'{x_midpoint} {y_midpoint}')
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
        logging.info(f'find_and_tap {searchKey}')
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
        count = 0

        # while True:
            # try:
            #     info = subprocess.check_output("adb devices", shell=True, encoding='utf-8',ignore='',)
            # except:
            #     info = ''
            # if re.findall(r'\n(.*?)\s+device', info, re.S):
            #     self.serialnumber = re.findall(r'\n(.*?)\s+device', info, re.S)[0]
            #     if '.' in self.serialnumber:
            #         subprocess.check_output(f'adb connect {self.serialnumber}', shell=True)
            #     self.set_status_on()
            #     break
            # if count % 10 == 0:
            #     logging.info('devices not exists')
            # self.set_status_off()
            # time.sleep(5)
            # count += 1
            # if count > 20:
            #     raise EnvironmentError('Lost Device')
            # time.sleep(10)


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
        self.subprocess_run("killall logcat")

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
        logging.debug(f"command:{self.ADB_S + self.serialnumber + ' ' + command}")
        cmd = self.ADB_S + self.serialnumber + ' ' + command
        return self.popen_term(cmd)

    def popen_term(self, command):
        """
        Popen term.

        -------------------------
        It executes external commands via Python's subprocess module.

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
        return subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
        command = self.ADB_S + self.serialnumber + ' ' + command
        return self.checkoutput_term(command)

    @connect_again
    def subprocess_run(self, command):
        """
        Subprocess run.

        -------------------------
        It executes external commands via Python's subprocess module.

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
        if isinstance(command, list):
            result = self.command_runner.run(command, shell=False)
            return result.stdout
        adb_command = f"{self.ADB_S}{self.serialnumber} shell {command}"
        result = self.command_runner.run(adb_command, shell=True)
        return result.stdout

    def open_omx_info(self):
        """
        Open omx info.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput("setprop media.omx.log_levels 255")
        self.checkoutput("setprop vendor.media.omx.log_levels 255")
        self.checkoutput("setprop debug.stagefright.omx-debug 5")
        self.checkoutput("setprop vendor.mediahal.loglevels 255")

    def close_omx_info(self):
        """
        Close omx info.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput("setprop media.omx.log_levels 0")
        self.checkoutput("setprop vendor.media.omx.log_levels 0")
        self.checkoutput("setprop debug.stagefright.omx-debug 0")
        self.checkoutput("setprop vendor.mediahal.loglevels 0")

    def factory_reset_bootloader(self):
        """
        Factory reset bootloader.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.checkoutput_term('adb reboot bootloader')
        self.set_status_off()
        for i in range(10):
            if 'fastboot' in self.checkoutput_term('fastboot devices'):
                break
            time.sleep(3)
        try:
            self.checkoutput_term('fastboot flashing unlock_critical')
            time.sleep(1)
            self.checkoutput_term('fastboot flashing unlock')
            time.sleep(1)
            self.checkoutput_term('fastboot -w')
            time.sleep(2)
        except subprocess.CalledProcessError as e:
            logging.info('Error occur')
        self.checkoutput_term('fastboot reboot')
        time.sleep(120)

    def apk_enable(self, packageName):
        """
        Apk enable.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        packageName : Any
            The ``packageName`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        output = self.checkoutput(f'pm enable {packageName}')
        return output

    def check_cmd_wifi(self):
        """
        Check cmd Wi‑Fi.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            return 'connect-network' in self.checkoutput("cmd wifi -h")
        except Exception:
            return False

    def set_wifi_enabled(self):
        """
        Set Wi‑Fi enabled.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        output = self.checkoutput("ifconfig")
        if "wlan0" not in output:
            self.checkoutput("cmd wifi set-wifi-enabled enabled")
        else:
            logging.debug("wifi has opened,no need to open wifi")

    def set_wifi_disabled(self):
        """
        Set Wi‑Fi disabled.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        output = self.checkoutput("cmd wifi set-wifi-enabled disabled")
        if "wlan0" not in output:
            logging.debug("wifi has closed")

    def _android_connect_wifi(self, ssid: str, pwd: str, security: str, hide: bool, lan=True) -> bool:
        """
        Android connect Wi‑Fi.

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
                ok, _ = self.wifi_wait_ip(cmd=command, target=target, lan=lan)
                if ok:
                    connect_status = True
                    break
            except Exception as exc:  # pragma: no cover - hardware dependent
                logging.info(exc)
                connect_status = False
        return connect_status

    def check_wifi_driver(self):
        """
        Check Wi‑Fi driver.

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
            logging.info('Wifi driver is exists')
            return True
        else:
            logging.info('Wifi driver is not exists')
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
            logging.info("mcs_rx all result: %s", mcs_info)
            result = re.findall(r'RX rate info for \w\w:\w\w:\w\w:\w\w:\w\w:\w\w:(.*?)Last received rate', mcs_info,
                                re.S)
            #logging.info("mcs_rx rate result: %s", result)
            result_list = []
            for i in result[0].split('\n'):
                if ':' in i:
                    rate = re.findall(r'(\w+\.?\/?\w+)\s+:\s+\d+\((.*?)\)', i)
                    result_list.append(rate[0])
            result_list = [(i[0], float(i[1][:-1].strip())) for i in result_list]

            result_list.sort(key=lambda x: x[1], reverse=True)
            logging.info(result_list)
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
            logging.info("mcs_tx all result: %s", mcs_info)
            result = re.findall(
                #r'TX rate info for [\w:]+:\s*\n(.*?MPDUs AMPDUs AvLen trialP)',
                r'(TX rate info for [\w:]+:\s*\n(?:\s*\[.*?\]\s*\[.*?\]\s*.*\n)+?)'
                r'(?=\s*\[|\s*$)',
                mcs_info,
                re.DOTALL
            )
            #logging.info("mcs_tx rate result: %s", result)
            # result_list = []
            # for i in result:
            #     for j in i.split('\n'):
            #         if ' T ' in j:
            #             temp = re.findall(r'(MCS\d+\/\d+)', j)
            #             result_list.append(temp[0])
            #             break
            # counts = Counter(result_list)
            # return max(counts.keys(), key=counts.get)
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

        # 提取每行的 MCS 和 skipped
        for line in data_lines:
            line = line.strip()
            #logging.info(f"tx_MCS_data_line: {line}")
            if not line:
                continue
            # 匹配 MCSx/y skipped
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
        Wait for for Wi‑Fi service.

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
            logging.info(info)
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
                logging.info('wait for launcher')
                break
        log.terminate()
        log.send_signal(signal.SIGINT)

    def enter_wifi_activity(self) -> None:
        """
        Enter Wi‑Fi activity.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.app_stop(self.SETTING_ACTIVITY_TUPLE[0])
        logging.info('Enter wifi activity')
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

    def find_ssid(self, ssid) -> bool:
        """
        Find ssid.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It sends key events to the device using ADB.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
        """
        self.enter_wifi_activity()
        logging.info('enter activity done')
        time.sleep(1)
        self.wait_and_tap('See all', 'text')
        result = False
        for i in range(100):
            for _ in range(4):
                self.ctl.keyevent(20 if i < 51 else 21)
            if self.find_and_tap(ssid, 'text') != (-1, -1):
                time.sleep(1)
                logging.info('find done')
                self.uiautomator_dump()
                result = True
                break
            else:
                self.uiautomator_dump()
                while 'Network & Internet' in self.get_dump_info():
                    self.keyevent(4)
                    self.uiautomator_dump()
            if i < 51:
                if self.find_element('See fewer', 'text'):
                    break;
            else:
                if self.find_element('Available networks', 'text'):
                    break;
        else:
            result = False
        time.sleep(1)
        assert result, "Can't find ssid"
        logging.info('find ssid done')
        return result

    def wait_keyboard(self):
        """
        Wait for keyboard.

        -------------------------
        It sends key events to the device using ADB.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        for i in range(5):
            self.uiautomator_dump()
            if 'keyboard_area' in self.get_dump_info():  # or \
                break
            else:
                self.keyevent(23)
                time.sleep(2)

    def connect_ssid_via_ui(self, ssid, passwd='', target="192.168.50") -> bool:
        """
        Connect ssid via ui.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It sends key events to the device using ADB.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.
        passwd : Any
            The ``passwd`` parameter.
        target : Any
            The ``target`` parameter.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
        """
        self.find_ssid(ssid)
        self.uiautomator_dump()
        if 'IP address' in self.get_dump_info():
            self.keyevent(4)
            logging.info('already connected')
        elif 'Forget network' in self.get_dump_info():
            self.wait_and_tap('Connect', 'text')
        else:
            if passwd != '':
                for _ in range(5):
                    self.wait_keyboard()
                    logging.info('try to input passwd')
                    self.u().d2(resourceId="com.android.tv.settings:id/guidedactions_item_title").clear_text()
                    time.sleep(1)
                    self.checkoutput(f'input text {passwd}')
                    time.sleep(1)
                    self.uiautomator_dump()
                    if passwd in self.get_dump_info():
                        self.keyevent(66)
                        break
                else:
                    assert passwd in self.get_dump_info(), "passwd not currently"
        logging.info('check status done')
        self.wifi_wait_ip(target=target)
        return True

    def connect_save_ssid(self, ssid, target=''):
        """
        Connect save ssid.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.
        target : Any
            The ``target`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.find_ssid(ssid)
        self.wait_and_tap('Connect', 'text')
        self.wifi_wait_ip(target=target)
        return True

    def forget_ssid(self, ssid):
        """
        Forget ssid.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.find_ssid(ssid)
        self.wait_and_tap('Forget network', 'text')
        self.wait_and_tap('OK', 'text')
        time.sleep(1)

    def wait_ssid_cmd(self, ssid: str) -> None:
        """
        Wait for ssid cmd.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.checkoutput('cmd wifi start-scan')
        scan_list = self.subprocess_run(f'cmd wifi list-scan-results |grep "{ssid}"')
        step = 0
        while ' ' + ssid + ' ' not in scan_list:
            time.sleep(5)
            step += 1
            logging.info('re scan')
            self.subprocess_run('cmd wifi start-scan')
            scan_list = self.subprocess_run(f'cmd wifi list-scan-results |grep "{ssid}"')
            logging.info(f'scan_list {scan_list}')
            if step > 5:
                assert False, "hotspot can't be found"

    def wait_ssid_disapper_cmd(self, ssid: str) -> None:
        """
        Wait for ssid disapper cmd.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        try:
            self.wait_ssid_cmd(ssid)
        except AssertionError as e:
            assert "hotspot can't be found" in e, "hotspot still can be found"

    def change_keyboard_language(self) -> None:
        """
        Change keyboard language.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It sends key events to the device using ADB.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.install_apk('ADBKeyboard.apk')
        self.start_activity(*self.SETTING_ACTIVITY_TUPLE)
        for i in range(5):
            self.keyevent(20)
        self.wait_and_tap('Device Preferences', 'text')
        self.wait_and_tap('Keyboard', 'text')
        self.wait_and_tap('Manage keyboards', 'text')
        self.wait_and_tap('ADB Keyboard', 'text')
        self.wait_and_tap('OK', 'text')
        self.wait_element('ADB Keyboard', 'text')
        self.checkoutput('ime set com.android.adbkeyboard/.AdbIME')
        for i in range(5):
            self.keyevent(4)

    def reset_keyboard_language(self) -> None:
        """
        Reset keyboard language.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.uninstall_apk('com.android.adbkeyboard')

    def add_network(self, ssid, type, passwd='') -> None:
        """
        Add network.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It sends key events to the device using ADB.
        It simulates user input on the device's screen (tap, swipe, or text entry).
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").
        passwd : Any
            The ``passwd`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.enter_wifi_activity()
        time.sleep(2)
        self.wait_and_tap('Add new network', 'text')
        self.checkoutput(f'input text {ssid}')
        time.sleep(2)
        self.keyevent(66)
        self.wait_and_tap(type, 'text')
        if type != 'None':
            if passwd == '':
                raise Exception("Passwd can't be empty")
            self.wait_keyboard()
            time.sleep(2)
            self.uiautomator_dump()
            if 'android.widget.EditText' not in self.get_dump_info():
                self.enter()
            self.text(passwd)
            self.keyevent(66)
        self.wifi_wait_ip()
        return True

    def open_wifi(self) -> None:
        """
        Open Wi‑Fi.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.enter_wifi_activity()
        self.wait_element('Wi-Fi', 'text')
        self.uiautomator_dump()
        if 'Available networks' not in self.get_dump_info():
            self.wait_and_tap('Wi-Fi', 'text')
        self.wait_element('Available networks', 'text')
        self.kill_setting()

    def close_wifi(self) -> None:
        """
        Close Wi‑Fi.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            A value of type ``None``.
        """
        self.enter_wifi_activity()
        self.wait_element('Wi-Fi', 'text')
        self.uiautomator_dump()
        if 'Available networks' in self.get_dump_info():
            self.wait_and_tap('Wi-Fi', 'text')
        self.wait_element('IP settings', 'text')
        self.kill_setting()

    def get_wifi_hw_addr(self) -> str:
        """
        Retrieve Wi‑Fi hw addr.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        str
            A value of type ``str``.
        """
        hw_addr = self.checkoutput('ifconfig wlan0')
        hw_addr = re.findall(r'HWaddr (.*?)  Driver', hw_addr, re.S)
        if hw_addr[0]:
            return hw_addr
        else:
            raise Exception("Can't get hw addr")

    def wait_router(self):
        """
        Wait for router.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        ipaddress = self.checkoutput_term('ifconfig')
        count = 0
        while '192.168.50' not in ipaddress:
            ipaddress = self.checkoutput_term('ifconfig')
            if count > 30:
                raise EnvironmentError("router power status not currently !!")
            count += 1
            time.sleep(3)
        logging.info('Router is power on')

    def playback_youtube(self, sleep_time=60, seek=False, seek_time=3):
        """
        Playback youtube.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It sends key events to the device using ADB.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        sleep_time : Any
            The ``sleep_time`` parameter.
        seek : Any
            The ``seek`` parameter.
        seek_time : Any
            The ``seek_time`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.checkoutput(self.PLAYERACTIVITY_REGU.format(self.VIDEO_TAG_LIST[0]['link']))
            time.sleep(10)
            if seek:
                for _ in range(60 * 24):
                    self.keyevent(23)
                    self.send_event(106, seek_time)
                    self.keyevent(23)
                    time.sleep(30)
                    self.keyevent(23)
                    self.send_event(105, seek_time)
                    self.keyevent(23)
                    time.sleep(30)
            else:
                time.sleep(sleep_time)
            self.home()
        except Exception as e:
            ...

    def set_hotspot(self, ssid='', passwd='', type='', encrypt=''):
        """
        Set hotspot.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It sends key events to the device using ADB.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.
        passwd : Any
            The ``passwd`` parameter.
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").
        encrypt : Any
            The ``encrypt`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if ssid:
            self.wait_and_tap("Hotspot name", "text")
            self.wait_element("android:id/edit", "resource-id")
            self.u().d2(resourceId="android:id/edit").clear_text()
            if ' ' in ssid:
                self.checkoutput(f'input text $(echo "{ssid}" | sed -e "s/ /\%s/g")')
            else:
                self.checkoutput(f'input text {ssid}')
            self.keyevent(66)
            self.wait_element('Hotspot name', 'text')
            assert ssid == self.u().d2(
                resourceId="android:id/summary").get_text(), "ssid can't be set currently"
        if passwd:
            self.wait_and_tap('Hotspot password', 'text')
            self.u().d2(resourceId="android:id/edit").clear_text()
            self.checkoutput(f'input text {passwd}')
            self.uiautomator_dump()
            assert passwd in self.get_dump_info(), "passwd doesn't currently"
            self.keyevent(66)
        if encrypt:
            self.wait_and_tap('Security', 'text')
            self.wait_element(encrypt, 'text')
            self.wait_and_tap(encrypt, 'text')
            self.wait_element('Security', 'text')
        if type:
            self.wait_and_tap('AP Band', 'text')
            self.wait_element(type, 'text')
            self.wait_and_tap(type, 'text')
            self.wait_element('AP Band', 'text')

    def get_hotspot_config(self):
        """
        Retrieve hotspot config.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return self.checkoutput('cat /data/vendor/wifi/hostapd/hostapd_*.conf')

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
        logging.info('device done')

    def get_hwaddr(self):
        """
        Retrieve hwaddr.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        hwAddr = self.checkoutput('ifconfig wlan0')
        hwAddr = re.findall(r'HWaddr (.*?)  Driver', hwAddr, re.S)
        if hwAddr[0]:
            return hwAddr
        else:
            raise Exception("Can't get hw addr")

    def get_wifi_cmd(self, router_info):
        """
        Retrieve Wi‑Fi cmd.

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
        logging.info(f'conn wifi cmd :{cmd}')
        return cmd
