package com.smarttest.mobile.ui.screens

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.smarttest.mobile.runner.RunnerSnapshot
import com.smarttest.mobile.runner.TestRunRequest
import com.smarttest.mobile.ui.navigation.AppPage

@Stable
class SmartTestPrototypeState(
    val categories: List<CaseCategory>,
    initialPage: AppPage,
    private val onPageChanged: (AppPage) -> Unit,
    private val onStartRunRequest: (TestRunRequest) -> Unit,
    private val onStopRunRequest: () -> Unit,
) {
    var currentPage by mutableStateOf(initialPage)
        private set

    val selectedCaseIds = mutableStateListOf<String>()
    val expandedCaseIds = mutableStateListOf<String>()
    val parameterValues = mutableStateMapOf<String, String>()

    private val caseById = categories
        .flatMap { category -> category.cases.map { case -> case.id to case } }
        .toMap()

    val selectedCases: List<CaseTemplate>
        get() = selectedCaseIds.mapNotNull { caseById[it] }

    fun onRunnerSnapshotChanged(snapshot: RunnerSnapshot) {
        if (snapshot.isRunning || snapshot.logLines.isNotEmpty()) {
            applyCurrentPage(AppPage.Log)
        }
    }

    fun navigateTo(page: AppPage) {
        applyCurrentPage(page)
    }

    fun toggleCase(case: CaseTemplate) {
        if (selectedCaseIds.contains(case.id)) {
            selectedCaseIds.remove(case.id)
            expandedCaseIds.remove(case.id)
            return
        }
        selectedCaseIds += case.id
        case.parameters.forEach { parameter ->
            val key = "${case.id}:${parameter.id}"
            if (!parameterValues.containsKey(key)) {
                parameterValues[key] = parameter.defaultValue
            }
        }
        if (case.parameters.isNotEmpty() && !expandedCaseIds.contains(case.id)) {
            expandedCaseIds += case.id
        }
    }

    fun toggleExpandedCase(caseId: String) {
        if (expandedCaseIds.contains(caseId)) {
            expandedCaseIds.remove(caseId)
        } else {
            expandedCaseIds += caseId
        }
    }

    fun updateParameter(caseId: String, parameterId: String, value: String) {
        parameterValues["$caseId:$parameterId"] = value
    }

    fun startRun() {
        if (selectedCaseIds.isEmpty()) return
        onStartRunRequest(
            TestRunRequest(
                caseIds = selectedCaseIds.toList(),
                parameterOverrides = parameterValues.toMap(),
                source = "ui",
                trigger = "start_button",
            ),
        )
        applyCurrentPage(AppPage.Log)
    }

    fun stopRun() {
        onStopRunRequest()
    }

    private fun applyCurrentPage(page: AppPage) {
        if (currentPage == page) {
            return
        }
        currentPage = page
        onPageChanged(page)
    }
}
