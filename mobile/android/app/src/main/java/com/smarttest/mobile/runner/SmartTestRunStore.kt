package com.smarttest.mobile.runner

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.File

object SmartTestRunStore {
    private const val MAX_LOG_LINES = 500
    private const val MAX_STEP_STATES = 120
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

    fun startRun(request: TestRunRequest, cases: List<RunningCase>, plannedSteps: List<RunnerStepPlan>) {
        val initialLogs = listOf(
            timestamped(
                "Received command from ${request.source}, trigger=${request.trigger}, requestId=${request.requestId}",
            ),
            timestamped("Prepared batch with ${cases.size} case(s)"),
        )
        mutableState.value = RunnerSnapshot(
            phase = RunPhase.Running,
            activeRequest = request,
            runningCases = cases,
            plannedSteps = plannedSteps,
            stepStates = plannedSteps.associate { step ->
                step.id to RunnerStepState(id = step.id, status = "planned")
            },
            logLines = initialLogs,
            logCount = initialLogs.size,
            logStartIndex = 0,
            report = null,
            lastCommandSummary = "${request.trigger} [${request.requestId}] -> ${request.caseIds.joinToString()}",
            currentLoop = null,
            totalLoops = null,
            currentStage = "",
            currentStepId = "",
        )
        persistSnapshot(mutableState.value)
    }

    fun appendLog(message: String) {
        mutableState.update { snapshot ->
            snapshot.withAppendedLog(timestamped(message))
        }
        persistSnapshot(mutableState.value)
    }

    fun updateProgress(
        currentLoop: Int?,
        totalLoops: Int?,
        stage: String,
        stepId: String? = null,
        actual: String = "",
    ) {
        mutableState.update { snapshot ->
            val updatedStates = if (stepId.isNullOrBlank()) {
                snapshot.stepStates
            } else {
                snapshot.stepStates.mapValues { (_, state) ->
                    if (state.status == "running" && state.id != stepId) {
                        state.copy(status = "passed")
                    } else {
                        state
                    }
                } + (stepId to RunnerStepState(id = stepId, status = "running", actual = actual))
            }
            snapshot.copy(
                currentLoop = currentLoop,
                totalLoops = totalLoops,
                currentStage = stage,
                currentStepId = stepId ?: snapshot.currentStepId,
                stepStates = trimStepStates(updatedStates, stepId ?: snapshot.currentStepId),
            )
        }
        persistSnapshot(mutableState.value)
    }

    fun finishStep(stepId: String, passed: Boolean, actual: String = "", error: String = "") {
        mutableState.update { snapshot ->
            val updatedStates = snapshot.stepStates + (
                    stepId to RunnerStepState(
                        id = stepId,
                        status = if (passed) "passed" else "failed",
                        actual = actual,
                        error = error,
                    )
                    )
            snapshot.copy(
                stepStates = trimStepStates(updatedStates, stepId),
            )
        }
        persistSnapshot(mutableState.value)
    }

    fun markStopping(reason: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                phase = RunPhase.Stopping,
                lastCommandSummary = reason,
                currentStage = "stopping",
            ).withAppendedLog(timestamped("Received stop request: $reason"))
        }
        persistSnapshot(mutableState.value)
    }

    fun finishRun(statusText: String, failedCount: Int) {
        mutableState.update { snapshot ->
            val total = snapshot.runningCases.size
            val success = (total - failedCount).coerceAtLeast(0)
            val finalStepStates = snapshot.stepStates.mapValues { (_, state) ->
                if (state.status == "running") {
                    state.copy(status = if (failedCount > 0) "failed" else "passed", error = if (failedCount > 0) statusText else state.error)
                } else {
                    state
                }
            }
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
                currentStage = if (failedCount > 0) "failed" else "completed",
                currentStepId = "",
                stepStates = trimStepStates(finalStepStates, snapshot.currentStepId),
            ).withAppendedLog(timestamped(statusText))
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
                plannedSteps = emptyList(),
                stepStates = emptyMap(),
                lastCommandSummary = statusText,
                currentLoop = null,
                totalLoops = null,
                currentStage = "idle",
                currentStepId = "",
            ).withAppendedLog(timestamped(statusText))
        }
        persistSnapshot(mutableState.value)
    }

    private fun timestamped(message: String): String {
        val now = java.time.LocalTime.now()
        return "%02d:%02d:%02d  %s".format(now.hour, now.minute, now.second, message)
    }

    private fun RunnerSnapshot.withAppendedLog(line: String): RunnerSnapshot {
        val updatedCount = logCount + 1
        val updatedLines = (logLines + line).takeLast(MAX_LOG_LINES)
        val dropped = logLines.size + 1 - updatedLines.size
        return copy(
            logLines = updatedLines,
            logCount = updatedCount,
            logStartIndex = logStartIndex + dropped.coerceAtLeast(0),
        )
    }

    private fun trimStepStates(
        states: Map<String, RunnerStepState>,
        currentStepId: String,
    ): Map<String, RunnerStepState> {
        if (states.size <= MAX_STEP_STATES) return states

        val current = states[currentStepId]
        val activeStates = states.filterValues { it.status == "running" || it.status == "failed" }
        val recentStates = states.entries.toList().takeLast(MAX_STEP_STATES).associate { it.key to it.value }
        val merged = LinkedHashMap<String, RunnerStepState>()
        merged.putAll(recentStates)
        merged.putAll(activeStates)
        if (current != null) {
            merged[currentStepId] = current
        }
        return merged.entries.toList().takeLast(MAX_STEP_STATES).associate { it.key to it.value }
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
