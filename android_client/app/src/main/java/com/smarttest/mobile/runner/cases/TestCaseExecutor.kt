package com.smarttest.mobile.runner.cases

interface TestCaseExecutor {
    val caseId: String

    suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult
}

data class TestCaseExecutionResult(
    val passed: Boolean,
    val summary: String,
    val pendingResume: Boolean = false,
)
