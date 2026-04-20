package com.smarttest.mobile.runner.cases

import com.smarttest.mobile.runner.cases.power.AutoRebootCaseExecutor
import com.smarttest.mobile.runner.cases.power.AutoSuspendCaseExecutor
import com.smarttest.mobile.runner.cases.radio.BluetoothOnOffCaseExecutor
import com.smarttest.mobile.runner.cases.radio.WifiOnOffCaseExecutor
import com.smarttest.mobile.runner.cases.storage.EmmcReadWriteCaseExecutor

object TestCaseRegistry {
    private val executors: Map<String, TestCaseExecutor> = listOf(
        EmmcReadWriteCaseExecutor(),
        AutoRebootCaseExecutor(),
        AutoSuspendCaseExecutor(),
        WifiOnOffCaseExecutor(),
        BluetoothOnOffCaseExecutor(),
    ).associateBy(TestCaseExecutor::caseId)

    fun find(caseId: String): TestCaseExecutor? = executors[caseId]
}
