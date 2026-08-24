package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.SmartTestRunStore
import kotlinx.coroutines.delay

data class PowerCycleRecoveryConfig(
    val pingTarget: String,
    val bluetoothTarget: String,
)

object PowerCycleRecoveryChecks {
    private const val PING_ATTEMPTS = 10
    private const val BLUETOOTH_TIMEOUT_MS = 60_000L
    private const val RETRY_DELAY_MS = 3_000L

    private data class BluetoothCheckResult(
        val connected: Boolean,
        val observedDevices: List<String>,
    )

    suspend fun verifyRecoveredState(
        context: TestCaseExecutionContext,
        stage: String,
        config: PowerCycleRecoveryConfig,
        stepIdPrefix: String? = null,
    ): Boolean {
        val captureStepId = stepIdPrefix?.let { "$it.capture_radio_state" }
        if (captureStepId != null) {
            SmartTestRunStore.updateProgress(null, null, "$stage capture radio state", captureStepId)
        }
        val snapshot = PowerCycleSupport.captureRadioState(context = context, stage = stage)
        if (captureStepId != null) {
            SmartTestRunStore.finishStep(
                captureStepId,
                passed = true,
                actual = "wifiIp=${snapshot.wifi.ipAddress ?: "-"} bluetooth=${snapshot.bluetooth.adapterName ?: "-"}",
            )
        }
        var passed = true

        val pingTarget = config.pingTarget.trim()
        if (pingTarget.isNotEmpty()) {
            val pingStepId = stepIdPrefix?.let { "$it.ping" }
            if (pingStepId != null) {
                SmartTestRunStore.updateProgress(null, null, "$stage ping $pingTarget", pingStepId)
            }
            val pingOk = verifyPingTarget(context, pingTarget)
            if (pingOk) {
                context.log("$stage ping target reachable: $pingTarget")
                if (pingStepId != null) {
                    SmartTestRunStore.finishStep(pingStepId, passed = true, actual = "$pingTarget reachable")
                }
            } else {
                context.log(
                    "$stage ping target unreachable after $PING_ATTEMPTS attempt(s): $pingTarget " +
                        "wifiIp=${snapshot.wifi.ipAddress ?: "-"} ssid=${snapshot.wifi.connectedSsid ?: "-"}",
                )
                if (pingStepId != null) {
                    SmartTestRunStore.finishStep(
                        pingStepId,
                        passed = false,
                        actual = "wifiIp=${snapshot.wifi.ipAddress ?: "-"} ssid=${snapshot.wifi.connectedSsid ?: "-"}",
                        error = "Ping target unreachable after $PING_ATTEMPTS attempt(s): $pingTarget",
                    )
                }
                passed = false
            }
        }

        val bluetoothTarget = config.bluetoothTarget.trim()
        if (bluetoothTarget.isNotEmpty()) {
            val bluetoothStepId = stepIdPrefix?.let { "$it.bluetooth" }
            if (bluetoothStepId != null) {
                SmartTestRunStore.updateProgress(null, null, "$stage verify Bluetooth target", bluetoothStepId)
            }
            val targetMac = parseBluetoothTargetMac(bluetoothTarget)
            if (targetMac == null) {
                context.log("$stage invalid bluetooth target format: $bluetoothTarget")
                if (bluetoothStepId != null) {
                    SmartTestRunStore.finishStep(
                        bluetoothStepId,
                        passed = false,
                        error = "Invalid bluetooth target format: $bluetoothTarget",
                    )
                }
                passed = false
            } else {
                val result = verifyBluetoothTarget(context, targetMac)
                if (result.connected) {
                    context.log("$stage bluetooth target connected: $bluetoothTarget")
                    if (bluetoothStepId != null) {
                        SmartTestRunStore.finishStep(bluetoothStepId, passed = true, actual = "$targetMac connected")
                    }
                } else {
                    context.log(
                        "$stage bluetooth target not connected within ${BLUETOOTH_TIMEOUT_MS / 1000}s: " +
                            "$bluetoothTarget connected=${result.observedDevices.joinToString(",").ifBlank { "-" }}",
                    )
                    if (bluetoothStepId != null) {
                        SmartTestRunStore.finishStep(
                            bluetoothStepId,
                            passed = false,
                            actual = "connected=${result.observedDevices.joinToString(",").ifBlank { "-" }}",
                            error = "Bluetooth target not connected within ${BLUETOOTH_TIMEOUT_MS / 1000}s: $bluetoothTarget",
                        )
                    }
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
        if (!isValidPingTarget(pingTarget)) {
            context.log("invalid recovery ping target format: $pingTarget")
            return false
        }
        var lastFailureSignature = ""
        repeat(PING_ATTEMPTS) { attempt ->
            val record = context.execShell(
                label = "recovery_ping_${attempt + 1}",
                command = "ping -c 1 -W 2 ${shellQuote(pingTarget)}",
                requireRoot = false,
            )
            if (record.result.success) {
                return true
            }
            val failureSignature = "exit=${record.result.exitCode} stderr=${record.result.stderr.ifBlank { "<empty>" }}"
            if (failureSignature != lastFailureSignature) {
                context.log(
                    "recovery ping state changed on attempt ${attempt + 1}/$PING_ATTEMPTS: " +
                        "target=$pingTarget $failureSignature",
                )
                lastFailureSignature = failureSignature
            }
            if (attempt + 1 < PING_ATTEMPTS) {
                delay(RETRY_DELAY_MS)
            }
        }
        return false
    }

    private fun isValidPingTarget(target: String): Boolean {
        return Regex("[A-Za-z0-9][A-Za-z0-9.:-]*").matches(target)
    }

    private fun shellQuote(value: String): String {
        return "'${value.replace("'", "'\\''")}'"
    }

    private suspend fun verifyBluetoothTarget(
        context: TestCaseExecutionContext,
        targetMac: String,
    ): BluetoothCheckResult {
        val deadlineMs = System.currentTimeMillis() + BLUETOOTH_TIMEOUT_MS
        var attempt = 1
        var lastObserved = emptyList<String>()
        var lastFailureSignature = ""
        while (System.currentTimeMillis() <= deadlineMs) {
            val record = context.execShell(
                label = "recovery_bluetooth_${attempt}",
                command = "dumpsys bluetooth_manager",
                requireRoot = false,
            )
            val connected = connectedBluetoothAddressesFromDumpsys(record.result.stdout).distinct()
            lastObserved = connected
            if (connected.any { bluetoothAddressMatches(targetMac, it) }) {
                return BluetoothCheckResult(connected = true, observedDevices = connected)
            }
            val failureSignature =
                "exit=${record.result.exitCode} connected=${connected.joinToString(",").ifBlank { "-" }}"
            if (failureSignature != lastFailureSignature) {
                context.log(
                    "recovery bluetooth state changed on attempt $attempt: " +
                        "target=$targetMac $failureSignature",
                )
                lastFailureSignature = failureSignature
            }
            val remainingMs = deadlineMs - System.currentTimeMillis()
            if (remainingMs > 0) {
                delay(minOf(RETRY_DELAY_MS, remainingMs))
            }
            attempt += 1
        }
        return BluetoothCheckResult(connected = false, observedDevices = lastObserved)
    }

    private fun parseBluetoothTargetMac(target: String): String? {
        val match = Regex("([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})").find(target)
        return match?.value?.uppercase()
    }

    private fun bluetoothAddressMatches(targetMac: String, observedMac: String): Boolean {
        val observedAddress = parseBluetoothTargetMac(observedMac) ?: observedMac.uppercase()
        if (observedAddress.equals(targetMac, ignoreCase = true)) {
            return true
        }
        val targetParts = targetMac.uppercase().split(":")
        val observedParts = observedAddress.uppercase().split(":")
        if (targetParts.size != 6 || observedParts.size != 6) {
            return false
        }
        val maskedPrefix = observedParts.take(4).all { it == "XX" }
        return maskedPrefix && observedParts.takeLast(2) == targetParts.takeLast(2)
    }

    private fun connectedBluetoothAddressesFromDumpsys(raw: String): List<String> {
        val addresses = mutableListOf<String>()
        val seen = mutableSetOf<String>()
        var pendingPeer = ""
        var pendingStateMachine = ""

        raw.lineSequence().forEach { line ->
            val text = line.trim()
            val lower = text.lowercase()

            if ("statemachine" in lower && " for " in lower) {
                pendingStateMachine = firstBluetoothAddress(text)
                if ("state=connected" in lower) {
                    appendBluetoothAddress(addresses, seen, pendingStateMachine)
                    pendingStateMachine = ""
                }
                return@forEach
            }

            if (pendingStateMachine.isNotEmpty() && "state=connected" in lower) {
                appendBluetoothAddress(addresses, seen, pendingStateMachine)
                pendingStateMachine = ""
                return@forEach
            }

            if ("state=disconnected" in lower) {
                pendingStateMachine = ""
            }

            if (lower.startsWith("peer:") || " active peer:" in lower) {
                pendingPeer = firstBluetoothAddress(text)
                return@forEach
            }

            if (pendingPeer.isNotEmpty() && lower.startsWith("connected:")) {
                if ("true" in lower) {
                    appendBluetoothAddress(addresses, seen, pendingPeer)
                }
                pendingPeer = ""
            }

            if ("mcurrentdevice:" in lower) {
                appendBluetoothAddress(addresses, seen, firstBluetoothAddress(text))
            }
        }
        return addresses
    }

    private fun appendBluetoothAddress(addresses: MutableList<String>, seen: MutableSet<String>, raw: String) {
        val address = raw.trim().uppercase()
        if (address.isNotEmpty() && address != "00:00:00:00:00:00" && seen.add(address)) {
            addresses.add(address)
        }
    }

    private fun firstBluetoothAddress(text: String): String {
        return Regex("(?:[0-9A-Fa-fXx]{2}:){5}[0-9A-Fa-fXx]{2}").find(text)?.value.orEmpty()
    }
}
