package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.device.model.CommandType
import kotlinx.coroutines.delay

class AutoRebootCaseExecutor : TestCaseExecutor {
    override val caseId: String = "auto_reboot"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 20).coerceAtLeast(1)
        val intervalSec = context.longParameter("interval_sec", 100L).coerceAtLeast(1L)
        val sessionStore = AutoRebootSessionStore(context.appContext)
        val initialSession = sessionStore.load() ?: AutoRebootSession(
            active = true,
            totalCycles = cycleCount,
            intervalSec = intervalSec,
            completedCycles = 0,
            awaitingPostBootCheck = false,
        ).also(sessionStore::save)

        var session = initialSession

        if (session.awaitingPostBootCheck) {
            val cycle = session.completedCycles + 1
            context.log("resume after reboot for cycle $cycle/${session.totalCycles}")
            delay(session.intervalSec * 1000L)
            PowerCycleSupport.captureRadioState(
                context = context,
                stage = "cycle $cycle/${session.totalCycles} after reboot",
            )
            session = session.copy(
                completedCycles = cycle,
                awaitingPostBootCheck = false,
            )
            if (cycle >= session.totalCycles) {
                sessionStore.clear()
                return TestCaseExecutionResult(
                    passed = true,
                    summary = "AutoReboot finished: cycles=${session.totalCycles}, PASS",
                )
            }
            sessionStore.save(session)
        }

        val nextCycle = session.completedCycles + 1
        context.log("trigger reboot cycle $nextCycle/${session.totalCycles}")
        sessionStore.save(
            session.copy(
                awaitingPostBootCheck = true,
            ),
        )

        val rebootRecord = context.execDeviceCommand(
            type = CommandType.Reboot,
            label = "reboot_cycle_$nextCycle",
        )
        if (!rebootRecord.result.success) {
            sessionStore.clear()
            return TestCaseExecutionResult(
                passed = false,
                summary = "AutoReboot failed to trigger reboot on cycle $nextCycle: ${rebootRecord.result.stderr.ifBlank { rebootRecord.result.stdout }}",
            )
        }

        return TestCaseExecutionResult(
            passed = true,
            summary = "AutoReboot cycle $nextCycle/${session.totalCycles} reboot requested; waiting for boot resume",
            pendingResume = true,
        )
    }
}
