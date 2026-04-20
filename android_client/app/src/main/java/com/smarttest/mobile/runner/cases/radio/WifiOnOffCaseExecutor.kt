package com.smarttest.mobile.runner.cases.radio

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.device.model.CommandType

class WifiOnOffCaseExecutor : TestCaseExecutor {
    override val caseId: String = "wifi_onoff_scan"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 1000).coerceAtLeast(1)
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
        )
    }
}
