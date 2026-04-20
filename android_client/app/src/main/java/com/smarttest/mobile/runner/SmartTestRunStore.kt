package com.smarttest.mobile.runner

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

object SmartTestRunStore {
    private val mutableState = MutableStateFlow(RunnerSnapshot())
    val state: StateFlow<RunnerSnapshot> = mutableState.asStateFlow()

    fun startRun(request: TestRunRequest, cases: List<RunningCase>) {
        mutableState.value = RunnerSnapshot(
            phase = RunPhase.Running,
            activeRequest = request,
            runningCases = cases,
            logLines = listOf(
                timestamped("Received command from ${request.source}, trigger=${request.trigger}"),
                timestamped("Prepared batch with ${cases.size} case(s)"),
            ),
            report = null,
            lastCommandSummary = "${request.trigger} -> ${request.caseIds.joinToString()}",
        )
    }

    fun appendLog(message: String) {
        mutableState.update { snapshot ->
            snapshot.copy(logLines = snapshot.logLines + timestamped(message))
        }
    }

    fun markStopping(reason: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                phase = RunPhase.Stopping,
                logLines = snapshot.logLines + timestamped("Received stop request: $reason"),
                lastCommandSummary = reason,
            )
        }
    }

    fun markStatus(reason: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                lastCommandSummary = reason,
                logLines = snapshot.logLines + timestamped(
                    "Status query: ${snapshot.phase} / ${snapshot.runningCases.size} case(s) / ${snapshot.logLines.size} log line(s)",
                ),
            )
        }
    }

    fun finishRun(statusText: String, failedCount: Int) {
        mutableState.update { snapshot ->
            val total = snapshot.runningCases.size
            val success = (total - failedCount).coerceAtLeast(0)
            snapshot.copy(
                phase = if (failedCount > 0) RunPhase.Failed else RunPhase.Completed,
                report = RunReport(
                    batchLabel = snapshot.activeRequest?.trigger ?: "manual",
                    totalCount = total,
                    successCount = success,
                    failedCount = failedCount,
                    statusText = statusText,
                ),
                logLines = snapshot.logLines + timestamped(statusText),
            )
        }
    }

    fun resetToIdle(statusText: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                phase = RunPhase.Idle,
                activeRequest = null,
                runningCases = emptyList(),
                logLines = snapshot.logLines + timestamped(statusText),
            )
        }
    }

    private fun timestamped(message: String): String {
        val now = java.time.LocalTime.now()
        return "%02d:%02d:%02d  %s".format(now.hour, now.minute, now.second, message)
    }
}
