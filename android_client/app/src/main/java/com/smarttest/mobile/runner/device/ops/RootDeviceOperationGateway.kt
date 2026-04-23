package com.smarttest.mobile.runner.device.ops

import com.smarttest.mobile.runner.device.log.CommandRecorder
import com.smarttest.mobile.runner.device.model.CommandRecord
import com.smarttest.mobile.runner.device.model.CommandType
import com.smarttest.mobile.runner.device.model.DeviceCommand
import com.smarttest.mobile.runner.device.model.DeviceCommandResult
import com.smarttest.mobile.runner.device.shell.ShellGateway

class RootDeviceOperationGateway(
    private val shellGateway: ShellGateway,
    private val commandRecorder: CommandRecorder,
) : DeviceOperationGateway {
    override suspend fun execute(command: DeviceCommand): CommandRecord {
        val shellCommand = buildShellCommand(command)
        val result = shellGateway.exec(
            command = shellCommand,
            asRoot = command.requireRoot,
        )
        val record = CommandRecord(
            command = command,
            shellCommand = shellCommand,
            result = DeviceCommandResult(
                success = result.success,
                exitCode = result.exitCode,
                stdout = result.stdout,
                stderr = result.stderr,
                startedAtMs = result.startedAtMs,
                finishedAtMs = result.finishedAtMs,
            ),
        )
        commandRecorder.record(record)
        return record
    }

    private fun buildShellCommand(command: DeviceCommand): String {
        return when (command.type) {
            CommandType.Reboot -> "svc power reboot || cmd power reboot || reboot"
            CommandType.Suspend -> buildSuspendCommand(command)
            CommandType.Wakeup -> command.args["raw"]
                ?: "input keyevent KEYCODE_WAKEUP"
            CommandType.WifiEnable -> "svc wifi enable"
            CommandType.WifiDisable -> "svc wifi disable"
            CommandType.BluetoothEnable -> command.args["raw"]
                ?: "cmd bluetooth_manager enable"
            CommandType.BluetoothDisable -> command.args["raw"]
                ?: "cmd bluetooth_manager disable"
            CommandType.EthernetUp -> "ip link set dev ${required(command, "iface")} up"
            CommandType.EthernetDown -> "ip link set dev ${required(command, "iface")} down"
            CommandType.ReadSysNode -> "cat ${quote(required(command, "path"))}"
            CommandType.WriteSysNode -> "echo ${quote(required(command, "value"))} > ${quote(required(command, "path"))}"
            CommandType.ShellRaw -> required(command, "raw")
        }
    }

    private fun buildSuspendCommand(command: DeviceCommand): String {
        command.args["raw"]?.let { return it }

        val wakeAfterSec = command.args["wake_after_sec"]?.toLongOrNull()
        if (wakeAfterSec == null || wakeAfterSec <= 0L) {
            return "input keyevent KEYCODE_SLEEP"
        }

        return """
            if command -v rtcwake >/dev/null 2>&1; then
                rtcwake -m mem -s $wakeAfterSec
            elif [ -w /sys/class/rtc/rtc0/wakealarm ] && [ -w /sys/power/state ]; then
                echo 0 > /sys/class/rtc/rtc0/wakealarm
                echo +$wakeAfterSec > /sys/class/rtc/rtc0/wakealarm
                echo mem > /sys/power/state
            else
                input keyevent KEYCODE_SLEEP
                sleep $wakeAfterSec
                input keyevent KEYCODE_WAKEUP
            fi
        """.trimIndent()
    }

    private fun required(command: DeviceCommand, key: String): String {
        return requireNotNull(command.args[key]) { "Command ${command.type} missing arg: $key" }
    }

    private fun quote(value: String): String {
        return "'${value.replace("'", "'\\''")}'"
    }
}
