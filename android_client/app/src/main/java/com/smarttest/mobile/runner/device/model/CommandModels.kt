package com.smarttest.mobile.runner.device.model

import java.util.UUID

enum class CommandType {
    Reboot,
    Suspend,
    Wakeup,
    WifiEnable,
    WifiDisable,
    BluetoothEnable,
    BluetoothDisable,
    EthernetUp,
    EthernetDown,
    ReadSysNode,
    WriteSysNode,
    ShellRaw,
}

data class DeviceCommand(
    val id: String = UUID.randomUUID().toString(),
    val type: CommandType,
    val label: String = type.name,
    val args: Map<String, String> = emptyMap(),
    val requireRoot: Boolean = false,
    val origin: String = "manual",
)

data class DeviceCommandResult(
    val success: Boolean,
    val exitCode: Int?,
    val stdout: String,
    val stderr: String,
    val startedAtMs: Long,
    val finishedAtMs: Long,
) {
    val durationMs: Long
        get() = finishedAtMs - startedAtMs
}

data class CommandRecord(
    val command: DeviceCommand,
    val shellCommand: String?,
    val result: DeviceCommandResult,
)
