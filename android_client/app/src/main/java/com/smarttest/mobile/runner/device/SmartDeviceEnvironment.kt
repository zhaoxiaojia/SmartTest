package com.smarttest.mobile.runner.device

import android.content.Context
import com.smarttest.mobile.runner.device.log.InMemoryCommandRecorder
import com.smarttest.mobile.runner.device.ops.RootDeviceOperationGateway
import com.smarttest.mobile.runner.device.shell.ProcessShellGateway
import com.smarttest.mobile.runner.device.state.SystemDeviceStateProvider

data class SmartDeviceEnvironment(
    val shellGateway: ProcessShellGateway,
    val commandRecorder: InMemoryCommandRecorder,
    val stateProvider: SystemDeviceStateProvider,
    val operationGateway: RootDeviceOperationGateway,
)

object SmartDeviceEnvironmentFactory {
    fun create(context: Context): SmartDeviceEnvironment {
        val shellGateway = ProcessShellGateway()
        val commandRecorder = InMemoryCommandRecorder()
        val stateProvider = SystemDeviceStateProvider(context, shellGateway)
        val operationGateway = RootDeviceOperationGateway(shellGateway, commandRecorder)
        return SmartDeviceEnvironment(
            shellGateway = shellGateway,
            commandRecorder = commandRecorder,
            stateProvider = stateProvider,
            operationGateway = operationGateway,
        )
    }
}
