package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import kotlinx.coroutines.delay

data class PowerCycleRecoveryConfig(
    val pingTarget: String,
    val bluetoothTarget: String,
)

object PowerCycleRecoveryChecks {
    private const val PING_ATTEMPTS = 3
    private const val BLUETOOTH_ATTEMPTS = 3
    private const val RETRY_DELAY_MS = 2_000L
    private const val CONNECTED_BT_MAC_COMMAND =
        "dumpsys bluetooth_manager | grep -B1 \"Connected: true\" | grep \"Peer:\" | awk '{print \$2}'"

    suspend fun verifyRecoveredState(
        context: TestCaseExecutionContext,
        stage: String,
        config: PowerCycleRecoveryConfig,
    ): Boolean {
        val snapshot = PowerCycleSupport.captureRadioState(context = context, stage = stage)
        var passed = true

        val pingTarget = config.pingTarget.trim()
        if (pingTarget.isNotEmpty()) {
            val pingOk = verifyPingTarget(context, pingTarget)
            if (pingOk) {
                context.log("$stage ping target reachable: $pingTarget")
            } else {
                context.log(
                    "$stage ping target unreachable after $PING_ATTEMPTS attempt(s): $pingTarget " +
                        "wifiIp=${snapshot.wifi.ipAddress ?: "-"} ssid=${snapshot.wifi.connectedSsid ?: "-"}",
                )
                passed = false
            }
        }

        val bluetoothTarget = config.bluetoothTarget.trim()
        if (bluetoothTarget.isNotEmpty()) {
            val targetMac = parseBluetoothTargetMac(bluetoothTarget)
            if (targetMac == null) {
                context.log("$stage invalid bluetooth target format: $bluetoothTarget")
                passed = false
            } else {
                val btOk = verifyBluetoothTarget(context, targetMac)
                if (btOk) {
                    context.log("$stage bluetooth target connected: $bluetoothTarget")
                } else {
                    context.log(
                        "$stage bluetooth target not connected after $BLUETOOTH_ATTEMPTS attempt(s): " +
                            "$bluetoothTarget connected=${snapshot.bluetooth.connectedDevices.joinToString(",").ifBlank { "-" }}",
                    )
                    passed = false
                }
            }
        }

        return passed
    }

    private suspend fun verifyPingTarget(
        context: TestCaseExecutionContext,
        pingTarget: String,
    ): Boolean {
        repeat(PING_ATTEMPTS) { attempt ->
            val record = context.execShell(
                label = "recovery_ping_${attempt + 1}",
                command = "ping -c 1 -W 2 $pingTarget",
                requireRoot = false,
            )
            if (record.result.success) {
                return true
            }
            context.log(
                "recovery ping attempt ${attempt + 1}/$PING_ATTEMPTS failed: " +
                    "target=$pingTarget exit=${record.result.exitCode} stderr=${record.result.stderr.ifBlank { "<empty>" }}",
            )
            if (attempt + 1 < PING_ATTEMPTS) {
                delay(RETRY_DELAY_MS)
            }
        }
        return false
    }

    private suspend fun verifyBluetoothTarget(
        context: TestCaseExecutionContext,
        targetMac: String,
    ): Boolean {
        repeat(BLUETOOTH_ATTEMPTS) { attempt ->
            val snapshot = context.environment.stateProvider.readBluetoothState()
            if (snapshot.connectedDevices.any { it.equals(targetMac, ignoreCase = true) }) {
                return true
            }
            val record = context.execShell(
                label = "recovery_bluetooth_${attempt + 1}",
                command = CONNECTED_BT_MAC_COMMAND,
                requireRoot = false,
            )
            val connected = record.result.stdout.lineSequence()
                .map(String::trim)
                .filter(String::isNotEmpty)
                .map(String::uppercase)
                .toList()
            if (connected.any { it == targetMac }) {
                return true
            }
            context.log(
                "recovery bluetooth attempt ${attempt + 1}/$BLUETOOTH_ATTEMPTS failed: " +
                    "target=$targetMac connected=${connected.joinToString(",").ifBlank { "-" }} " +
                    "stderr=${record.result.stderr.ifBlank { "<empty>" }}",
            )
            if (attempt + 1 < BLUETOOTH_ATTEMPTS) {
                delay(RETRY_DELAY_MS)
            }
        }
        return false
    }

    private fun parseBluetoothTargetMac(target: String): String? {
        val match = Regex("([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})").find(target)
        return match?.value?.uppercase()
    }
}
