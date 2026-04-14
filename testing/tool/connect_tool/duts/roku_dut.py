"""
Roku control utilities.

This module provides helper functions and a subclass of the ``roku.Roku`` class
to interact with Roku devices programmatically.  It includes logic to look
up the device's IP address from a configuration file, decode bytes while
ignoring errors, and extend the base Roku functionality with additional
commands, screen capture, infrared navigation and media playback helpers.
"""

import logging
import os
import re
import threading
import time
from threading import Thread
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET
from typing import Optional

import requests
from roku import Roku

from testing.tool.connect_tool.transports.serial_tool import serial_tool
from testing.tool.connect_tool.transports.telnet_tool import telnet_tool
from testing.tool.connect_tool.duts.linux import linux
from testing.tool.connect_tool.mixins.dut_mixins import WifiConnectParams
from testing.tool.connect_tool.roku_wpa import roku_wpa
from src.util.constants import load_config
from src.util.constants import RokuConst
from typing import Annotated


def _get_roku_ip() -> Optional[str]:
    """
    Load the latest Roku IP address from the configuration.

    This helper refreshes the configuration using :func:`load_config` and
    returns the IP address defined under the ``connect_type`` section and logs
    the result for debugging purposes.

    Returns
    -------
    Optional[str]
        The configured Roku IP address, or ``None`` if not defined.
    """
    cfg = load_config(refresh=True) or {}
    connect_cfg = cfg.get("connect_type", {})
    linux_cfg = connect_cfg.get("Linux") or {}
    ip = linux_cfg.get("ip")
    logging.info(f"Read ROKU IP: {ip}")
    return ip


lock: Annotated[threading.Lock, "A lock used to synchronize operations across threads"] = threading.Lock()


def decode_ignore(info: Annotated[bytes, "Byte string to decode"]):
    """
    Decode a byte string while gracefully handling invalid sequences.

    The implementation decodes the incoming byte array using UTF‑8, replacing
    invalid bytes with their escape codes.  It then encodes back to a byte
    string with ``unicode_escape`` and decodes again, ignoring any remaining
    errors.  Finally, escaped carriage return, line feed and tab sequences are
    converted to their literal counterparts.

    Parameters
    ----------
    info : bytes
        The input byte sequence to decode.

    Returns
    -------
    str
        A decoded string with problematic bytes replaced and common escape
        sequences normalised.
    """
    info.decode('utf-8', 'backslashreplace_backport') \
        .encode('unicode_escape') \
        .decode('utf-8', errors='ignore') \
        .replace('\\r', '\r') \
        .replace('\\n', '\n') \
        .replace('\\t', '\t')


