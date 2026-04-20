package com.smarttest.mobile.runner.cases

import android.content.Context
import com.smarttest.mobile.runner.RunningCase
import com.smarttest.mobile.runner.TestRunRequest
import com.smarttest.mobile.runner.device.SmartDeviceEnvironment
import com.smarttest.mobile.runner.device.model.CommandRecord
import com.smarttest.mobile.runner.device.model.CommandType
import com.smarttest.mobile.runner.device.model.DeviceCommand

class TestCaseExecutionContext(
    val appContext: Context,
    val environment: SmartDeviceEnvironment,
    val request: TestRunRequest,
    val runningCase: RunningCase,
    private val logger: (String) -> Unit,
) {
    fun log(message: String) {
        logger("[${runningCase.title}] $message")
    }

    fun parameter(paramId: String, defaultValue: String): String {
        return request.parameterOverrides["${runningCase.id}:$paramId"] ?: defaultValue
    }

    fun intParameter(paramId: String, defaultValue: Int): Int {
        return parameter(paramId, defaultValue.toString()).toIntOrNull() ?: defaultValue
    }

    fun longParameter(paramId: String, defaultValue: Long): Long {
        return parameter(paramId, defaultValue.toString()).toLongOrNull() ?: defaultValue
    }

    suspend fun execDeviceCommand(
        type: CommandType,
        label: String,
        args: Map<String, String> = emptyMap(),
        requireRoot: Boolean = true,
    ): CommandRecord {
        return environment.operationGateway.execute(
            DeviceCommand(
                type = type,
                label = "${runningCase.id}:$label",
                args = args,
                requireRoot = requireRoot,
                origin = runningCase.id,
            ),
        )
    }

    suspend fun execShell(
        label: String,
        command: String,
        requireRoot: Boolean = true,
    ): CommandRecord {
        return environment.operationGateway.execute(
            DeviceCommand(
                type = CommandType.ShellRaw,
                label = "${runningCase.id}:$label",
                args = mapOf("raw" to command),
                requireRoot = requireRoot,
                origin = runningCase.id,
            ),
        )
    }
}
