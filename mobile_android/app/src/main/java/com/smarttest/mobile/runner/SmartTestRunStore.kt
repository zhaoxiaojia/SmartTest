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
                timestamped("收到 ${request.source} 指令，触发来源 ${request.trigger}"),
                timestamped("批次创建完成，共 ${cases.size} 项用例"),
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
                logLines = snapshot.logLines + timestamped("收到停止请求: $reason"),
                lastCommandSummary = reason,
            )
        }
    }

    fun markStatus(reason: String) {
        mutableState.update { snapshot ->
            snapshot.copy(
                lastCommandSummary = reason,
                logLines = snapshot.logLines + timestamped(
                    "状态查询: ${snapshot.phase} / ${snapshot.runningCases.size} 项 / ${snapshot.logLines.size} 行日志",
                ),
            )
        }
    }

    fun finishRun(statusText: String, failedCount: Int = 0) {
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