class roku_ctrl(Roku):
    _instance = None
    # Patterns used to identify notable video status log entries.
    VIDEO_STATUS_TAG = [
        r'display_engine_show: push frame: \d+',
        r'display_thread_func: pop frame: \d+',
    ]
    # Patterns used to identify notable audio status log entries.
    AUDIO_STATUS_TAG = [
        r'get_position:<audio_sink>',
    ]

    AML_SINK_ERROR_TAG = re.compile(r'gst_caps_new_empty failed|gst_pad_template_new failed|'
                                    r'dec ope fail|can not get formats|can not build caps|invalid dw mode \d+|'
                                    r'Bad screen properties string|Bad source window properties string|'
                                    r'Bad window properties string|not accepting format\(\w+\)|'
                                    r'no memory for codec data size \d+|gst_buffer_map failed for codec data|'
                                    r'fail to create thread|V4L2_DEC_CMD_STOP output fail \d+|'
                                    r'postErrorMessage: code \d+ \(\w+\)|meta data is invalid|'
                                    r'Get mate head error|Metadata oversize \d+ > \d+, please check|'
                                    r'VIDIOC_G_FMT error \d+|cap VIDIOC_STREAMOFF error \d+|'
                                    r'v4l_dec_config failed|fail to get visible dimension \d+|'
                                    r'fail to get cropcap \d+|setup capture fail|streamon failed for output: rc \d+ errno \d+|'
                                    r'fail VIDIOC_DQEVENT \d+|VIDIOC_G_PARM error \d+ rc \d+|'
                                    r'cap VIDIOC_DQBUF fail \d+|start avsync error|VIDIOC_STREAMOFF fail ret:\d+|'
                                    r'set secure mode fail|v4l_dec_dw_config failed|set output format \w+ fail|'
                                    r'setup output fail|can not get output buffer \d+|queuing output buffer failed: rc \d+ errno \d+|'
                                    r'start_video_thread failed|dec open fail|uvm open fail|get capture format fail|'
                                    r'reg event fail|start render fail|invalid para \d+ \d+|free index \d+ fail|'
                                    r'queue cb fail \d+|unable to open file \w+|unable to get pts from: \w+|'
                                    r'fail to open \w+|fail to write \w+ to \w+|set volume fail \d+|stream mute fail:\d+|'
                                    r'invalid sync mode \d+|invalid value:\w+|can not get string|wrong ac4_lang:\w+|'
                                    r'wrong ac4_lang2:\w+|wrong ass type \w+|rate \d+.?\d+ fail|no stream opened|'
                                    r'create av sync fail|segment event not received yet|create timer fail|create thread fail|'
                                    r'out buffer fail \d+|wrong size \d+/\d+|asink open failure|fail to load hw:\d+|'
                                    r'OOM|unsupported channel number:\d+|invalid port:\d+|can not open output stream:\d+|'
                                    r'pause failure:\d+|parse ac4 fail|frame too big \d+|header too big \d+|'
                                    r'trans mode write fail \d+/\d+|drop data \d+/\d+|null pointer')

    def __init__(self, ip: Optional[str] = None, *, telnet=None, serial=None):
        """
        Initialize the class instance, set up internal state and construct UI elements if needed.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if ip is None:
            ip = _get_roku_ip()
        super().__init__(ip)
        self.ip = ip
        self.telnet = telnet
        self.ptc_size, self.ptc_mode = '', ''
        self.current_target_array = 'launcher'
        self._layout_init()
        self.ir_current_location = ''
        self.logcat_check = False
        self._ser = serial

        logging.info('roku init done')

    def __setattr__(self, key, value):
        """
        Execute the setattr   routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if key == 'ir_current_location':
            if 'amp;' in value:
                value = value.replace('amp;', '')
        self.__dict__[key] = value

    def checkoutput(self, cmd, wildcard=""):
        return self.telnet.checkoutput(cmd, wildcard=wildcard)

    def _layout_init(self):
        """
        Execute the layout init routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.layout_media_player_home = [['All', 'Video', 'Audio', 'Photo']]
        self.layout_media_player_help_setting = [['Help'], ['Request media type at startup - [On]'],
                                                 ['Lookup album art on Web - [On]'], ['Display format - [Grid]'],
                                                 ['Autorun - [On]'], ['OK']]

    def _focus_from_secret_endpoint(self) -> Optional[str]:
        """Query the secret focus endpoint and return the currently focused label."""
        for _ in range(5):
            url = f'http://{self.ip}:8060/query/focus/secret'
            response = requests.get(url).content.decode('utf-8')
            if 'RoScreenWrapper' in response:
                self.home(time=1)
                continue
            if 'SGScreen.RMPScene.ComponentController_0.ViewManager_0.ViewStack_0.MediaView_0.Video_' in response:
                logging.debug("Skip focus lookup on media view stack")
                break
            if 'SGScreen.RMPScene.ComponentController_0.ViewManager_0.ViewStack_0.GridView_0.RenderableNode_0.ZoomRowList_0.RenderableNode_' in response:
                logging.debug("Skip focus lookup on zoom row list")
                break
            focused = re.findall(r'<text>(.*?)</text>', response)
            if focused:
                return focused[0]
        return None

    def _focus_from_xml_tree(self, filename: str) -> Optional[str]:
        """Extract the focused label by inspecting the current screen XML tree."""
        root = self._get_xml_root(filename)
        node_list = []
        for child in root:
            for node in child.iter():
                label = self._extract_label_from_node(node)
                if label:
                    return label
                if node.tag == 'StandardGridItemComponent' and node.attrib.get('focused') == 'true':
                    node_list.append(node)
        if node_list:
            layout = node_list[-1].find('LayoutGroup')
            if layout is not None:
                label_node = layout.find('Label')
                if label_node is not None and label_node.attrib.get('text'):
                    return label_node.attrib['text']
        return None

    def _extract_label_from_node(self, node) -> Optional[str]:
        """Return the text of the focused node if available."""
        if node.tag == 'ItemDetailsView':
            for child in node.iter('Label'):
                if child.attrib.get('name') == 'title' and child.attrib.get('text'):
                    text = child.attrib['text']
                    return text.split('|')[0].strip() if '|' in text else text
        if (
            node.tag == 'RenderableNode'
            and node.attrib.get('focused') == 'true'
            and node.attrib.get('uiElementId') != 'overlay-root'
        ):
            for tag in ('RadioButtonItem', 'AVRadioButtonItem', 'LabelListNativeItem'):
                container = node.find(tag)
                if container is not None:
                    scrolling = container.find('ScrollingLabel')
                    if scrolling is not None:
                        label = scrolling.find('Label')
                        if label is not None and label.attrib.get('text'):
                            return label.attrib['text']
        if node.tag == 'Button' and node.attrib.get('focused') == 'true':
            label = node.find('Label')
            if label is not None:
                return label.attrib.get('text')
        return None

    def __getattr__(self, name):
        """
        Dynamically resolve Roku remote commands and expose them as callables.

        Each attribute lookup is translated into a callable that ultimately
        delegates to :meth:`_dispatch_roku_command`, keeping the command
        resolution logic in a single place.
        """

        def command(*args, **kwargs):
            self._dispatch_roku_command(name, args, kwargs)

        return command

    def _dispatch_roku_command(self, name, args, kwargs):
        """Execute a Roku remote command or sensor input."""
        if name in RokuConst.SENSORS:
            keys = [f"{name}.{axis}" for axis in ("x", "y", "z")]
            params = dict(zip(keys, args))
            self.input(params)
        elif name == "literal":
            for char in args[0]:
                path = f"/keypress/{RokuConst.COMMANDS[name]}_{quote_plus(char)}"
                self._post(path)
        elif name == "search":
            path = "/search/browse"
            params = {k.replace("_", "-"): v for k, v in kwargs.items()}
            self._post(path, params=params)
        else:
            if len(args) > 0 and args[0] in {"keydown", "keyup"}:
                path = f"/{args[0]}/{RokuConst.COMMANDS[name]}"
                logging.info("key %s", args[0])
            else:
                path = f"/keypress/{RokuConst.COMMANDS[name]}"
                logging.info("Press key %s", RokuConst.COMMANDS[name])
            try:
                self._post(path)
            except Exception:
                logging.warning("Can't touch roku server")
        if "time" in kwargs:
            time.sleep(kwargs["time"])

    def capture_screen(self, filename):
        """
        Execute the capture screen routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info("\rStart to capture screen ....\r")
        para = {'param-image-type': 'jpeg'}
        url = "http://%s:8060/capture-screen/secret" % (self.ip)
        r = requests.get(url, json=para)
        response = r.content

        with open(file=filename, mode='wb') as handle:
            handle.write(response)
            handle.close()

    def load_array(self, array_txt):
        """
        Load  array from persistent storage.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        with open(os.getcwd() + f'/config/roku/layout/{array_txt}') as f:
            info = f.readlines()
            arr = [i.strip().split(',') for i in info]
        return arr

    def get_ir_focus(self, filename='dumpsys.xml', secret=False):
        """
        Retrieve the ir focus attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        focus = None
        if not secret:
            focus = self._focus_from_secret_endpoint()
        if focus is None:
            focus = self._focus_from_xml_tree(filename=filename)
        if focus:
            self.ir_current_location = focus
            return focus
        return ''

    def _get_media_process_bar(self, filename='dumpsys.xml'):
        """
        Retrieve the media process bar attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        process_index = '0:0'
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == 'TrickPlayBar' and not child_1.attrib.get('name'):
                    process_index = child_1.find('Label').attrib['text']
                    logging.info(process_index)
                    logging.info(int(process_index.split(':')[0]) * 60 + int(process_index.split(":")[1]))
                    return int(process_index.split(':')[0]) * 60 + int(process_index.split(":")[1])

    def get_ir_index(self, name, item, fuz_match=False):
        """
        Retrieve the ir index attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        target_array = self.get_launcher_element(item)
        for i in target_array:
            for y in i:
                if fuz_match:
                    if name in y:
                        return (target_array.index(i), i.index(y)), len(i)
                else:
                    if name == y:
                        return (target_array.index(i), i.index(y)), len(i)

        logging.debug(f"Can't find such this widget {name}")
        return None, None

    def _move_vertical(self, current_row: int, target_row: int, total_rows: int) -> None:
        """Move the focus vertically between rows."""
        step = abs(target_row - current_row)
        if step == 0 or total_rows <= 0:
            return
        wrap_steps = current_row + total_rows - target_row
        if step > total_rows / 2:
            for _ in range(wrap_steps):
                self.up(time=1)
        else:
            for _ in range(step):
                self.down(time=1)

    def _move_horizontal(self, current_col: int, target_col: int, row_length: int) -> None:
        """Move the focus horizontally within a row."""
        step = abs(target_col - current_col)
        if step == 0 or row_length <= 0:
            return
        wrap_steps = current_col + row_length - target_col
        if step > row_length / 2:
            for _ in range(wrap_steps):
                self.left(time=1)
        else:
            for _ in range(step):
                self.left(time=1)

    def ir_navigation(self, target, item, secret=False, fuz_match=False):
        """
        Execute the ir navigation routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info(f'navigation {target}')
        self.get_ir_focus(secret=secret)
        array = self.get_launcher_element(item)
        target_idx, _ = self.get_ir_index(target, item, fuz_match)

        current_index, _ = self.get_ir_index(self.ir_current_location, item, fuz_match=fuz_match)
        target_index, list_len = self.get_ir_index(target, item, fuz_match=fuz_match)
        array = self.get_launcher_element(item)
        if current_index and target_index and list_len:
            x_step = abs(target_index[0] - current_index[0])
            y_step = abs(target_index[1] - current_index[1])
            if x_step == 0 and y_step == 0:
                logging.info(f'navigation {target} done')
                return True

            self._move_vertical(current_index[0], target_index[0], len(array))
            self._move_horizontal(current_index[1], target_index[1], list_len)

        return self.ir_navigation(target, item, secret=secret, fuz_match=fuz_match)

    def ir_enter(self, target, item, secret=False, fuz_match=False):
        """
        Execute the ir enter routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.ir_navigation(target, item, secret=secret, fuz_match=fuz_match)
        self.select(time=2)

    def media_playback(self, target, array):
        """
        Execute the media playback routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.ir_enter(target, array)
        time.sleep(1)
        info = self._get_screen_xml()
        if 'Play from beginning' in info:
            self.down(time=1)
        self.select(time=1)

    def _get_screen_xml(self, filename='dumpsys.xml'):
        """
        Retrieve the screen xml attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        r, focused = '', ''

        for _ in range(5):
            url = f"http://{self.ip}:8060/query/screen/secret"
            r = requests.get(url).content.decode('utf-8')
            if 'Internal error' not in r:
                break
        with open(file=filename, mode='w', encoding='utf-8') as handle:
            handle.write(r)
        return r

    def _get_xml_root(self, filename='dumpsys.xml'):
        """
        Get the xml root attribute from the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._get_screen_xml(filename)
        tree = ET.parse(filename)
        return tree.getroot()

    def wait_for_element(self, element, timeout=60):
        """
        Execute the wait for element routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        start = time.time()
        while element not in self._get_screen_xml():
            time.sleep(1)
            if time.time() - start > timeout:
                logging.warning(f"Can't loading {element}")
                break

    def get_u_disk_file_distribution(self, filename='dumpsys.xml'):
        """
        Retrieve the u disk file distribution attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        node_list, temp = [], []
        current_file = ''
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == 'StandardGridItemComponent':
                    index = int(child_1.attrib['index'])
                    for child_2 in child_1.iter():
                        # if child_2.tag == 'Poster' and 'poster_' in child_2.attrib['uri']:
                        # 	type = re.findall(r'poster_(.*?)_fhd', child_2.attrib['uri'])[0]
                        if child_2.tag == 'Label' and child_2.attrib['name'] == 'line1':
                            if index == 0:
                                if temp:
                                    node_list.append(temp)
                                temp = []
                            temp.append(child_2.attrib['text'])
        if temp not in node_list:
            node_list.append(temp)
        self.media_player_dumpsys = node_list
        logging.info(f'layout info {self.media_player_dumpsys}')
        return node_list

    def get_launcher_element(self, target_element):
        """
        Retrieve the launcher element attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        node_list = []
        current_file = ''
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == target_element:
                    index = int(child_1.attrib['index'])
                    for child_2 in child_1.iter():
                        if child_2.tag == 'Label' and 'renderPass' not in child_2.attrib:
                            text = child_2.attrib['text']
                            if text and [text] not in node_list:
                                node_list.append([child_2.attrib['text']])
        return node_list

    def switch_ir(self, status):
        """
        Execute the switch ir routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        ir_command = {
            'on': 'echo 0xD > /sys/class/remote/amremote/protocol',
            'off': 'echo 0x2 > /sys/class/remote/amremote/protocol'
        }
        logging.info(f'Set roku ir {status}')
        self.checkoutput(ir_command[status])

    def set_display_size(self, size):
        """
        Set the display size attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for _ in range(9):
            if self.get_ir_focus() == size:
                self.ptc_size = size
                self.select(time=1)
                break
            self.down(time=1)
            time.sleep(1)
        else:
            logging.warning(f"Can't set display size into {size}")
        logging.info(f'Current size : {size}')

    def set_display_mode(self, mode):
        """
        Set the display mode attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for _ in range(9):
            if self.get_ir_focus() == mode:
                self.ptc_mode = mode
                self.select(time=1)
                break
            self.down(time=1)
            time.sleep(1)
        else:
            logging.warning(f"Can't set display mode into {mode}")
        logging.info(f'Current mode : {mode}')

    def set_picture_mode(self, mode):
        """
        Set the picture mode attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.info(time=3)
        # if pytest.light_sensor:
        # 	res = pytest.light_sensor.count_kpi(0, roku_lux.get_note('setting_white')[pytest.panel])
        # 	if not res:
        self.info()
        self.down(time=1)
        self.select(time=1)
        self.down(time=1)
        for i in mode:
            logging.info(f'Try to set picture mode into {i}')
            self.select(time=1)
            if self.ptc_mode != i:
                self.set_display_mode(i)
        self.back(time=1)
        self.back(time=1)

    def set_picture_size(self, size):
        """
        Set the picture size attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.info(time=3)
        # if pytest.light_sensor:
        # 	res = pytest.light_sensor.count_kpi(0, roku_lux.get_note('setting_white')[pytest.panel])
        # 	if not res:
        self.info()
        self.down(time=1)
        self.select(time=1)
        self.down(time=1)
        self.down(time=1)
        self.select(time=1)
        for _ in range(6):
            self.down(time=1)
        for i in size:
            logging.info(f'Try to set picture size into {i}')
            self.select(time=1)
            if self.ptc_size != i:
                self.set_display_size(i)
        self.back(time=1)
        self.back(time=1)
        self.back(time=1)

    def set_caption_status(self, status):
        """
        Set the caption status attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if status not in ['On always', 'On replay', 'On mute', 'Off']:
            raise ValueError(f"Does't support this {status}")
        self.info(time=3)
        for _ in range(3):
            self.down(time=1)
        self.select(time=1)
        self.select(time=1)
        for _ in range(6):
            if self.get_ir_focus() != status:
                self.down(time=1)
                continue
            self.select(time=1)
            break
        else:
            logging.warning(f"Can't set caption to {status}")

    def set_caption(self, language):
        """
        Set the caption attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for _ in range(3):
            if 'TV settings' in self._get_screen_xml():
                break
            self.info(time=3)
        for _ in range(3):
            self.down(time=1)
        self.select(time=1)
        self.down(time=1)
        self.select(time=1)
        for _ in range(10):
            index = self.get_ir_focus()
            logging.info(f'index {index}')
            if index != language:
                self.down(time=1)
                continue
            self.select(time=1)
            break
        else:
            logging.warning(f"Can't set language {language}")

    def get_dmesg_log(self):
        """
        Retrieve the dmesg log attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        with open('dmesg.log', 'a') as f:
            info = self.checkoutput('dmesg')
            f.write(info)
        self.checkoutput('dmesg -c')

    def get_kernel_log(self, filename='kernel.log'):
        """
        Retrieve the kernel log attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        def run_logcast(filename):
            """
            Execute the run logcast routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            while True:
                info = tl.tn.read_very_eager()
                if info != b'':
                    with open(filename, 'a', encoding='utf-8') as f:
                        try:
                            info = info.decode('utf-8').replace('\r\n', "\n")
                        except Exception as e:
                            info = ''
                        f.write(info)

        logging.info('start telnet 8080 to caputre kernel log ')
        tl = telnet_tool(self.ip, 'sandia')
        info = tl.checkoutput(f'telnet {self.ip} 8080', wildcard=b'onn. Roku TV')
        tl.checkoutput('logcast start')
        time.sleep(1)
        tl.checkoutput('\x03')  # ,wildcard=b'Console')
        time.sleep(1)
        tl.checkoutput('\x1A')
        time.sleep(1)
        tl.checkoutput(f'telnet {self.ip} 8070')
        t = Thread(target=run_logcast, args=(filename,))
        t.daemon = True
        t.start()

    def analyze_logcat(self, re_list, timeout=10):
        """
        Execute the logcat analysis routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        import copy

        target_list = copy.deepcopy(re_list)
        self.checkoutput('\x03')
        self.checkoutput('\x03')
        self.checkoutput('logcat')
        self._capture_logcat_stream(timeout)

        with open('logcat.log', 'r') as handle:
            for line in handle.readlines():
                if not target_list:
                    return
                if re.findall(target_list[0], line):
                    logging.info(line.strip())
                    target_list.pop(0)
        assert False, "Can't catch target log"

    def _capture_logcat_stream(self, timeout: int) -> None:
        """Capture logcat output for the specified timeout window."""
        start = time.time()
        buffer: list[str] = []
        while time.time() - start < timeout:
            data = self.telnet.tn.read_eager()
            if not data:
                continue
            try:
                decoded = data.decode()
            except Exception:
                continue
            if '\n' in decoded:
                lines = decoded.split('\n')
                for entry in lines[:-1]:
                    buffer.append(entry)
                    info = ''.join(buffer)
                    with open('logcat.log', 'a', encoding='utf-8') as handle:
                        handle.write(info)
                    buffer.clear()
                buffer.append(lines[-1])
            else:
                buffer.append(decoded)

    def catch_err(self, filename, tag_list):
        """
        Execute the catch err routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info(f'Start to catch err. Logfile :{filename}')
        with open(filename, 'r') as f:
            info = f.readlines()
        for i in info:
            res = tag_list.findall(i)
            if res:
                logging.warning(res)
        logging.info('Catch done')

    def shutdown(self):
        """
        Execute the shutdown routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        count = 0
        while self.light_sensor.check_backlight():
            # shut down the dut before test
            self.send('power', 10)
            if count > 5:
                raise EnvironmentError("Pls check ir control")

    def get_hdmirx_info(self, **kwargs):
        """
        Retrieve the hdmirx info attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info(f'hdmirx for expect : {kwargs}')

        snapshot = self._fetch_hdmirx_snapshot()
        logging.info(snapshot)
        info_lines = [line.strip() for line in snapshot.split('\n') if self._is_hdmirx_attribute(line)]
        logging.info(' ,'.join(info_lines[:5]))
        logging.info(' ,'.join(info_lines[5:]))
        result = {line.split(':')[0].strip(): line.split(':')[1].strip() for line in info_lines}
        for key, value in kwargs.items():
            lookup = {'depth': 'Color Depth', 'space': 'Color Space', 'frame': 'Frame Rate'}.get(key, key)
            if lookup not in result:
                logging.warning("Missing key %s in HDMI info", lookup)
                return False
            if lookup == 'Frame Rate':
                if int(result[lookup]) not in range(*value):
                    logging.warning('%s not in expect , should in %s', result[lookup], value)
                    return False
            elif result[lookup] != value:
                logging.warning('%s not in expect , should be %s', result[lookup], value)
                return False
        return True

    def _is_hdmirx_attribute(self, line: str) -> bool:
        """Return True when the line matches a known HDMI info attribute."""
        pattern = (
            r'Hactive|Vactive|Color Depth|Frame Rate|TMDS clock|HDR EOTF|Dolby Vision|'
            r'HDCP Debug Value|HDCP14 state|HDCP22 state|Color Space'
        )
        return bool(re.findall(pattern, line))

    def _fetch_hdmirx_snapshot(self) -> str:
        """Poll the HDMI RX info sysfs node and return its contents."""
        for _ in range(3):
            try:
                info = self.checkoutput('cat /sys/class/hdmirx/hdmirx0/info')
            except Exception:
                info = ''
            if 'HDCP1.4 secure' in info:
                return info
            time.sleep(2)
        return info

    def enter_media_player(self):
        """
        Execute the enter media player routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self['2213'].launch()
        count = 0
        while True:
            if 'Media Type Selection' in self._get_screen_xml():
                logging.info('enter done')
                return
            self.back(time=1)
            if count > 5:
                logging.warning("Can't open media player")
            time.sleep(3)

    def check_udisk(self):
        """
        Execute the check udisk routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        return 'Select Media Device' in self._get_screen_xml()

    def enter_bt(self):
        """
        Execute the enter bt routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.ir_enter('Settings', 'LabelListNativeItem')
        self.ir_enter('Remotes & devices', 'ArrayGridItem')
        self.ir_enter('Wireless headphones', 'ArrayGridItem')
        self.select(time=1)

    def enter_wifi(self):
        """
        Execute the enter wifi routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.home(time=1)
        self.ir_enter('Settings', 'LabelListNativeItem')
        self.ir_enter('Network', 'ArrayGridItem')

    def check_conn(self):
        """
        Execute the check conn routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.enter_wifi()
        self.ir_enter('Check connection', 'LabelListItem')
        for _ in range(20):
            if 'Connection check was successful' in self._get_screen_xml():
                return True
            time.sleep(2)
        else:
            return False

    def setup_conn(self):
        """
        Execute the setup conn routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.enter_wifi()
        self.ir_enter('Set up connection', 'LabelListItem')
        if self.get_ir_focus() != 'Wireless':
            self.down()
        logging.info('check wireless')
        assert 'Wireless' == self.get_ir_focus(), "Can't found wireless "
        self.select()
        self.select()
        for _ in range(20):
            time.sleep(1)
            if 'Scan again to see all network' in self._get_screen_xml():
                logging.info('Wi-Fi list catched')
                return
        else:
            assert False, "Can't load wifi scan list"

    def wifi_scan(self, ssid):
        """
        Execute the wifi scan routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        def wait():
            """
            Execute the wait routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            for _ in range(20):
                time.sleep(1)
                if 'Looking for wireless networks...' not in self._get_screen_xml():
                    break

        self.setup_conn()
        if self.get_ir_focus() == "Set up connection":
            self.select(time=2)
        time.sleep(2)
        for i in range(5):
            for info in self.get_launcher_element('ArrayGridItem'):
                logging.info(info[0])
                if ssid in info[0]:
                    logging.info('Find target ssid')
                    return True
            try:
                if i == 0:
                    self.ir_enter('Scan again to see all networks', 'ArrayGridItem', fuz_match=True)
                    wait()
                else:
                    self.ir_enter('Scan again', 'ArrayGridItem', fuz_match=True)
                    wait()
            except TypeError:
                ...
        else:
            logging.info(f"Can't find target ssid {ssid}")
            return False

    @property
    def ser(self):
        """
        Execute the ser routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if self._ser is None:
            raise RuntimeError(
                "The 'ser' property of roku_ctrl was accessed before it was initialized. "
                "This usually means the parent 'roku' DUT object was not created with a valid 'serial' argument."
            )
        return self._ser

    def wifi_conn(self, ssid, pwd='', band=5):
        """
        Execute the wifi conn routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        found = self.wifi_scan(ssid)
        if not found:
            logging.error(f"Target SSID {ssid} not found in scan results!")
            #return ""
        self.ir_enter(ssid, 'ArrayGridItem', fuz_match=True) #找到的SSID配置
        time.sleep(5)
        if 'Recommended network found' in self._get_screen_xml():
            if band == 2:
                self.down()
            self.select()
        if 'Enter the network password for' in self._get_screen_xml():
            if 'Connect' == self.get_ir_focus():
                self.down()
                self.select()
                self.up()
                self.up()
            self.literal(pwd)
            time.sleep(10)
            for _ in range(4):
                self.down()


        self.select()
        for _ in range(20):
            time.sleep(3)
            ip = self.ser.get_ip_address('wlan0')
            if ip:
                self.ip = ip
                Roku.__init__(self, ip)
                logging.info(f'roku ip {self.ip}')
                break
        else:
            logging.error("Failed to obtain IP address after 60 seconds!")
            return ""
        self.home(time=3)
        self.home(time=3)
        self.home(time=3)
        return ip

    def flush_ip(self):
        """
        Execute the flush ip routine.
        """
        ip = self.ser.get_ip_address('wlan0')
        if not ip:
            return ""
        self.ip = ip
        # Refresh the HTTP client in the parent Roku class
        Roku.__init__(self, ip)
        logging.info(f'roku ip refreshed to {self.ip}')
        return ip

    def remote(self, button_list, idle=1):
        """
        Execute the remote routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        button_dict = {'h': 'home', 'p': 'play', 's': 'select', 'l': 'left', 'r': 'right', 'd': 'down', 'u': 'up',
                       'b': 'back', 'i': 'info'}
        for i in button_list:
            if i in RokuConst.COMMANDS:
                getattr(self, button_dict[i])(time=idle)
            else:
                logging.info(f'{i} not in button_dict .pls check again')


class roku(linux):
    def __init__(self, telnet_ip: str, *, serial=None) -> None:
        super().__init__(serial=serial, telnet=telnet_tool(telnet_ip))
        self.roku = roku_ctrl(telnet_ip, telnet=self.telnet, serial=serial)
        # if serial is not None:
        #     self.roku._ser = serial
        self.wpa = roku_wpa(self.roku.ser)
        logging.info(f"[DUT INIT] DUT created with serial: {'YES' if serial else 'NO'}")
        logging.info(f"[DUT INIT] roku_ctrl._ser is None: {self.roku._ser is None}")

    def _refresh_ip(self, ip: str) -> None:
        """Refresh the internal state with a new IP address."""
        self.telnet = telnet_tool(ip)
        self.dut_ip = ip
        # --- 【修复】更新现有 roku_ctrl 对象的 ip 和 telnet，而不是替换它 ---
        self.roku.ip = ip
        self.roku.telnet = self.telnet
        # Also, refresh the parent Roku class's HTTP client target
        Roku.__init__(self.roku, ip)

    def flush_ip(self) -> bool:
        ip = self.roku.flush_ip()
        if not ip:
            return False
        self._refresh_ip(ip)
        return True

    def wifi_connect(self, ssid, password="", security=""):
        """Implement the standard DUT interface for Roku."""
        band = 5 if "5G" in ssid else 2
        ip = self.roku.wifi_conn(ssid=ssid, pwd=password, band=band)
        return bool(ip and ip != "")

    def _wifi_connect_impl(self, params: WifiConnectParams) -> bool:
        # Todo 逻辑待优化
        # ip = self.roku.wifi_conn(params.ssid, params.password)
        # if not ip:
        #     return False
        # self._refresh_ip(ip)
        return True

    def _wifi_scan_impl(self, ssid: str, *, attempts: int, scan_wait: int, interval: float) -> bool:
        return self.roku.wifi_scan(ssid)

    def _wifi_forget_impl(self):
        return None

    def _get_mcs_tx_impl(self):
        # Roku devices may not support the default iwpriv commands; the telnet
        # transport provides the best-effort MCS hooks when available.
        telnet = getattr(self, "telnet", None)
        if telnet is not None and hasattr(telnet, "get_mcs_tx"):
            return telnet.get_mcs_tx()
        return None

    def _get_mcs_rx_impl(self):
        telnet = getattr(self, "telnet", None)
        if telnet is not None and hasattr(telnet, "get_mcs_rx"):
            return telnet.get_mcs_rx()
        return None
