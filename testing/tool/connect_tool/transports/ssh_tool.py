"""This module implements SSH tool functionality for the connect_tool package."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import contextmanager
from typing import Optional

logging.getLogger("asyncssh").setLevel(logging.WARNING)
import asyncssh
from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess

from src.util.constants import get_telnet_connect_window


class FastConnectSSHClient(asyncssh.SSHClient):
    """A custom SSH client that can be used to hook into connection events."""
    pass


class SSHSession:
    """A synchronous wrapper around an asynchronous SSH connection."""

    def __init__(
            self,
            host: str,
            port: int = 22,
            *,
            username: str = "root",
            password: Optional[str] = None,
            timeout: float = 10.0,
            encoding: str = "utf-8",
            client_factory: Optional[type[asyncssh.SSHClient]] = None,
    ) -> None:
        # 正确初始化属性
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.encoding = encoding
        self._client_factory = client_factory or FastConnectSSHClient
        self._loop = asyncio.new_event_loop()
        self._conn: Optional[SSHClientConnection] = None
        self.sock = None

        # ↓↓↓ 删除这行！不要创建另一个SSHSession
        # self._session = SSHSession(...)

        # ↓↓↓ 如果有，也删除这些多余的初始化代码
        # try:
        #     self._session.open()
        #     ...
        # except Exception as e:
        #     ...

    @contextmanager
    def _use_loop(self):
        previous_loop = None
        try:
            previous_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            previous_loop = None
        asyncio.set_event_loop(self._loop)
        try:
            yield
        finally:
            asyncio.set_event_loop(previous_loop)

    def open(self) -> None:
        """Synchronously open the SSH connection."""

        async def _open():
            conn = await asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                client_factory=self._client_factory,
                known_hosts=None,  # Disable for testing
            )
            return conn

        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()

        with self._use_loop():
            self._conn = self._loop.run_until_complete(
                asyncio.wait_for(_open(), timeout=self.timeout)
            )
        self.sock = object()

    def close(self) -> None:
        """Synchronously close the SSH connection."""
        if self._loop.is_closed():
            self._conn = None
            self.sock = None
            return

        async def _close():
            if self._conn is not None:
                self._conn.close()
                await self._conn.wait_closed()

        try:
            if self._conn is not None:
                with self._use_loop():
                    self._loop.run_until_complete(_close())
        finally:
            self._conn = None
            self.sock = None
            try:
                self._loop.close()
            except Exception:
                logging.debug("Error closing SSHSession event loop", exc_info=True)

    def is_connected(self) -> bool:
        if self._conn is None or self.sock is None:
            return False
        try:
            return not self._conn.is_closed()
        except Exception:
            return False

    async def _exec_command_async(self, command: str) -> str:
        """Execute a command on the already established connection."""
        if not self.is_connected():
            raise RuntimeError("SSHSession is not connected")

        process: SSHClientProcess = await self._conn.create_process(command)
        output = await process.wait()
        return (output.stdout + output.stderr).rstrip('\n')

    def exec_command(self, command: str, timeout: float = 10.0) -> str:
        """Synchronously execute a command using the persistent session."""
        if not self.is_connected():
            raise RuntimeError("SSHSession is not connected")

        async def _run():
            return await self._exec_command_async(command)

        with self._use_loop():
            return self._loop.run_until_complete(
                asyncio.wait_for(_run(), timeout=timeout)
            )


class ssh_tool:
    """SSH tool for executing commands over a persistent SSH session."""

    def __init__(
            self,
            host: str,
            port: int = 22,
            *,
            username: str = "root",
            password: Optional[str] = None,
            timeout: float = 10.0,
            encoding: str = "utf-8",
            client_factory: Optional[type[asyncssh.SSHClient]] = None,
    ) -> None:
        # 设置所有必要属性
        self.dut_ip = host  # 保持向后兼容
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.encoding = encoding
        self._client_factory = client_factory or FastConnectSSHClient
        self._connect_minwait, self._connect_maxwait = get_telnet_connect_window()
        self._last_output = ""
        self._connected = False  # 连接状态标志

        # 创建SSHSession但不立即连接
        self._session = SSHSession(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout
        )

        # 不立即连接，延迟到真正需要时
        logging.info('SSH target: %s@%s:%s (delayed connection)', self.username, self.dut_ip, self.port)

    def checkoutput(self, cmd: str, wildcard: str = '') -> str:
        """Execute a command and return its output using the persistent session."""
        # 确保_session属性存在
        if not hasattr(self, '_session') or self._session is None:
            # 重新创建session
            self._session = SSHSession(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout
            )

        # 确保已连接
        if not self._connected or not self._session.is_connected():
            try:
                self._session.open()
                self._connected = True
                logging.info('SSH connected for command execution: %s@%s', self.username, self.dut_ip)
            except Exception as e:
                logging.error('SSH connection failed: %s', e)
                return ""  # 返回空字符串而不是抛出异常

        # 执行命令
        connection_errors = (ConnectionError, OSError, asyncio.TimeoutError, RuntimeError, asyncssh.Error)
        try:
            output = self._session.exec_command(cmd, timeout=self.timeout)
            self._last_output = output
            return output
        except connection_errors as e:
            logging.warning("SSH connection lost during command execution: %s", e)
            # 尝试重新连接
            self._connected = False
            if not self.wait_reconnect_sync():
                return ""  # 返回空字符串
            # 重试命令
            output = self._session.exec_command(cmd, timeout=self.timeout)
            self._last_output = output
            return output

    async def wait_reconnect(self, timeout: int = 30, interval: float = 1.0) -> bool:
        """Asynchronously wait for the SSH service to become reachable again."""
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            try:
                conn = await asyncio.wait_for(
                    asyncssh.connect(
                        self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        known_hosts=None,
                    ),
                    timeout=5.0,
                )
                conn.close()
                await conn.wait_closed()
                # 重新打开session
                self._session.close()
                self._session.open()
                self._connected = True
                return True
            except (OSError, asyncssh.Error, asyncio.TimeoutError):
                await asyncio.sleep(interval)
        return False

    def wait_reconnect_sync(self, timeout: int = 30, interval: float = 1.0) -> bool:
        """Synchronously wait for SSH to reconnect."""
        return asyncio.run(self.wait_reconnect(timeout=timeout, interval=interval))

    def close(self):
        """Close the underlying SSH session."""
        if hasattr(self, '_session') and self._session:
            self._session.close()
            self._connected = False

    def __del__(self):
        self.close()
