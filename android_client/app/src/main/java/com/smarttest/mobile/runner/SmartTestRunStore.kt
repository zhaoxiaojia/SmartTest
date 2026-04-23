package com.smarttest.mobile.runner

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.File

object SmartTestRunStore {
    private val mutableState = MutableStateFlow(RunnerSnapshot())
    val state: StateFlow<RunnerSnapshot> = mutableState.asStateFlow()
    @Volatile
    private var snapshotFile: File? = null
    @Volatile
    private var publicSnapshotFile: File? = null

    fun initialize(context: Context) {
        snapshotFile = SmartTestRunSnapshotFile.resolve(context.applicationContext)
        publicSnapshotFile = SmartTestPublicSnapshotFile.resolve(context.applicationContext)
        persistSnapshot(mutableState.value)
    }

    fun startRun(request: TestRunRequest, cases: List<RunningCase>) {
        mutableState.value = RunnerSnapshot(
            phase = RunPhase.Running,
            activeRequest = request,
            runningCases = cases,
            logLines = listOf(
                timestamped(
                    "Received command from ${request.source}, trigger=${request.trigger}, requestId=${request.requestId}",
                ),
                timestamped("Prepared batch with ${cases.size} case(s)"),
            ),
            report = null,
            lastCommandSummary = "${request.trigger} [${request.requestId}] -> ${request.caseIds.joinToString()}",
            currentLoop = null,
            totalLoops = null,
            currentStage = "",
        )
        persistSnapshot(mutableState.value)
    }

    fun appendLog(message: String) {
        mutableState.update { snapshot ->
            snapshot.copy(logLines = snapshot.logLines + timestamped(message))
        }
        persistSnapshot(mutableState.value)
    }

    fun updateProgress(
        currentLoop: Int?,
        totalLoops: Int?,
        stage: String,
    ) {
        mutableState.update { snapshot ->
            snapshot.copy(
                currentLoop = currentLoop,
                totalLoops = totalLoops,
                currentStage = stage,
            )
        }
        persistSnapshot(mutableState.value)
    }

    fun markStopping(reason: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                phase = RunPhase.Stopping,
                logLines = snapshot.logLines + timestamped("Received stop request: $reason"),
                lastCommandSummary = reason,
                currentStage = "stopping",
            )
        }
        persistSnapshot(mutableState.value)
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
        persistSnapshot(mutableState.value)
    }

    fun finishRun(statusText: String, failedCount: Int) {
        mutableState.update { snapshot ->
            val total = snapshot.runningCases.size
            val success = (total - failedCount).coerceAtLeast(0)
            snapshot.copy(
                phase = if (failedCount > 0) RunPhase.Failed else RunPhase.Completed,
                report = RunReport(
                    batchLabel = snapshot.activeRequest?.trigger ?: "manual",
                    requestId = snapshot.activeRequest?.requestId ?: "manual",
                    totalCount = total,
                    successCount = success,
                    failedCount = failedCount,
                    statusText = statusText,
                ),
                logLines = snapshot.logLines + timestamped(statusText),
                currentStage = if (failedCount > 0) "failed" else "completed",
            )
        }
        persistSnapshot(mutableState.value)
    }

    fun resetToIdle(statusText: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                phase = RunPhase.Idle,
                activeRequest = null,
                runningCases = emptyList(),
                report = null,
                logLines = snapshot.logLines + timestamped(statusText),
                lastCommandSummary = statusText,
                currentLoop = null,
                totalLoops = null,
                currentStage = "idle",
            )
        }
        persistSnapshot(mutableState.value)
    }

    private fun timestamped(message: String): String {
        val now = java.time.LocalTime.now()
        return "%02d:%02d:%02d  %s".format(now.hour, now.minute, now.second, message)
    }

    private fun persistSnapshot(snapshot: RunnerSnapshot) {
        val payload = RunnerSnapshotJson.serialize(snapshot)
        writeSnapshot(snapshotFile, payload)
        writeSnapshot(publicSnapshotFile, payload)
    }

    private fun writeSnapshot(target: File?, payload: String) {
        if (target == null) return
        runCatching {
            target.parentFile?.mkdirs()
            target.writeText(payload)
        }
    }
}
