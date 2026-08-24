package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.device.model.BluetoothState
import com.smarttest.mobile.runner.device.model.WifiState

data class RadioStateSnapshot(
    val wifi: WifiState,
    val bluetooth: BluetoothState,
)

object PowerCycleSupport {
    suspend fun captureRadioState(
        context: TestCaseExecutionContext,
        stage: String,
    ): RadioStateSnapshot {
        val wifi = context.environment.stateProvider.readWifiState()
        val bluetooth = context.environment.stateProvider.readBluetoothState()
        context.log(
            "$stage wifi(enabled=${wifi.enabled}, ssid=${wifi.connectedSsid ?: "-"}, ip=${wifi.ipAddress ?: "-"}) " +
                "bt(enabled=${bluetooth.enabled}, name=${bluetooth.adapterName ?: "-"})",
        )
        return RadioStateSnapshot(
            wifi = wifi,
            bluetooth = bluetooth,
        )
    }
}
