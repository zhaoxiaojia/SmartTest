package com.smarttest.mobile.runner.device.ops

import android.bluetooth.BluetoothManager
import android.content.Context
import android.net.wifi.WifiManager
import com.smarttest.mobile.runner.device.log.CommandRecorder
import com.smarttest.mobile.runner.device.model.CommandRecord
import com.smarttest.mobile.runner.device.model.CommandType
import com.smarttest.mobile.runner.device.model.DeviceCommand
import com.smarttest.mobile.runner.device.model.DeviceCommandResult
import com.smarttest.mobile.runner.device.shell.ShellGateway

class RootDeviceOperationGateway(
    context: Context,
    private val shellGateway: ShellGateway,
    private val commandRecorder: CommandRecorder,
) : DeviceOperationGateway {
    private val appContext = context.applicationContext
    private val wifiManager: WifiManager? = appContext.getSystemService(WifiManager::class.java)
    private val bluetoothManager: BluetoothManager? = appContext.getSystemService(BluetoothManager::class.java)

    override suspend fun execute(command: DeviceCommand): CommandRecord {
        when (command.type) {
            CommandType.WifiEnable -> return executeFrameworkCommand(command, "WifiManager.setWifiEnabled(true)") {
                setWifiEnabled(true)
            }
            CommandType.WifiDisable -> return executeFrameworkCommand(command, "WifiManager.setWifiEnabled(false)") {
                setWifiEnabled(false)
            }
            CommandType.BluetoothEnable -> return executeFrameworkCommand(command, "BluetoothAdapter.enable()") {
                setBluetoothEnabled(true)
            }
            CommandType.BluetoothDisable -> return executeFrameworkCommand(command, "BluetoothAdapter.disable()") {
                setBluetoothEnabled(false)
            }
            else -> Unit
        }

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

    private fun executeFrameworkCommand(
        command: DeviceCommand,
        operationName: String,
        action: () -> Boolean,
    ): CommandRecord {
        val startedAt = System.currentTimeMillis()
        val result = try {
            val success = action()
            DeviceCommandResult(
                success = success,
                exitCode = if (success) 0 else 1,
                stdout = operationName,
                stderr = if (success) "" else "$operationName returned false",
                startedAtMs = startedAt,
                finishedAtMs = System.currentTimeMillis(),
            )
        } catch (error: SecurityException) {
            DeviceCommandResult(
                success = false,
                exitCode = null,
                stdout = operationName,
                stderr = "SecurityException: ${error.message ?: error.javaClass.simpleName}",
                startedAtMs = startedAt,
                finishedAtMs = System.currentTimeMillis(),
            )
        } catch (error: RuntimeException) {
            DeviceCommandResult(
                success = false,
                exitCode = null,
                stdout = operationName,
                stderr = "${error.javaClass.simpleName}: ${error.message ?: ""}".trim(),
                startedAtMs = startedAt,
                finishedAtMs = System.currentTimeMillis(),
            )
        }
        val record = CommandRecord(
            command = command,
            shellCommand = operationName,
            result = result,
        )
        commandRecorder.record(record)
        return record
    }

    @Suppress("DEPRECATION")
    private fun setWifiEnabled(enabled: Boolean): Boolean {
        val manager = wifiManager ?: return false
        return manager.setWifiEnabled(enabled)
    }

    @Suppress("DEPRECATION")
    private fun setBluetoothEnabled(enabled: Boolean): Boolean {
        val adapter = bluetoothManager?.adapter ?: return false
        return if (enabled) adapter.enable() else adapter.disable()
    }

    private fun buildShellCommand(command: DeviceCommand): String {
        return when (command.type) {
            CommandType.Reboot -> "svc power reboot || cmd power reboot || reboot"
            CommandType.Wakeup -> command.args["raw"]
                ?: "input keyevent KEYCODE_WAKEUP"
            CommandType.WifiEnable -> error("WifiEnable is handled through framework API.")
            CommandType.WifiDisable -> error("WifiDisable is handled through framework API.")
            CommandType.BluetoothEnable -> command.args["raw"]
                ?: error("BluetoothEnable is handled through framework API.")
            CommandType.BluetoothDisable -> command.args["raw"]
                ?: error("BluetoothDisable is handled through framework API.")
            CommandType.EthernetUp -> "ip link set dev ${required(command, "iface")} up"
            CommandType.EthernetDown -> "ip link set dev ${required(command, "iface")} down"
            CommandType.ReadSysNode -> "cat ${quote(required(command, "path"))}"
            CommandType.WriteSysNode -> "echo ${quote(required(command, "value"))} > ${quote(required(command, "path"))}"
            CommandType.ShellRaw -> required(command, "raw")
        }
    }

    private fun required(command: DeviceCommand, key: String): String {
        return requireNotNull(command.args[key]) { "Command ${command.type} missing arg: $key" }
    }

    private fun quote(value: String): String {
        return "'${value.replace("'", "'\\''")}'"
    }
}
