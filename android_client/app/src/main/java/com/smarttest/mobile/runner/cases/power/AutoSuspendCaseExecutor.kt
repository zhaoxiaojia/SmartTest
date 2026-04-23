package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.device.model.CommandType
import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.runner.SmartTestUiLauncher

class AutoSuspendCaseExecutor : TestCaseExecutor {
    override val caseId: String = "auto_suspend"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 20).coerceAtLeast(1)
        val intervalSec = context.longParameter("interval_sec", 100L).coerceAtLeast(1L)
        var suspendFailures = 0

        context.log("start auto suspend: cycles=$cycleCount, interval=${intervalSec}s")
        for (cycle in 1..cycleCount) {
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = cycleCount,
                stage = "loop $cycle/$cycleCount entering suspend for ${intervalSec}s",
            )
            context.log("cycle $cycle/$cycleCount suspend")

            val suspendRecord = context.execDeviceCommand(
                type = CommandType.Suspend,
                label = "suspend_cycle_$cycle",
                args = mapOf("wake_after_sec" to intervalSec.toString()),
            )
            if (!suspendRecord.result.success) {
                suspendFailures += 1
                context.log(
                    "suspend failed on cycle $cycle: exit=${suspendRecord.result.exitCode}, " +
                        "stderr=${suspendRecord.result.stderr}",
                )
                continue
            }

            SmartTestUiLauncher.launchMainActivity(context.appContext)
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = cycleCount,
                stage = "loop $cycle/$cycleCount resumed from suspend",
            )
            PowerCycleSupport.captureRadioState(
                context = context,
                stage = "cycle $cycle/$cycleCount after suspend",
            )
        }

        val passed = suspendFailures == 0
        val summary = "AutoSuspend finished: cycles=$cycleCount, suspend_failures=$suspendFailures"
        return TestCaseExecutionResult(
            passed = passed,
            summary = if (passed) "$summary, PASS" else "$summary, FAIL",
        )
    }
}
