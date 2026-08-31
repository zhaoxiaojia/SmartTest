package com.smarttest.mobile.runner.cases.radio

import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.power.PowerCycleRecoveryChecks
import com.smarttest.mobile.runner.cases.power.PowerCycleRecoveryConfig
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
        recoveryConfig: PowerCycleRecoveryConfig? = null,
        disableSettleTimeoutMs: Long = 20_000L,
        enableSettleTimeoutMs: Long = 30_000L,
        offHoldMs: Long = 5_000L,
        onHoldMs: Long = 5_000L,
        statePollIntervalMs: Long = 1_000L,
    ): TestCaseExecutionResult {
        var commandFailures = 0
        var stateFailures = 0
        var recoveryFailures = 0

        context.log(
            "start $caseLabel: cycles=$cycleCount " +
                "disable_timeout=${disableSettleTimeoutMs / 1000}s enable_timeout=${enableSettleTimeoutMs / 1000}s " +
                "off_hold=${offHoldMs / 1000}s on_hold=${onHoldMs / 1000}s",
        )
        for (cycle in 1..cycleCount) {
            val stepPrefix = "${context.runningCase.id}.cycle.$cycle"
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = cycleCount,
                stage = "cycle $cycle/$cycleCount disable $caseLabel",
                stepId = "$stepPrefix.disable",
            )
            val disableRecord = context.execDeviceCommand(
                type = disableCommand,
                label = "${caseLabel}_disable_$cycle",
                requireRoot = false,
            )
            val disabledProbe = waitForExpectedState(
                context = context,
                cycleLabel = "cycle $cycle/$cycleCount off",
                expectedEnabled = false,
                timeoutMs = disableSettleTimeoutMs,
                pollIntervalMs = statePollIntervalMs,
                readProbe = readProbe,
            )
            if (!disableRecord.result.success) {
                commandFailures += 1
                context.log(
                    "cycle $cycle disable command failed: exit=${disableRecord.result.exitCode}, " +
                        "stderr=${disableRecord.result.stderr}",
                )
                SmartTestRunStore.finishStep(
                    "$stepPrefix.disable",
                    passed = false,
                    actual = "exit=${disableRecord.result.exitCode}",
                    error = disableRecord.result.stderr.ifBlank { disableRecord.result.stdout },
                )
            } else if (disabledProbe.enabled) {
                stateFailures += 1
                context.log("cycle $cycle disable state mismatch: expected off")
                SmartTestRunStore.finishStep(
                    "$stepPrefix.disable",
                    passed = false,
                    actual = disabledProbe.detail,
                    error = "Expected off",
                )
            } else {
                SmartTestRunStore.finishStep("$stepPrefix.disable", passed = true, actual = disabledProbe.detail)
            }
            if (!disabledProbe.enabled && offHoldMs > 0L) {
                context.log("cycle $cycle/$cycleCount off hold ${offHoldMs / 1000}s")
                delay(offHoldMs)
            }

            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = cycleCount,
                stage = "cycle $cycle/$cycleCount enable $caseLabel",
                stepId = "$stepPrefix.enable",
            )
            val enableRecord = context.execDeviceCommand(
                type = enableCommand,
                label = "${caseLabel}_enable_$cycle",
                requireRoot = false,
            )
            val enabledProbe = waitForExpectedState(
                context = context,
                cycleLabel = "cycle $cycle/$cycleCount on",
                expectedEnabled = true,
                timeoutMs = enableSettleTimeoutMs,
                pollIntervalMs = statePollIntervalMs,
                readProbe = readProbe,
            )
            if (!enableRecord.result.success) {
                commandFailures += 1
                context.log(
                    "cycle $cycle enable command failed: exit=${enableRecord.result.exitCode}, " +
                        "stderr=${enableRecord.result.stderr}",
                )
                SmartTestRunStore.finishStep(
                    "$stepPrefix.enable",
                    passed = false,
                    actual = "exit=${enableRecord.result.exitCode}",
                    error = enableRecord.result.stderr.ifBlank { enableRecord.result.stdout },
                )
            } else if (!enabledProbe.enabled) {
                stateFailures += 1
                context.log("cycle $cycle enable state mismatch: expected on")
                SmartTestRunStore.finishStep(
                    "$stepPrefix.enable",
                    passed = false,
                    actual = enabledProbe.detail,
                    error = "Expected on",
                )
            } else {
                SmartTestRunStore.finishStep("$stepPrefix.enable", passed = true, actual = enabledProbe.detail)
            }
            if (enabledProbe.enabled && onHoldMs > 0L) {
                context.log("cycle $cycle/$cycleCount on hold ${onHoldMs / 1000}s before recovery check")
                delay(onHoldMs)
            }

            if (recoveryConfig != null) {
                val recovered = PowerCycleRecoveryChecks.verifyRecoveredState(
                    context = context,
                    stage = "cycle $cycle/$cycleCount after $caseLabel enable",
                    config = recoveryConfig,
                    stepIdPrefix = stepPrefix,
                )
                if (!recovered) {
                    recoveryFailures += 1
                }
            }
        }

        val passed = commandFailures == 0 && stateFailures == 0 && recoveryFailures == 0
        val summary =
            "$caseLabel finished: cycles=$cycleCount, command_failures=$commandFailures, " +
                "state_failures=$stateFailures, recovery_failures=$recoveryFailures"
        return TestCaseExecutionResult(
            passed = passed,
            summary = if (passed) "$summary, PASS" else "$summary, FAIL",
        )
    }

    private suspend fun waitForExpectedState(
        context: TestCaseExecutionContext,
        cycleLabel: String,
        expectedEnabled: Boolean,
        timeoutMs: Long,
        pollIntervalMs: Long,
        readProbe: suspend () -> ToggleProbe,
    ): ToggleProbe {
        val deadlineMs = System.currentTimeMillis() + timeoutMs
        var lastDetail = ""
        var lastProbe = readProbe()
        while (true) {
            if (lastProbe.detail != lastDetail) {
                context.log("$cycleLabel state -> ${lastProbe.detail}")
                lastDetail = lastProbe.detail
            }
            if (lastProbe.enabled == expectedEnabled || System.currentTimeMillis() >= deadlineMs) {
                return lastProbe
            }
            delay(pollIntervalMs.coerceAtLeast(250L))
            lastProbe = readProbe()
        }
    }
}
