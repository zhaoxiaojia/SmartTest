package com.smarttest.mobile.runner.device.ops

import com.smarttest.mobile.runner.device.model.CommandRecord
import com.smarttest.mobile.runner.device.model.DeviceCommand

interface DeviceOperationGateway {
    suspend fun execute(command: DeviceCommand): CommandRecord
}
