package com.smarttest.mobile.runner.device.model

data class WifiState(
    val enabled: Boolean,
    val connectedSsid: String?,
    val ipAddress: String?,
    val scanResultCount: Int?,
    val detail: String? = null,
)

data class BluetoothState(
    val enabled: Boolean,
    val adapterName: String?,
    val connectedDevices: List<String> = emptyList(),
    val discovering: Boolean = false,
)

data class CpuCoreState(
    val index: Int,
    val online: Boolean,
    val currentFreqKhz: Long?,
    val minFreqKhz: Long?,
    val maxFreqKhz: Long?,
)

data class CpuState(
    val onlineCoreCount: Int,
    val governor: String?,
    val temperatureC: Float?,
    val cores: List<CpuCoreState>,
    val rawSummary: String? = null,
)

data class PowerState(
    val interactive: Boolean?,
    val screenOn: Boolean?,
    val batteryLevel: Int?,
    val charging: Boolean?,
)

data class NetworkInterfaceState(
    val name: String,
    val up: Boolean?,
    val ipAddress: String?,
)

data class NetworkState(
    val activeTransport: String?,
    val hasInternet: Boolean?,
    val ethernet: NetworkInterfaceState?,
    val wifiIpAddress: String?,
)

data class SystemSnapshot(
    val wifi: WifiState,
    val bluetooth: BluetoothState,
    val cpu: CpuState,
    val power: PowerState,
    val network: NetworkState,
    val recordedAtMs: Long,
)
