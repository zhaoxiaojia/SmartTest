package com.smarttest.mobile.runner.cases.power

import android.os.SystemClock
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
            sleepRequestElapsedRealtimeMs = 0L,
            sleepRequestUptimeMs = 0L,
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
            "executor start cycles=$cycleCount requestedIntervalSec=$requestedIntervalSec " +
                "effectiveIntervalSec=$intervalSec source=${context.request.source} " +
                "trigger=${context.request.trigger} requestId=${context.request.requestId} " +
                "elapsedNow=${SystemClock.elapsedRealtime()} uptimeNow=${SystemClock.uptimeMillis()}",
        )
        var session = reconcileSession(
            context = context,
            sessionStore = sessionStore,
            requestSession = requestSession,
        )

        if (session.awaitingResume) {
            val cycle = session.completedCycles + 1
            val deepSleep = measureDeepSleep(session)
            launchSmartTestUiAndWait(context, cycle, session.totalCycles, session.requestId)
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
            context.log(
                "deep suspend evidence for cycle $cycle/${session.totalCycles}: " +
                    "elapsed=${deepSleep.elapsedDeltaMs}ms uptime=${deepSleep.uptimeDeltaMs}ms " +
                    "deep_sleep=${deepSleep.deepSleepMs}ms requestId=${session.requestId} " +
                    "elapsedReset=${deepSleep.elapsedReset} uptimeReset=${deepSleep.uptimeReset} " +
                    "reqElapsed=${deepSleep.requestElapsedMs} reqUptime=${deepSleep.requestUptimeMs} " +
                    "nowElapsed=${deepSleep.nowElapsedMs} nowUptime=${deepSleep.nowUptimeMs}",
            )
            AutoSuspendDebugLogger.append(
                context.appContext,
                "deep suspend evidence cycle=$cycle elapsedMs=${deepSleep.elapsedDeltaMs} " +
                    "uptimeMs=${deepSleep.uptimeDeltaMs} deepSleepMs=${deepSleep.deepSleepMs} requestId=${session.requestId}",
            )
            if (deepSleep.deepSleepMs < MIN_DEEP_SLEEP_MS) {
                val likelyNoSuspendOrReboot = kotlin.math.abs(
                    deepSleep.elapsedDeltaMs - deepSleep.uptimeDeltaMs,
                ) <= 1_000L
                context.log(
                    "deep suspend verification warning on cycle $cycle/${session.totalCycles}: " +
                        "deep_sleep=${deepSleep.deepSleepMs}ms is below threshold ${MIN_DEEP_SLEEP_MS}ms; " +
                        "likely_no_suspend_or_reboot=$likelyNoSuspendOrReboot; " +
                        "elapsedReset=${deepSleep.elapsedReset} uptimeReset=${deepSleep.uptimeReset}; " +
                        "continue execution with recovery checks",
                )
            }
            SmartTestRunStore.updateProgress(
                currentLoop = cycle,
                totalLoops = session.totalCycles,
                stage = "loop $cycle/${session.totalCycles} waiting ${session.intervalSec}s after deep suspend",
            )
            context.log(
                "wait ${session.intervalSec}s after deep suspend for cycle $cycle/${session.totalCycles} requestId=${session.requestId}; " +
                    "interval countdown starts after SmartTest UI ready",
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
        val sleepRequestElapsedRealtimeMs = SystemClock.elapsedRealtime()
        val sleepRequestUptimeMs = SystemClock.uptimeMillis()
        AutoSuspendDebugLogger.append(
            context.appContext,
            "persist awaitingResume=true cycle=$nextCycle requestId=${session.requestId} " +
                "sleepRequestElapsedMs=$sleepRequestElapsedRealtimeMs sleepRequestUptimeMs=$sleepRequestUptimeMs",
        )
        sessionStore.save(
            session.copy(
                awaitingResume = true,
                sleepRequestElapsedRealtimeMs = sleepRequestElapsedRealtimeMs,
                sleepRequestUptimeMs = sleepRequestUptimeMs,
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
                "deep suspend request failed cycle=$nextCycle totalCycles=${session.totalCycles} " +
                    "requestId=${session.requestId}",
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
        AutoSuspendDebugLogger.append(
            context.appContext,
            "reconcile loaded session cycles=${saved.totalCycles} intervalSec=${saved.intervalSec} " +
                "completed=${saved.completedCycles} awaitingResume=${saved.awaitingResume} " +
                "sleepRequestElapsedMs=${saved.sleepRequestElapsedRealtimeMs} " +
                "sleepRequestUptimeMs=${saved.sleepRequestUptimeMs} source=${saved.source} " +
                "trigger=${saved.trigger} requestId=${saved.requestId}",
        )

        if (!saved.isRecoverable()) {
            context.log("discard stale auto suspend session: invalid saved state")
            AutoSuspendDebugLogger.append(
                context.appContext,
                "reconcile discard reason=invalid_saved_state requestId=${saved.requestId}",
            )
            sessionStore.clear()
            sessionStore.save(requestSession)
            return requestSession
        }

        val sessionAgeMs = (SystemClock.elapsedRealtime() - saved.sleepRequestElapsedRealtimeMs).coerceAtLeast(0L)
        if (saved.awaitingResume && sessionAgeMs > MAX_AWAITING_RESUME_AGE_MS) {
            context.log(
                "discard stale auto suspend session: awaitingResume age ${sessionAgeMs}ms " +
                    "exceeds ${MAX_AWAITING_RESUME_AGE_MS}ms",
            )
            AutoSuspendDebugLogger.append(
                context.appContext,
                "reconcile discard reason=awaiting_resume_too_old ageMs=$sessionAgeMs requestId=${saved.requestId}",
            )
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
            AutoSuspendDebugLogger.append(
                context.appContext,
                "reconcile discard reason=request_mismatch savedRequestId=${saved.requestId} " +
                    "newRequestId=${requestSession.requestId} savedTrigger=${saved.trigger} " +
                    "newTrigger=${requestSession.trigger} savedSource=${saved.source} " +
                    "newSource=${requestSession.source}",
            )
            sessionStore.clear()
            sessionStore.save(requestSession)
            return requestSession
        }

        context.log("resume saved auto suspend session requestId=${saved.requestId}")
        AutoSuspendDebugLogger.append(
            context.appContext,
            "reconcile resume_saved_session requestId=${saved.requestId} awaitingResume=${saved.awaitingResume}",
        )
        return saved
    }

    companion object {
        private const val MIN_INTERVAL_SEC = 30L
        private const val SUSPEND_WAKE_DELAY_SEC = 20L
        private const val MIN_DEEP_SLEEP_MS = 10_000L
        private const val MAX_AWAITING_RESUME_AGE_MS = 300_000L
        private const val UI_READY_SETTLE_MS = 3_000L
    }

    private data class DeepSleepMeasurement(
        val requestElapsedMs: Long,
        val requestUptimeMs: Long,
        val nowElapsedMs: Long,
        val nowUptimeMs: Long,
        val elapsedDeltaMs: Long,
        val uptimeDeltaMs: Long,
        val deepSleepMs: Long,
        val elapsedReset: Boolean,
        val uptimeReset: Boolean,
    )

    private fun measureDeepSleep(session: AutoSuspendSession): DeepSleepMeasurement {
        val nowElapsed = SystemClock.elapsedRealtime()
        val nowUptime = SystemClock.uptimeMillis()
        val rawElapsedDelta = nowElapsed - session.sleepRequestElapsedRealtimeMs
        val rawUptimeDelta = nowUptime - session.sleepRequestUptimeMs
        val elapsedDelta = rawElapsedDelta.coerceAtLeast(0L)
        val uptimeDelta = rawUptimeDelta.coerceAtLeast(0L)
        val deepSleepMs = (elapsedDelta - uptimeDelta).coerceAtLeast(0L)
        return DeepSleepMeasurement(
            requestElapsedMs = session.sleepRequestElapsedRealtimeMs,
            requestUptimeMs = session.sleepRequestUptimeMs,
            nowElapsedMs = nowElapsed,
            nowUptimeMs = nowUptime,
            elapsedDeltaMs = elapsedDelta,
            uptimeDeltaMs = uptimeDelta,
            deepSleepMs = deepSleepMs,
            elapsedReset = rawElapsedDelta < 0L,
            uptimeReset = rawUptimeDelta < 0L,
        )
    }

    private suspend fun launchSmartTestUiAndWait(
        context: TestCaseExecutionContext,
        cycle: Int,
        totalCycles: Int,
        requestId: String,
    ) {
        context.log("launch SmartTest UI for cycle $cycle/$totalCycles before interval countdown")
        AutoSuspendDebugLogger.append(
            context.appContext,
            "launch SmartTest UI cycle=$cycle totalCycles=$totalCycles requestId=$requestId",
        )
        SmartTestUiLauncher.launchMainActivity(context.appContext)
        delay(UI_READY_SETTLE_MS)
        context.log("SmartTest UI ready for cycle $cycle/$totalCycles; settle=${UI_READY_SETTLE_MS}ms")
        AutoSuspendDebugLogger.append(
            context.appContext,
            "SmartTest UI ready cycle=$cycle totalCycles=$totalCycles requestId=$requestId settleMs=$UI_READY_SETTLE_MS",
        )
    }
}
