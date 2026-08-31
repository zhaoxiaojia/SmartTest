package com.smarttest.mobile.runner.cases.radio

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.cases.power.PowerCycleRecoveryConfig
import com.smarttest.mobile.runner.device.model.CommandType

class BluetoothOnOffCaseExecutor : TestCaseExecutor {
    override val caseId: String = "bt_onoff_scan"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 1000).coerceAtLeast(1)
        val onWaitMs = context.longParameter("on_wait_sec", 5L).coerceAtLeast(0L) * 1000L
        val offWaitMs = context.longParameter("off_wait_sec", 5L).coerceAtLeast(0L) * 1000L
        val bluetoothTarget = context.parameter("bt_target", "").trim()
        if (bluetoothTarget.isEmpty() || bluetoothTarget.equals("none", ignoreCase = true)) {
            context.log("bt_onoff reconnect check requires bt_target; no Bluetooth reconnect check can run without a target")
            return TestCaseExecutionResult(
                passed = false,
                summary = "BT OnOff reconnect requires bt_target.",
            )
        }
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
            recoveryConfig = PowerCycleRecoveryConfig(
                pingTarget = "",
                bluetoothTarget = bluetoothTarget,
            ),
            disableSettleTimeoutMs = 20_000L,
            enableSettleTimeoutMs = 30_000L,
            offHoldMs = offWaitMs,
            onHoldMs = onWaitMs,
        )
    }
}
