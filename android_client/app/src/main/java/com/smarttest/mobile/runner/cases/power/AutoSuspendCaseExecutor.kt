package com.smarttest.mobile.runner.cases.power

import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.runner.SmartTestUiLauncher
import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import kotlinx.coroutines.delay

class AutoSuspendCaseExecutor : TestCaseExecutor {
    override val caseId: String = "auto_suspend"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val cycleCount = context.intParameter("cycle_count", 20).coerceAtLeast(1)
        val requestedIntervalSec = context.longParameter("interval_sec", 100L).coerceAtLeast(1L)
        val intervalSec = requestedIntervalSec.coerceAtLeast(MIN_INTERVAL_SEC)
        val recoveryConfig = PowerCycleRecoveryConfig(
            pingTarget = context.parameter("ping_target", ""),
            bluetoothTarget = context.parameter("bt_target", ""),
        )
        val sessionStore = AutoSuspendSessionStore(context.appContext)
        val requestSession = AutoSuspendSession(
            totalCycles = cycleCount,
            intervalSec = intervalSec,
            completedCycles = 0,
            awaitingResume = false,
            source = context.request.source,
            trigger = context.request.trigger,
            requestId = context.request.requestId,
        )
        context.log(
            "request parameters: cycles=$cycleCount interval=${requestedIntervalSec}s " +
                "effective_interval=${intervalSec}s " +
                "trigger=${context.request.trigger} requestId=${context.request.requestId}",
        )
        AutoSuspendDebugLogger.append(
            context.appContext,
            "executor start cycles=$cycleCount requestedIntervalSec=$requestedIntervalSec effectiveIntervalSec=$intervalSec trigger=${context.request.trigger} requestId=${context.request.requestId}",
        )
        var session = reconcileSession(
            context = context,
            sessionStore = sessionStore,
            requestSession = requestSession,
        )

        if (session.awaitingResume) {
            val cycle = session.completedCycles + 1
            SmartTestUiLauncher.launchMainActivity(context.appContext)
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = session.totalCycles,
                stage = "loop $cycle/${session.totalCycles} resumed from deep suspend",
            )
            context.log(
                "resume after deep suspend for cycle $cycle/${session.totalCycles} requestId=${session.requestId}",
            )
            AutoSuspendDebugLogger.append(
                context.appContext,
                "resume after deep suspend cycle=$cycle totalCycles=${session.totalCycles} requestId=${session.requestId}",
            )
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = session.totalCycles,
                stage = "loop $cycle/${session.totalCycles} waiting ${session.intervalSec}s after deep suspend",
            )
            context.log(
                "wait ${session.intervalSec}s after deep suspend for cycle $cycle/${session.totalCycles} requestId=${session.requestId}",
            )
            AutoSuspendDebugLogger.append(
                context.appContext,
                "wait after deep suspend cycle=$cycle intervalSec=${session.intervalSec} requestId=${session.requestId}",
            )
            delay(session.intervalSec * 1000L)
            val recovered = PowerCycleRecoveryChecks.verifyRecoveredState(
                context = context,
                stage = "cycle $cycle/${session.totalCycles} after deep suspend",
                config = recoveryConfig,
            )
            if (!recovered) {
                sessionStore.clear()
                AutoSuspendPowerController.cancelResumeAlarm(context.appContext)
                return TestCaseExecutionResult(
                    passed = false,
                    summary = "AutoSuspend failed recovery checks on cycle $cycle/${session.totalCycles}",
                )
            }
            session = session.copy(
                completedCycles = cycle,
                awaitingResume = false,
            )
            if (cycle >= session.totalCycles) {
                sessionStore.clear()
                AutoSuspendPowerController.cancelResumeAlarm(context.appContext)
                return TestCaseExecutionResult(
                    passed = true,
                    summary = "AutoSuspend finished: cycles=${session.totalCycles}, PASS",
                )
            }
            sessionStore.save(session)
        }

        val nextCycle = session.completedCycles + 1
        SmartTestRunStore.updateProgress(
            currentLoop = nextCycle,
            totalLoops = session.totalCycles,
            stage = "loop $nextCycle/${session.totalCycles} entering deep suspend",
        )
        context.log(
            "request dut self deep suspend cycle $nextCycle/${session.totalCycles} requestId=${session.requestId}",
        )
        AutoSuspendDebugLogger.append(
            context.appContext,
            "request deep suspend cycle=$nextCycle totalCycles=${session.totalCycles} requestId=${session.requestId}",
        )
        sessionStore.save(
            session.copy(
                awaitingResume = true,
            ),
        )

        return try {
            AutoSuspendPowerController.scheduleResumeAlarm(
                context = context.appContext,
                delaySec = SUSPEND_WAKE_DELAY_SEC,
                requestId = session.requestId,
            )
            AutoSuspendPowerController.goToSleep(context.appContext)
            SmartTestRunStore.updateProgress(
                currentLoop = nextCycle,
                totalLoops = session.totalCycles,
                stage = "loop $nextCycle/${session.totalCycles} waiting for deep suspend resume",
            )
            TestCaseExecutionResult(
                passed = true,
                pendingResume = true,
                summary = "AutoSuspend pending deep suspend resume on cycle $nextCycle/${session.totalCycles}",
            )
        } catch (error: Throwable) {
            sessionStore.clear()
            AutoSuspendPowerController.cancelResumeAlarm(context.appContext)
            AutoSuspendDebugLogger.append(
                context.appContext,
                "deep suspend request failed cycle=$nextCycle totalCycles=${session.totalCycles} requestId=${session.requestId}",
                error,
            )
            context.log("deep suspend request failed on cycle $nextCycle: ${error.message ?: error.javaClass.simpleName}")
            TestCaseExecutionResult(
                passed = false,
                summary = "AutoSuspend failed to enter deep suspend on cycle $nextCycle/${session.totalCycles}",
            )
        }
    }

    private fun reconcileSession(
        context: TestCaseExecutionContext,
        sessionStore: AutoSuspendSessionStore,
        requestSession: AutoSuspendSession,
    ): AutoSuspendSession {
        val saved = sessionStore.load()
        if (saved == null) {
            context.log("start new auto suspend session requestId=${requestSession.requestId}")
            sessionStore.save(requestSession)
            return requestSession
        }

        context.log(
            "loaded saved auto suspend session: cycles=${saved.totalCycles}, interval=${saved.intervalSec}, " +
                "completed=${saved.completedCycles}, awaitingResume=${saved.awaitingResume}, " +
                "trigger=${saved.trigger}, requestId=${saved.requestId}",
        )

        if (!saved.isRecoverable()) {
            context.log("discard stale auto suspend session: invalid saved state")
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
                "discard stale auto suspend session: " +
                    "saved(cycles=${saved.totalCycles}, interval=${saved.intervalSec}, trigger=${saved.trigger}, requestId=${saved.requestId}) " +
                    "!= request(cycles=${requestSession.totalCycles}, interval=${requestSession.intervalSec}, trigger=${requestSession.trigger}, requestId=${requestSession.requestId})",
            )
            sessionStore.clear()
            sessionStore.save(requestSession)
            return requestSession
        }

        context.log("resume saved auto suspend session requestId=${saved.requestId}")
        return saved
    }

    companion object {
        private const val MIN_INTERVAL_SEC = 30L
        private const val SUSPEND_WAKE_DELAY_SEC = 20L
    }
}
