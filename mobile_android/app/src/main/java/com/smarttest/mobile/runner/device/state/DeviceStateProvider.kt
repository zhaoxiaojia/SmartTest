package com.smarttest.mobile.runner.device.state

import com.smarttest.mobile.runner.device.model.BluetoothState
import com.smarttest.mobile.runner.device.model.CpuState
import com.smarttest.mobile.runner.device.model.NetworkState
import com.smarttest.mobile.runner.device.model.PowerState
import com.smarttest.mobile.runner.device.model.SystemSnapshot
import com.smarttest.mobile.runner.device.model.WifiState

interface DeviceStateProvider {
    suspend fun readSnapshot(): SystemSnapshot

    suspend fun readWifiState(): WifiState

    suspend fun readBluetoothState(): BluetoothState

    suspend fun readCpuState(): CpuState

    suspend fun readPowerState(): PowerState

    suspend fun readNetworkState(): NetworkState
}
