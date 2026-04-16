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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
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
import com.smarttest.mobile.ui.theme.SmartTestMobileTheme
import kotlinx.coroutines.delay

@Composable
fun SmartTestPrototypeApp() {
    var darkMode by remember { mutableStateOf(false) }
    var currentPage by remember { mutableStateOf(AppPage.Cases) }
    val selectedCaseIds = remember { mutableStateListOf<String>() }
    val parameterValues = remember { mutableStateMapOf<String, String>() }
    val logLines = remember { mutableStateListOf<String>() }
    var expandedCaseId by remember { mutableStateOf<String?>(null) }
    var isRunning by remember { mutableStateOf(false) }
    var sessionKey by remember { mutableIntStateOf(0) }
    var runningCases by remember { mutableStateOf<List<RunningCase>>(emptyList()) }

    val categories = buildCaseCategories()
    val allCases = categories.flatMap { category -> category.cases.map { category.title to it } }
    val caseById = allCases.associate { (category, case) -> case.id to (category to case) }
    val selectedCases = selectedCaseIds.mapNotNull { caseById[it] }

    LaunchedEffect(sessionKey, isRunning) {
        if (!isRunning || runningCases.isEmpty()) return@LaunchedEffect
        runningCases.forEachIndexed { index, runningCase ->
            delay(280)
            logLines += "08:${40 + index}:00  [${runningCase.category}] ${runningCase.title} 开始执行"
            if (runningCase.parameters.isNotEmpty()) {
                delay(180)
                logLines += "08:${40 + index}:01  参数: ${
                    runningCase.parameters.joinToString(" / ") { "${it.first}=${it.second}" }
                }"
            }
            delay(220)
            logLines += "08:${40 + index}:02  设备状态正常，持续采集中"
        }
        delay(260)
        logLines += "08:59:59  批次已启动，等待后续设备日志..."
    }

    fun toggleCase(case: CaseTemplate) {
        if (selectedCaseIds.contains(case.id)) {
            selectedCaseIds.remove(case.id)
            if (expandedCaseId == case.id) expandedCaseId = null
            return
        }
        selectedCaseIds += case.id
        case.parameters.forEach { parameter ->
            val key = "${case.id}:${parameter.id}"
            if (!parameterValues.containsKey(key)) {
                parameterValues[key] = parameter.defaultValue
            }
        }
        expandedCaseId = if (case.parameters.isNotEmpty()) case.id else null
    }

    fun startRun() {
        if (selectedCaseIds.isEmpty()) return
        runningCases = selectedCaseIds.mapNotNull { id ->
            val (category, case) = caseById[id] ?: return@mapNotNull null
            RunningCase(
                title = case.title,
                category = category,
                parameters = case.parameters.map { parameter ->
                    parameter.label to (parameterValues["${case.id}:${parameter.id}"] ?: parameter.defaultValue)
                },
            )
        }
        logLines.clear()
        logLines += "08:39:58  创建测试批次，共 ${runningCases.size} 项"
        logLines += "08:39:59  跳转日志页，等待执行器接管"
        isRunning = true
        sessionKey += 1
        currentPage = AppPage.Log
    }

    fun stopRun() {
        if (!isRunning) return
        isRunning = false
        logLines += "09:00:10  用户触发停止，等待测试任务安全退出"
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
                        AppPage.Log -> LogBottomBar(isRunning, ::stopRun)
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
                            expandedCaseId = expandedCaseId,
                            parameterValues = parameterValues,
                            onToggleCase = ::toggleCase,
                            onExpandCase = { expandedCaseId = if (expandedCaseId == it) null else it },
                            onParameterChange = { caseId, parameterId, value ->
                                parameterValues["$caseId:$parameterId"] = value
                            },
                        )
                        AppPage.Log -> LogScreen(
                            runningCases = runningCases,
                            logLines = logLines,
                            isRunning = isRunning,
                        )
                        AppPage.Report -> ReportScreen()
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
