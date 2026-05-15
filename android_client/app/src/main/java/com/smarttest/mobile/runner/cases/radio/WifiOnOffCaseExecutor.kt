package com.smarttest.mobile.runner.cases.radio

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.cases.power.PowerCycleRecoveryConfig
import com.smarttest.mobile.runner.device.model.CommandType

class WifiOnOffCaseExecutor : TestCaseExecutor {
    override val caseId: String = "wifi_onoff_scan"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 1000).coerceAtLeast(1)
        val pingTarget = context.parameter("ping_target", "").trim()
        if (pingTarget.isEmpty()) {
            context.log("wifi_onoff reconnect check requires ping_target; no ping check can run with an empty target")
            return TestCaseExecutionResult(
                passed = false,
                summary = "Wi-Fi OnOff reconnect requires ping_target.",
            )
        }
        return ToggleCaseSupport.runToggleCycles(
            context = context,
            cycleCount = cycleCount,
            caseLabel = "wifi_onoff",
            disableCommand = CommandType.WifiDisable,
            enableCommand = CommandType.WifiEnable,
            readProbe = {
                val state = context.environment.stateProvider.readWifiState()
                ToggleProbe(
                    enabled = state.enabled,
                    detail = "wifi(enabled=${state.enabled}, ssid=${state.connectedSsid ?: "-"}, ip=${state.ipAddress ?: "-"})",
                )
            },
            recoveryConfig = PowerCycleRecoveryConfig(
                pingTarget = pingTarget,
                bluetoothTarget = "",
            ),
            disableSettleTimeoutMs = 20_000L,
            enableSettleTimeoutMs = 30_000L,
        )
    }
}
