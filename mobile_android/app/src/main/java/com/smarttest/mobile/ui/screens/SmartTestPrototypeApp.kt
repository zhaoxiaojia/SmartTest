package com.smarttest.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.microsoft.fluentui.theme.FluentTheme
import com.microsoft.fluentui.theme.ThemeMode
import com.microsoft.fluentui.theme.token.FluentStyle
import com.microsoft.fluentui.theme.token.controlTokens.AppBarSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.tokenized.AppBar
import com.microsoft.fluentui.tokenized.controls.Button
import com.smarttest.mobile.ui.navigation.AppPage
import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.runner.SmartTestRunnerService
import com.smarttest.mobile.runner.TestRunRequest
import com.smarttest.mobile.ui.theme.SmartTestMobileTheme

@Composable
fun SmartTestPrototypeApp() {
    val context = LocalContext.current
    val runnerSnapshot by SmartTestRunStore.state.collectAsState()
    var darkMode by remember { mutableStateOf(false) }
    var currentPage by remember { mutableStateOf(AppPage.Cases) }
    val selectedCaseIds = remember { mutableStateListOf<String>() }
    val expandedCaseIds = remember { mutableStateListOf<String>() }
    val parameterValues = remember { mutableStateMapOf<String, String>() }

    val categories = buildCaseCategories()
    val allCases = categories.flatMap { category -> category.cases.map { category.title to it } }
    val caseById = allCases.associate { (category, case) -> case.id to (category to case) }
    val selectedCases = selectedCaseIds.mapNotNull { caseById[it] }

    LaunchedEffect(runnerSnapshot.phase) {
        if (runnerSnapshot.isRunning || runnerSnapshot.logLines.isNotEmpty()) {
            currentPage = AppPage.Log
        }
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

    fun startRun() {
        if (selectedCaseIds.isEmpty()) return
        val request = TestRunRequest(
            caseIds = selectedCaseIds.toList(),
            parameterOverrides = parameterValues.toMap(),
            source = "ui",
            trigger = "start_button",
        )
        SmartTestRunnerService.enqueueRun(context, request)
        currentPage = AppPage.Log
    }

    fun stopRun() {
        SmartTestRunnerService.enqueueStop(context, "UI 停止按钮")
    }

    SmartTestMobileTheme(darkTheme = darkMode) {
        FluentTheme(themeMode = if (darkMode) ThemeMode.Dark else ThemeMode.Light) {
            Scaffold(
                topBar = {
                    AppBar(
                        title = "SmartTest",
                        subTitle = currentPage.subtitle,
                        appBarSize = AppBarSize.Large,
                        style = FluentStyle.Brand,
                        rightAccessoryView = {
                            ThemeModeButton(
                                darkMode = darkMode,
                                onToggle = { darkMode = !darkMode },
                            )
                        },
                    )
                },
                bottomBar = {
                    when (currentPage) {
                        AppPage.Cases -> CasesBottomBar(selectedCaseIds.size, ::startRun)
                        AppPage.Log -> LogBottomBar(runnerSnapshot.isRunning, ::stopRun)
                        AppPage.Report -> {}
                    }
                },
            ) { innerPadding ->
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(MaterialTheme.colorScheme.background)
                        .padding(innerPadding),
                ) {
                    PageTabs(currentPage = currentPage, onPageChange = { currentPage = it })
                    when (currentPage) {
                        AppPage.Cases -> CasesScreen(
                            categories = categories,
                            selectedCases = selectedCases,
                            selectedCaseIds = selectedCaseIds,
                            expandedCaseIds = expandedCaseIds,
                            parameterValues = parameterValues,
                            onToggleCase = ::toggleCase,
                            onToggleExpandedCase = ::toggleExpandedCase,
                            onParameterChange = { caseId, parameterId, value ->
                                parameterValues["$caseId:$parameterId"] = value
                            },
                        )

                        AppPage.Log -> LogScreen(
                            runningCases = runnerSnapshot.runningCases,
                            logLines = runnerSnapshot.logLines,
                            isRunning = runnerSnapshot.isRunning,
                            statusText = runnerSnapshot.phase.name,
                            commandSummary = runnerSnapshot.lastCommandSummary,
                        )

                        AppPage.Report -> ReportScreen(snapshot = runnerSnapshot)
                    }
                }
            }
        }
    }
}

@Composable
private fun ThemeModeButton(
    darkMode: Boolean,
    onToggle: () -> Unit,
) {
    FilledTonalIconButton(onClick = onToggle) {
        Icon(
            imageVector = if (darkMode) Icons.Outlined.LightMode else Icons.Outlined.DarkMode,
            contentDescription = if (darkMode) "切换到浅色模式" else "切换到深色模式",
        )
    }
}

@Composable
private fun PageTabs(
    currentPage: AppPage,
    onPageChange: (AppPage) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        AppPage.entries.forEach { page ->
            Button(
                onClick = { onPageChange(page) },
                text = page.title,
                modifier = Modifier.weight(1f),
                style = if (page == currentPage) ButtonStyle.Button else ButtonStyle.OutlinedButton,
                size = ButtonSize.Large,
            )
        }
    }
}
