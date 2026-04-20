package com.smarttest.mobile.runner.cases.radio

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.device.model.CommandType

class BluetoothOnOffCaseExecutor : TestCaseExecutor {
    override val caseId: String = "bt_onoff_scan"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 1000).coerceAtLeast(1)
        return ToggleCaseSupport.runToggleCycles(
            context = context,
            cycleCount = cycleCount,
            caseLabel = "bt_onoff",
            disableCommand = CommandType.BluetoothDisable,
            enableCommand = CommandType.BluetoothEnable,
            readProbe = {
                val state = context.environment.stateProvider.readBluetoothState()
                ToggleProbe(
                    enabled = state.enabled,
                    detail = "bt(enabled=${state.enabled}, name=${state.adapterName ?: "-"}, discovering=${state.discovering})",
                )
            },
        )
    }
}
