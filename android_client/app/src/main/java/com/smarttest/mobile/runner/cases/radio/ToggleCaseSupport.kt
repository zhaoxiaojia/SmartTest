package com.smarttest.mobile.runner.cases.radio

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.device.model.CommandType
import kotlinx.coroutines.delay

data class ToggleProbe(
    val enabled: Boolean,
    val detail: String,
)

object ToggleCaseSupport {
    suspend fun runToggleCycles(
        context: TestCaseExecutionContext,
        cycleCount: Int,
        caseLabel: String,
        disableCommand: CommandType,
        enableCommand: CommandType,
        readProbe: suspend () -> ToggleProbe,
        settleDelayMs: Long = 2_000L,
    ): TestCaseExecutionResult {
        var commandFailures = 0
        var stateFailures = 0

        context.log("start $caseLabel: cycles=$cycleCount")
        for (cycle in 1..cycleCount) {
            val disableRecord = context.execDeviceCommand(
                type = disableCommand,
                label = "${caseLabel}_disable_$cycle",
            )
            delay(settleDelayMs)
            val disabledProbe = readProbe()
            context.log("cycle $cycle/$cycleCount off -> ${disabledProbe.detail}")
            if (!disableRecord.result.success) {
                commandFailures += 1
                context.log(
                    "cycle $cycle disable command failed: exit=${disableRecord.result.exitCode}, " +
                        "stderr=${disableRecord.result.stderr}",
                )
            } else if (disabledProbe.enabled) {
                stateFailures += 1
                context.log("cycle $cycle disable state mismatch: expected off")
            }

            val enableRecord = context.execDeviceCommand(
                type = enableCommand,
                label = "${caseLabel}_enable_$cycle",
            )
            delay(settleDelayMs)
            val enabledProbe = readProbe()
            context.log("cycle $cycle/$cycleCount on -> ${enabledProbe.detail}")
            if (!enableRecord.result.success) {
                commandFailures += 1
                context.log(
                    "cycle $cycle enable command failed: exit=${enableRecord.result.exitCode}, " +
                        "stderr=${enableRecord.result.stderr}",
                )
            } else if (!enabledProbe.enabled) {
                stateFailures += 1
                context.log("cycle $cycle enable state mismatch: expected on")
            }
        }

        val passed = commandFailures == 0 && stateFailures == 0
        val summary = "$caseLabel finished: cycles=$cycleCount, command_failures=$commandFailures, state_failures=$stateFailures"
        return TestCaseExecutionResult(
            passed = passed,
            summary = if (passed) "$summary, PASS" else "$summary, FAIL",
        )
    }
}
