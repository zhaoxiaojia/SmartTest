package com.smarttest.mobile.runner.device.state

import android.bluetooth.BluetoothManager
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.PowerManager
import com.smarttest.mobile.runner.device.model.BluetoothState
import com.smarttest.mobile.runner.device.model.CpuCoreState
import com.smarttest.mobile.runner.device.model.CpuState
import com.smarttest.mobile.runner.device.model.NetworkInterfaceState
import com.smarttest.mobile.runner.device.model.NetworkState
import com.smarttest.mobile.runner.device.model.PowerState
import com.smarttest.mobile.runner.device.model.SystemSnapshot
import com.smarttest.mobile.runner.device.model.WifiState
import com.smarttest.mobile.runner.device.shell.ShellGateway
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import java.net.InetAddress
import java.nio.ByteBuffer
import java.nio.ByteOrder

class SystemDeviceStateProvider(
    context: Context,
    private val shellGateway: ShellGateway,
) : DeviceStateProvider {
    private val appContext = context.applicationContext
    private val wifiManager: WifiManager? = appContext.getSystemService(WifiManager::class.java)
    private val bluetoothManager: BluetoothManager? = appContext.getSystemService(BluetoothManager::class.java)
    private val connectivityManager: ConnectivityManager? = appContext.getSystemService(ConnectivityManager::class.java)
    private val powerManager: PowerManager? = appContext.getSystemService(PowerManager::class.java)
    private val batteryManager: BatteryManager? = appContext.getSystemService(BatteryManager::class.java)

    override suspend fun readSnapshot(): SystemSnapshot = coroutineScope {
        val wifi = async { readWifiState() }
        val bluetooth = async { readBluetoothState() }
        val cpu = async { readCpuState() }
        val power = async { readPowerState() }
        val network = async { readNetworkState() }

        SystemSnapshot(
            wifi = wifi.await(),
            bluetooth = bluetooth.await(),
            cpu = cpu.await(),
            power = power.await(),
            network = network.await(),
            recordedAtMs = System.currentTimeMillis(),
        )
    }

    override suspend fun readWifiState(): WifiState {
        val manager = wifiManager
        if (manager == null) {
            return WifiState(enabled = false, connectedSsid = null, ipAddress = null, scanResultCount = null)
        }

        val connectionInfo = runCatching { manager.connectionInfo }.getOrNull()
        return WifiState(
            enabled = manager.isWifiEnabled,
            connectedSsid = connectionInfo?.ssid?.takeUnless { it == WifiManager.UNKNOWN_SSID },
            ipAddress = connectionInfo?.ipAddress?.takeIf { it != 0 }?.let(::intToIpAddress),
            scanResultCount = runCatching { manager.scanResults?.size }.getOrNull(),
            detail = connectionInfo?.supplicantState?.name,
        )
    }

    override suspend fun readBluetoothState(): BluetoothState {
        val adapter = bluetoothManager?.adapter
        return BluetoothState(
            enabled = adapter?.isEnabled == true,
            adapterName = runCatching { adapter?.name }.getOrNull(),
            connectedDevices = emptyList(),
            discovering = adapter?.isDiscovering == true,
        )
    }

    override suspend fun readCpuState(): CpuState {
        val online = shellGateway.exec("cat /sys/devices/system/cpu/online", asRoot = true)
        val coreIndexes = parseCpuRange(online.stdout).ifEmpty { listOf(0) }

        val cores = coreIndexes.map { index ->
            val current = shellGateway.exec(
                "cat /sys/devices/system/cpu/cpu$index/cpufreq/scaling_cur_freq",
                asRoot = true,
            )
            val min = shellGateway.exec(
                "cat /sys/devices/system/cpu/cpu$index/cpufreq/scaling_min_freq",
                asRoot = true,
            )
            val max = shellGateway.exec(
                "cat /sys/devices/system/cpu/cpu$index/cpufreq/scaling_max_freq",
                asRoot = true,
            )
            CpuCoreState(
                index = index,
                online = coreIndexes.contains(index),
                currentFreqKhz = current.stdout.toLongOrNull(),
                minFreqKhz = min.stdout.toLongOrNull(),
                maxFreqKhz = max.stdout.toLongOrNull(),
            )
        }

        val governor = shellGateway.exec(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
            asRoot = true,
        ).stdout.ifBlank { null }
        val temperature = shellGateway.exec(
            "cat /sys/class/thermal/thermal_zone0/temp",
            asRoot = true,
        ).stdout.toFloatOrNull()?.let { temp ->
            if (temp > 1000f) temp / 1000f else temp
        }

        return CpuState(
            onlineCoreCount = cores.count { it.online },
            governor = governor,
            temperatureC = temperature,
            cores = cores,
            rawSummary = online.stdout.ifBlank { null },
        )
    }

    override suspend fun readPowerState(): PowerState {
        return PowerState(
            interactive = powerManager?.isInteractive,
            screenOn = powerManager?.isInteractive,
            batteryLevel = batteryManager?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY),
            charging = batteryManager?.isCharging,
        )
    }

    override suspend fun readNetworkState(): NetworkState {
        val activeNetwork = connectivityManager?.activeNetwork
        val capabilities = activeNetwork?.let { connectivityManager?.getNetworkCapabilities(it) }
        val ethernetIp = shellGateway.exec("ip -f inet addr show eth0", asRoot = true).stdout
        val up = shellGateway.exec("cat /sys/class/net/eth0/operstate", asRoot = true).stdout

        return NetworkState(
            activeTransport = transportName(capabilities),
            hasInternet = capabilities?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
            ethernet = NetworkInterfaceState(
                name = "eth0",
                up = up.equals("up", ignoreCase = true),
                ipAddress = extractIp(ethernetIp),
            ),
            wifiIpAddress = readWifiState().ipAddress,
        )
    }

    private fun parseCpuRange(raw: String): List<Int> {
        return raw.split(",")
            .map(String::trim)
            .filter(String::isNotEmpty)
            .flatMap { token ->
                if ("-" !in token) {
                    token.toIntOrNull()?.let(::listOf).orEmpty()
                } else {
                    val (start, end) = token.split("-", limit = 2)
                    val startIndex = start.toIntOrNull()
                    val endIndex = end.toIntOrNull()
                    if (startIndex == null || endIndex == null) {
                        emptyList()
                    } else {
                        (startIndex..endIndex).toList()
                    }
                }
            }
    }

    private fun transportName(capabilities: NetworkCapabilities?): String? {
        if (capabilities == null) return null
        return when {
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH) -> "bluetooth"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            else -> "unknown"
        }
    }

    private fun extractIp(raw: String): String? {
        return raw.lineSequence()
            .map(String::trim)
            .firstOrNull { it.startsWith("inet ") }
            ?.substringAfter("inet ")
            ?.substringBefore("/")
            ?.trim()
    }

    private fun intToIpAddress(value: Int): String {
        val bytes = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array()
        return InetAddress.getByAddress(bytes).hostAddress.orEmpty()
    }
}
