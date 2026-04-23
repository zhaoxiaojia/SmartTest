package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.runner.SmartTestUiLauncher
import com.smarttest.mobile.runner.device.model.CommandType
import kotlinx.coroutines.delay

class AutoRebootCaseExecutor : TestCaseExecutor {
    override val caseId: String = "auto_reboot"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 20).coerceAtLeast(1)
        val intervalSec = context.longParameter("interval_sec", 100L).coerceAtLeast(1L)
        val sessionStore = AutoRebootSessionStore(context.appContext)
        val requestSession = AutoRebootSession(
            active = true,
            totalCycles = cycleCount,
            intervalSec = intervalSec,
            completedCycles = 0,
            awaitingPostBootCheck = false,
            source = context.request.source,
            trigger = context.request.trigger,
            requestId = context.request.requestId,
        )
        context.log(
            "request parameters: cycles=$cycleCount interval=${intervalSec}s " +
                "trigger=${context.request.trigger} requestId=${context.request.requestId}",
        )
        val initialSession = reconcileSession(
            context = context,
            sessionStore = sessionStore,
            requestSession = requestSession,
        )

        var session = initialSession

        if (session.awaitingPostBootCheck) {
            val cycle = session.completedCycles + 1
            SmartTestUiLauncher.launchMainActivity(context.appContext)
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = session.totalCycles,
                stage = "loop $cycle/${session.totalCycles} waiting ${session.intervalSec}s after reboot",
            )
            context.log(
                "resume after reboot for cycle $cycle/${session.totalCycles} requestId=${session.requestId}",
            )
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
        SmartTestRunStore.updateProgress(
            currentLoop = nextCycle,
            totalLoops = session.totalCycles,
            stage = "loop $nextCycle/${session.totalCycles} rebooting dut",
        )
        context.log(
            "request dut self reboot cycle $nextCycle/${session.totalCycles} requestId=${session.requestId}",
        )
        sessionStore.save(
            session.copy(
                awaitingPostBootCheck = true,
            ),
        )
        val rebootRecord = context.execDeviceCommand(
            type = CommandType.Reboot,
            label = "reboot_cycle_$nextCycle",
            requireRoot = false,
        )
        context.log(
            "reboot command result on cycle $nextCycle: " +
                "success=${rebootRecord.result.success}, " +
                "exit=${rebootRecord.result.exitCode}, " +
                "stdout=${rebootRecord.result.stdout.ifBlank { "<empty>" }}, " +
                "stderr=${rebootRecord.result.stderr.ifBlank { "<empty>" }}",
        )
        if (!rebootRecord.result.success) {
            sessionStore.clear()
            context.log(
                "reboot command failed on cycle $nextCycle: exit=${rebootRecord.result.exitCode}, " +
                    "stdout=${rebootRecord.result.stdout}, stderr=${rebootRecord.result.stderr}",
            )
            return TestCaseExecutionResult(
                passed = false,
                summary = "AutoReboot failed to reboot DUT on cycle $nextCycle/${session.totalCycles}",
            )
        }
        SmartTestRunStore.updateProgress(
            currentLoop = nextCycle,
            totalLoops = session.totalCycles,
            stage = "loop $nextCycle/${session.totalCycles} waiting for dut reboot",
        )
        delay(5_000L)
        sessionStore.clear()
        context.log(
            "reboot command returned but DUT stayed alive for 5s on cycle $nextCycle; " +
                "treat as reboot failure",
        )
        return TestCaseExecutionResult(
            passed = false,
            summary = "AutoReboot failed: DUT did not restart after reboot command on cycle $nextCycle/${session.totalCycles}",
        )
    }

    private fun reconcileSession(
        context: TestCaseExecutionContext,
        sessionStore: AutoRebootSessionStore,
        requestSession: AutoRebootSession,
    ): AutoRebootSession {
        val saved = sessionStore.load()
        if (saved == null) {
            context.log("start new auto reboot session requestId=${requestSession.requestId}")
            sessionStore.save(requestSession)
            return requestSession
        }

        context.log(
            "loaded saved auto reboot session: cycles=${saved.totalCycles}, interval=${saved.intervalSec}, " +
                "completed=${saved.completedCycles}, awaitingPostBoot=${saved.awaitingPostBootCheck}, " +
                "trigger=${saved.trigger}, requestId=${saved.requestId}",
        )

        if (!saved.isRecoverable()) {
            context.log("discard stale auto reboot session: invalid saved state")
            sessionStore.clear()
            sessionStore.save(requestSession)
            return requestSession
        }

        if (
            !saved.matchesRequest(
                totalCycles = requestSession.totalCycles,
                intervalSec = requestSession.intervalSec,
                source = requestSession.source,
                trigger = requestSession.trigger,
                requestId = requestSession.requestId,
            )
        ) {
            context.log(
                "discard stale auto reboot session: " +
                    "saved(cycles=${saved.totalCycles}, interval=${saved.intervalSec}, trigger=${saved.trigger}, requestId=${saved.requestId}) " +
                    "!= request(cycles=${requestSession.totalCycles}, interval=${requestSession.intervalSec}, trigger=${requestSession.trigger}, requestId=${requestSession.requestId})",
            )
            sessionStore.clear()
            sessionStore.save(requestSession)
            return requestSession
        }

        context.log("resume saved auto reboot session requestId=${saved.requestId}")
        return saved
    }
}
