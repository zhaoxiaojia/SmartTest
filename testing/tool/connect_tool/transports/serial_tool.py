"""
This module implements serial tool functionality for the ``connect_tool`` package.

It provides a ``serial_tool`` class which wraps low‑level ``pyserial`` primitives
to manage a serial connection, read and write data, and collect logs from a
device under test.  The module defines helper methods for connection recovery,
log saving, keyword detection and other convenience operations used by the
test harness.  All methods expose docstrings to describe their purpose and
parameters in English.
"""

import logging
import re, queue
import signal
import time
from time import sleep
import threading

import pytest
import serial
from queue import Queue, Empty
from typing import Annotated
import uuid

_serial_tool_instances = {}
class serial_tool:
    """
    Serial tool.

    -------------------------
    It logs information for debugging or monitoring purposes.
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """


    def __init__(self, serial_port='', baud='', log_file="kernel_log.txt", enable_log=True):
        """
        Init.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        serial_port : Any
            The ``serial_port`` parameter.
        baud : Any
            The ``baud`` parameter.
        log_file : Any
            The ``log_file`` parameter.
        enable_log : Any
            The ``enable_log`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """

        logging.info("!!! SerialTool.__init__ IS BEING CALLED !!!")
        self.serial_port = serial_port or pytest.config.get('serial_port')['port']
        self.baud = baud or pytest.config.get('serial_port')['baud']
        logging.info(f'port {self.serial_port} baud {self.baud}')
        logging.debug(f'__init__: Attempting to open serial with port={self.serial_port}, baud={self.baud}')
        self.ethernet_ip = ''
        self.uboot_time = 0
        self.ser = None
        self._open_serial()
        self.status = self._is_serial_open()
        logging.info('Serial port open status: %s', self.status)

        self.log_file = log_file
        self.keyword_flags = {}  # Dictionary storing detection flags for keywords
        self.keyword_flags_lock = threading.Lock()  # Lock used for thread safety

        self._rx_queue = Queue()  # Thread‑safe receive buffer
        self._stop_flag = threading.Event()
        if enable_log:
            self.log_thread = threading.Thread(
                target=self._save_and_detect_log, daemon=True)
            self.log_thread.start()

    def _open_serial(self):
        """
        Open serial.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.ser = serial.Serial(self.serial_port, self.baud,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE,
                                     stopbits=serial.STOPBITS_ONE,
                                     xonxoff=False,
                                     rtscts=False,
                                     dsrdtr=False,
                                     timeout=1)
            logging.info('Serial port %s-%s opened', self.serial_port, self.baud)
            logging.info(f'_open_serial: Successfully created serial object: {self.ser}')
        except serial.serialutil.SerialException as e:
            logging.error('Failed to open serial port %s-%s: %s',
                          self.serial_port, self.baud, e)
            logging.debug(f'_open_serial: Failed to create serial object, set to None. Exception: {e}')
            error_msg = f'Failed to open serial port {self.serial_port}-{self.baud}: {e}'
            self.ser = None
            raise RuntimeError(error_msg) from e

    def _is_serial_open(self):
        """
        Is serial open.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if not self.ser:
            return False
        attr = getattr(self.ser, 'is_open', None)
        if isinstance(attr, bool):
            return attr
        if callable(attr):
            try:
                return bool(attr())
            except Exception:
                return False
        legacy = getattr(self.ser, 'isOpen', None)
        if callable(legacy):
            try:
                return bool(legacy())
            except Exception:
                return False
        return False

    def exec_command(self, cmd: str, timeout: float = 10.0) -> str:
        if self.ser is None:
            raise RuntimeError("Serial port is not open.")

        # 1. 生成唯一标记
        marker_start = f"CMD_START_{uuid.uuid4().hex[:8]}"
        marker_end = f"CMD_END_{marker_start.split('_')[-1]}"

        # 2. 发送复合命令
        full_cmd = f'echo "{marker_start}"; {cmd}; echo "{marker_end}"'
        self.write(full_cmd)

        output = ""
        start_time = time.time()

        # 3. 读取所有数据直到超时
        while time.time() - start_time < timeout:
            try:
                data = self._rx_queue.get(timeout=0.5)
                output += data.decode('utf-8', errors='ignore')
                if marker_end in output:
                    break
            except queue.Empty:
                continue

        # 4. 提取目标命令的输出
        try:
            start_idx = output.index(marker_start) + len(marker_start)
            end_idx = output.index(marker_end)
            result = output[start_idx:end_idx].strip()
            # 移除可能的命令回显 (optional)
            if result.startswith(cmd):
                result = result[len(cmd):].lstrip('\r\n')
            return result
        except ValueError:
            raise RuntimeError(f"Command '{cmd}' did not complete within {timeout}s. Output: {output[-500:]}")

    def _ensure_connection(self, retries=3, interval=2):
        """
        Ensure connection.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        retries : Any
            The ``retries`` parameter.
        interval : Any
            The ``interval`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._is_serial_open():
            self.status = True
            return True

        for attempt in range(1, retries + 1):
            logging.warning('Serial connection lost, retrying to connect (%s/%s)',
                            attempt, retries)
            if self.ser:
                try:
                    self.ser.close()
                except serial.serialutil.SerialException as e:
                    logging.debug('Error closing serial during reconnect: %s', e)
                finally:
                    logging.debug(f'_ensure_connection: Set self.ser to None before reopening.')
                    self.ser = None
            self._open_serial()
            if self._is_serial_open():
                self.status = True
                logging.info('Serial reconnected successfully')
                return True
            sleep(interval)

        self.status = False
        raise RuntimeError('Failed to reconnect serial port after multiple attempts')

    def _save_and_detect_log(self):
        """
        Save and detect log.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with open(self.log_file, 'w', encoding='utf-8', errors="ignore") as file:
            while not self._stop_flag.is_set():
                if not self._is_serial_open():
                    time.sleep(0.5)
                    continue
                data = self.ser.read(1024)  # Do not decode immediately
                if not data:
                    continue
                chunk = data.decode("utf-8", errors="ignore")
                chunk = chunk.replace("\r\n", "\n").replace("\r", "\n")
                file.write(chunk)
                self._rx_queue.put(data)  # Feed data to the business thread
                with self.keyword_flags_lock:
                    for kw in list(self.keyword_flags):
                        if kw.encode() in data:
                            self.keyword_flags[kw] = True

    def start_keyword_detection(self, keyword):
        """
        Start keyword detection.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with self.keyword_flags_lock:
            self.keyword_flags[keyword] = False

    def is_keyword_detected(self, keyword):
        """
        Is keyword detected.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        with self.keyword_flags_lock:
            logging.debug("get %s : %s", keyword, self.keyword_flags.get(keyword))
            return self.keyword_flags.get(keyword, False)

    def clear_keyword(self, keyword):
        """
        Clear keyword.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with self.keyword_flags_lock:
            if keyword in self.keyword_flags:
                del self.keyword_flags[keyword]

    def get_ip_address(self, inet='wlan0', count=10):
        """Retrieve ip address."""
        if self.ser is None:
            logging.error("get_ip_address called, but self.ser is None!")
            return None

        for attempt in range(count):
            try:
                # --- 清空队列中的旧数据 ---
                while not self._rx_queue.empty():
                    try:
                        self._rx_queue.get_nowait()
                    except Empty:
                        break

                # --- 发送命令 ---
                logging.info("[GET_IP] Sending 'echo HELLO' to test.")
                self.write('echo HELLO')
                time.sleep(1)

                # --- 从 _rx_queue 读取 echo 响应 ---
                echo_response = ''
                start_time = time.time()
                while time.time() - start_time < 3:
                    try:
                        data = self._rx_queue.get(timeout=0.5)
                        chunk = data.decode('utf-8', errors='ignore')
                        echo_response += chunk
                        if 'HELLO' in chunk:
                            break
                    except Empty:
                        continue

                logging.info(f"[GET_IP] Echo response: {repr(echo_response)}")
                if 'HELLO' not in echo_response:
                    logging.warning("[GET_IP] Echo test failed!")

                # --- 发送 ifconfig 命令 ---
                command = f'ifconfig {inet}'
                logging.info(f'[GET_IP] Sending: {command}')
                self.write(command)
                time.sleep(2)

                # --- 从 _rx_queue 读取 ifconfig 响应 ---
                ip_info = ''
                start_time = time.time()
                while time.time() - start_time < 10:
                    try:
                        data = self._rx_queue.get(timeout=1)
                        chunk = data.decode('utf-8', errors='ignore')
                        ip_info += chunk
                        # 如果看到 TX bytes 或者新提示符，可以提前结束
                        if 'TX bytes:' in chunk or 'console:/ $' in chunk:
                            break
                    except Empty:
                        break  # Timeout, no more data

                logging.info(f"[GET_IP] Full response:\n{ip_info}")

                # --- 解析 IP ---
                ip_match = re.search(r'inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)', ip_info)
                if ip_match:
                    ipaddress = ip_match.group(1)
                    logging.info(f'[GET_IP] Found IP: {ipaddress}')
                    return ipaddress

            except Exception as e:
                logging.exception(f'[GET_IP] Error on attempt {attempt + 1}: {e}')

            time.sleep(2)

        logging.error('[GET_IP] Failed after all attempts')
        return None

    def write_pipe(self, command):
        """
        Write pipe.

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
        try:
            self.ser.write(bytes(command + '\r', encoding='utf-8'))
        except (serial.serialutil.SerialException, AttributeError, OSError) as err:
            logging.error('Serial write failed for command %s: %s', command, err)
            self._ensure_connection()
            self.ser.write(bytes(command + '\r', encoding='utf-8'))
        logging.info(f'=> {command}')
        sleep(0.1)
        data = self.recv()
        logging.debug(data.strip())
        return data

    def enter_uboot(self):
        """
        Enter uboot.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.write('reboot')
        start = time.time()
        info = ''
        while time.time() - start < 30:
            logging.debug(f'uboot {self.ser.read(100)}')
            try:
                info = self.ser.read(100).decode('utf-8')
                logging.info(info)
            except UnicodeDecodeError as e:
                logging.warning(e)
            if 'gxl_p211_v1#' in info:
                logging.info('the device is in uboot')
                return True
            if 'sc2_ah212#' or 's4_ap222#' in info:
                logging.info('OTT is in uboot')
                return True
            else:
                self.write('\n\n')
        logging.info('no uboot info printed,please confirm manually')

    def enter_kernel(self):
        """
        Enter kernel.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        self.write('reset')
        self.ser.readlines()
        sleep(2)
        start = time.time()
        info = ''
        while time.time() - start < 60:
            try:
                info = self.ser.read(10000).decode('utf-8')
                logging.info(info)
            except UnicodeDecodeError as e:
                logging.warning(e)
            if 'uboot time:' in info:
                self.uboot_time = re.findall(".*uboot time: (.*) us.*", info, re.S)[0]
            if 'Starting kernel ...' in info:
                self.write('\n\n')
            if 'console:/ $' in info:
                logging.info('now is in kernel')
                return True
        logging.info('no kernel message captured,please confirm manually')

    def write(self, command):
        """
        Write.

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
        None
            This method does not return a value.
        """
        if self.ser is None:
            return

        try:
            #self.ser.write(bytes(command + '\r\n', encoding='utf-8'))
            full_cmd = command + '\r\n'  # <-- 这是关键！
            self.ser.write(full_cmd.encode())
            logging.info(f"=> {command}")
        except (serial.serialutil.SerialException, AttributeError, OSError) as err:
            logging.error('Serial write failed for command %s: %s', command, err)
            self._ensure_connection()
            self.ser.write(bytes(command + '\r\n', encoding='utf-8'))
        logging.info(f'=> {command}')
        sleep(0.1)

    def recv(self, timeout=5, until_newline=False):
        """
        Recv.

        -------------------------
        Parameters
        -------------------------
        timeout : Any
            Timeout in seconds for waiting or connection operations.
        until_newline : Any
            The ``until_newline`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        deadline = time.time() + timeout
        buf = bytearray()

        while time.time() < deadline:
            try:
                chunk = self._rx_queue.get(timeout=deadline - time.time())
                buf.extend(chunk)
                if until_newline and b'\n' in chunk:
                    break
            except Empty:
                break  # Timeout
        return buf.decode('utf-8', errors='ignore')

    def exec_command(
        self,
        command: str,
        *,
        timeout: float = 8.0,
        prompt_markers: tuple[bytes, ...] = (
            b"\n/ #",
            b"\r\n/ #",
            b"/ #",
            b"\n# ",
            b"\r\n# ",
            b"console:/ $",
        ),
        progress_interval_s: float = 0.0,
        progress_tail_chars: int = 800,
    ) -> str:
        try:
            while True:
                self._rx_queue.get_nowait()
        except Empty:
            pass

        self.write(command)
        deadline = time.time() + timeout
        next_progress = time.time() + float(progress_interval_s) if progress_interval_s else 0.0
        buf = bytearray()
        while time.time() < deadline:
            remaining = deadline - time.time()
            try:
                chunk = self._rx_queue.get(timeout=remaining)
            except Empty:
                break
            buf.extend(chunk)
            if any(m in buf for m in prompt_markers):
                break
            if progress_interval_s and time.time() >= next_progress:
                text = buf.decode("utf-8", errors="ignore")
                tail = text[-progress_tail_chars:].strip()
                if tail:
                    logging.info("Serial command output (tail):\n%s", tail)
                next_progress = time.time() + float(progress_interval_s)
        text = buf.decode("utf-8", errors="ignore")
        if not any(m in buf for m in prompt_markers):
            tail = text[-1000:].strip()
            raise RuntimeError(
                f"Serial command did not complete: {command}\nCaptured output tail:\n{tail}"
            )
        return text

    def recv_until_pattern(self, pattern=b'', timeout=60):
        """
        Recv until pattern.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        pattern : Any
            The ``pattern`` parameter.
        timeout : Any
            Timeout in seconds for waiting or connection operations.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        start = time.time()
        result = []
        while True:
            if time.time() - start > timeout:
                if pattern:
                    raise TimeoutError('Time Out')
                return result
            log = self.ser.readline()
            if not log:
                continue
            result.append(log)
            if pattern and pattern in log:
                return result

    def receive_file_via_serial(self, output_file):
        """
        Receive file via serial.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        output_file : Any
            The ``output_file`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            with open(output_file, 'wb') as file:
                while True:
                    data = self.ser.read(1024)
                    if not data:
                        break
                    file.write(data)
            logging.info("File transfer completed")
        except serial.SerialException as e:
            logging.error("Serial connection error: %s", str(e))
        except Exception as e:
            logging.error("An error occurred: %s", str(e))

    def start_saving_kernel_log(self):
        """
        Start saving kernel log.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            with open(self.log_file, 'wb') as file:
                while True:
                    data = self.ser.read(1024)
                    if data:
                        file.write(data)
                        file.flush()  # Force flush the buffer
        except serial.SerialException as e:
            logging.error("Serial connection error: %s", str(e))
        except Exception as e:
            logging.error("An error occurred: %s", str(e))

    def search_keyword_in_log(self, keyword):
        """
        Search keyword in log.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            with open(self.log_file, 'rb') as file:
                file.seek(self.log_file_position)  # Start reading from the last recorded position
                for line in file:
                    if keyword.encode() in line:
                        return True
                self.log_file_position = file.tell()  # Update read position
            return False
        except Exception as e:
            logging.error("An error occurred: %s", str(e))
            return False

    def close(self):
        """
        Close.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._stop_flag.set()
        if hasattr(self, 'log_thread') and self.log_thread.is_alive():
            self.log_thread.join(timeout=1)
        if getattr(self, 'ser', None):
            self.ser.close()

    def __del__(self):
        """
        Del.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.close()
            logging.info('close serial port %s' % self.ser)
        except AttributeError as e:
            logging.info('failed to open serial port,not need to close')


class SerialShellExecutor:
    def __init__(self, serial: serial_tool, *, timeout: float = 20.0) -> None:
        self._serial = serial
        self._timeout = timeout
        self._last_output = ""

    def write(
        self,
        command: str,
        timeout: float | None = None,
        *,
        progress_interval_s: float = 0.0,
    ) -> None:
        cmd_timeout = self._timeout if timeout is None else float(timeout)
        self._last_output = self._serial.exec_command(
            command,
            timeout=cmd_timeout,
            progress_interval_s=progress_interval_s,
        )

    def recv(self) -> str:
        return self._last_output
