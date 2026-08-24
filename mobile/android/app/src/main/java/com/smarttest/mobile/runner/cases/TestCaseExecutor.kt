package com.smarttest.mobile.runner.cases

import com.smarttest.mobile.runner.RunnerStepPlan
import com.smarttest.mobile.runner.RunningCase
import com.smarttest.mobile.runner.TestRunRequest

interface TestCaseExecutor {
    val caseId: String

    fun plan(request: TestRunRequest, runningCase: RunningCase): List<RunnerStepPlan> {
        return listOf(RunnerStepPlan(
            id = "${runningCase.id}.execute",
            title = "Execute ${runningCase.title}",
            kind = "action",
            definitionId = "${runningCase.id}.execute",
            parameters = runningCase.parameters,
            expected = "Case executor finishes without failed result.",
        ))
    }

    suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult
}

data class TestCaseExecutionResult(
    val passed: Boolean,
    val summary: String,
    val pendingResume: Boolean = false,
)
