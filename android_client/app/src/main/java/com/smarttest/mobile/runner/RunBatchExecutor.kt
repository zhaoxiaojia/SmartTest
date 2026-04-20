package com.smarttest.mobile.runner

import android.content.Context
import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import com.smarttest.mobile.runner.cases.TestCaseRegistry
import com.smarttest.mobile.runner.device.SmartDeviceEnvironment

data class RunBatchExecutionResult(
    val failedCount: Int,
    val pendingResume: Boolean = false,
)

object RunBatchExecutor {
    suspend fun execute(
        appContext: Context,
        request: TestRunRequest,
        cases: List<RunningCase>,
        environment: SmartDeviceEnvironment,
        findExecutor: (String) -> TestCaseExecutor? = TestCaseRegistry::find,
        logger: (String) -> Unit = SmartTestRunStore::appendLog,
    ): RunBatchExecutionResult {
        var failedCount = 0
        cases.forEach { runningCase ->
            val executor = findExecutor(runningCase.id)
            if (executor == null) {
                failedCount += 1
                logger("[${runningCase.title}] executor not implemented")
                return@forEach
            }

            logger("[${runningCase.category}] ${runningCase.title} start")
            if (runningCase.parameters.isNotEmpty()) {
                logger(
                    "params: ${runningCase.parameters.joinToString(" / ") { "${it.first}=${it.second}" }}",
                )
            }

            val result = executor.execute(
                TestCaseExecutionContext(
                    appContext = appContext,
                    environment = environment,
                    request = request,
                    runningCase = runningCase,
                    logger = logger,
                ),
            )

            logger(result.summary)
            if (result.pendingResume) {
                return RunBatchExecutionResult(failedCount = failedCount, pendingResume = true)
            }
            if (!result.passed) {
                failedCount += 1
            }
        }
        return RunBatchExecutionResult(failedCount = failedCount)
    }
}
