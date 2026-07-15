import os
import sys
import threading

from PySide6.QtCore import QDateTime, QSysInfo, QtMsgType, qInstallMessageHandler

from support.logging import default_log_path, smart_log


_logging = None


def _level_name(level) -> str:
    if isinstance(level, str):
        return level.lower()
    if level >= 50:
        return "critical"
    if level >= 40:
        return "error"
    if level >= 30:
        return "warning"
    if level >= 20:
        return "info"
    return "debug"


def _level_by_msg_type(msg_type) -> str:
    if msg_type == QtMsgType.QtFatalMsg:
        return "critical"
    if msg_type == QtMsgType.QtCriticalMsg:
        return "error"
    if msg_type == QtMsgType.QtWarningMsg:
        return "warning"
    if msg_type == QtMsgType.QtInfoMsg:
        return "info"
    return "debug"


class _SmartLogger:
    def __init__(self, name: str):
        self.name = name

    def log(self, level, message, *args, **kwargs):
        smart_log(
            message,
            *args,
            level=_level_name(level),
            domain="ui",
            source=self.name,
            extra=kwargs.pop("extra", None),
        )

    def debug(self, message, *args, **kwargs):
        self.log("debug", message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.log("info", message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.log("warning", message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.log("error", message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        self.log("critical", message, *args, **kwargs)


def _messageHandler(msgType, context, message):
    extra = {"thread_id": threading.get_ident()}
    if context.file:
        extra["file"] = context.file
        extra["line"] = context.line
    smart_log(
        message,
        level=_level_by_msg_type(msgType),
        domain="ui",
        source="qt",
        extra=extra,
    )


def LogSetup(name, level="debug"):
    global _logging
    _logging = _SmartLogger(name)
    qInstallMessageHandler(_messageHandler)

    startup_lines = [
        "===================================================",
        f"[AppName] {name}",
        f"[AppPath] {sys.argv[0]}",
        f"[ProcessId] {os.getpid()}",
        "[DeviceInfo]",
        f"  [DeviceId] {QSysInfo.machineUniqueId().toStdString()}",
        f"  [Manufacturer] {QSysInfo.productVersion()}",
        f"  [CPU_ABI] {QSysInfo.currentCpuArchitecture()}",
        f"[LOG_LEVEL] {_level_name(level)}",
        f"[LOG_PATH] {default_log_path()}",
        "===================================================",
    ]
    for line in startup_lines:
        smart_log(line, level="info", domain="ui", source=name)


def Logger():
    global _logging
    if _logging is None:
        _logging = _SmartLogger("SmartTest")
    return _logging
