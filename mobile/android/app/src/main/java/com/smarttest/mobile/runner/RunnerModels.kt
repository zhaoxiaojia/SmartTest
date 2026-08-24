package com.smarttest.mobile.runner

enum class RunPhase {
    Idle,
    Running,
    Stopping,
    Completed,
    Failed,
}

data class RunningCase(
    val id: String,
    val title: String,
    val category: String,
    val parameters: List<Pair<String, String>>,
    val parameterValues: Map<String, String> = emptyMap(),
)

data class RunnerStepPlan(
    val id: String,
    val title: String,
    val kind: String = "action",
    val definitionId: String = id,
    val parameters: List<Pair<String, String>> = emptyList(),
    val expected: String = "",
)

data class RunnerStepState(
    val id: String,
    val status: String,
    val actual: String = "",
    val error: String = "",
)

data class TestRunRequest(
    val caseIds: List<String>,
    val parameterOverrides: Map<String, String>,
    val source: String,
    val trigger: String,
    val requestId: String,
)

data class RunReport(
    val batchLabel: String,
    val requestId: String,
    val totalCount: Int,
    val successCount: Int,
    val failedCount: Int,
    val statusText: String,
)

data class RunnerSnapshot(
    val phase: RunPhase = RunPhase.Idle,
    val activeRequest: TestRunRequest? = null,
    val runningCases: List<RunningCase> = emptyList(),
    val plannedSteps: List<RunnerStepPlan> = emptyList(),
    val stepStates: Map<String, RunnerStepState> = emptyMap(),
    val logLines: List<String> = emptyList(),
    val logCount: Int = logLines.size,
    val logStartIndex: Int = 0,
    val report: RunReport? = null,
    val lastCommandSummary: String = "",
    val currentLoop: Int? = null,
    val totalLoops: Int? = null,
    val currentStage: String = "",
    val currentStepId: String = "",
) {
    val isRunning: Boolean
        get() = phase == RunPhase.Running || phase == RunPhase.Stopping
}
