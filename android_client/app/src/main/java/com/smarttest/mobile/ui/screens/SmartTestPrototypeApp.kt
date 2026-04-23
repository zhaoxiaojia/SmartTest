package com.smarttest.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.microsoft.fluentui.theme.FluentTheme
import com.microsoft.fluentui.theme.ThemeMode
import com.microsoft.fluentui.theme.token.FluentStyle
import com.microsoft.fluentui.theme.token.controlTokens.AppBarSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.tokenized.AppBar
import com.microsoft.fluentui.tokenized.controls.Button
import com.smarttest.mobile.R
import com.smarttest.mobile.runner.SmartTestRunnerService
import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.settings.AppSettingsStore
import com.smarttest.mobile.settings.ThemePreference
import com.smarttest.mobile.ui.navigation.AppPage
import com.smarttest.mobile.ui.theme.SmartTestMobileTheme

@Composable
fun SmartTestPrototypeApp() {
    val context = LocalContext.current
    val runnerSnapshot by SmartTestRunStore.state.collectAsState()
    val settingsState by AppSettingsStore.state.collectAsState()
    var savedPageName by rememberSaveable { androidx.compose.runtime.mutableStateOf(AppPage.Cases.name) }
    var settingsExpanded by rememberSaveable { androidx.compose.runtime.mutableStateOf(false) }
    val initialPage = AppPage.entries.firstOrNull { it.name == savedPageName } ?: AppPage.Cases
    val darkMode = when (settingsState.themePreference) {
        ThemePreference.System -> isSystemInDarkTheme()
        ThemePreference.Light -> false
        ThemePreference.Dark -> true
    }

    SmartTestMobileTheme(darkTheme = darkMode) {
        val categories = buildCaseCategories(
            tertiaryAccent = MaterialTheme.colorScheme.tertiary,
            errorAccent = MaterialTheme.colorScheme.error,
        )
        val state = remember(context, categories) {
            SmartTestPrototypeState(
                categories = categories,
                initialPage = initialPage,
                onPageChanged = { savedPageName = it.name },
                onStartRunRequest = { request ->
                    SmartTestRunnerService.enqueueRun(context, request)
                },
                onStopRunRequest = {
                    SmartTestRunnerService.enqueueStop(context, "UI stop button")
                },
            )
        }

        LaunchedEffect(runnerSnapshot.phase, runnerSnapshot.logLines.size) {
            state.onRunnerSnapshotChanged(runnerSnapshot)
        }

        FluentTheme(themeMode = if (darkMode) ThemeMode.Dark else ThemeMode.Light) {
            Scaffold(
                topBar = {
                    AppBar(
                        title = stringResource(R.string.app_name),
                        subTitle = stringResource(state.currentPage.subtitleRes),
                        appBarSize = AppBarSize.Large,
                        style = FluentStyle.Brand,
                        rightAccessoryView = {
                            SettingsButton(
                                onOpenSettings = { settingsExpanded = !settingsExpanded },
                            )
                        },
                    )
                },
                bottomBar = {
                    when (state.currentPage) {
                        AppPage.Cases -> CasesBottomBar(state.selectedCaseIds.size, state::startRun)
                        AppPage.Log -> LogBottomBar(runnerSnapshot.isRunning, state::stopRun)
                        AppPage.Report -> {}
                    }
                },
            ) { innerPadding ->
                Row(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(MaterialTheme.colorScheme.background)
                        .padding(innerPadding)
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Column(
                        modifier = Modifier.weight(1f),
                    ) {
                        PageTabs(currentPage = state.currentPage, onPageChange = state::navigateTo)
                        Box(
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            when (state.currentPage) {
                                AppPage.Cases -> CasesScreen(
                                    categories = state.categories,
                                    selectedCases = state.selectedCases,
                                    selectedCaseIds = state.selectedCaseIds,
                                    expandedCaseIds = state.expandedCaseIds,
                                    parameterValues = state.parameterValues,
                                    onToggleCase = state::toggleCase,
                                    onToggleExpandedCase = state::toggleExpandedCase,
                                    onParameterChange = state::updateParameter,
                                )

                                AppPage.Log -> LogScreen(
                                    runningCases = runnerSnapshot.runningCases,
                                    logLines = runnerSnapshot.logLines,
                                    isRunning = runnerSnapshot.isRunning,
                                    statusText = runnerSnapshot.phase.name,
                                    commandSummary = runnerSnapshot.lastCommandSummary,
                                    currentLoop = runnerSnapshot.currentLoop,
                                    totalLoops = runnerSnapshot.totalLoops,
                                    currentStage = runnerSnapshot.currentStage,
                                )

                                AppPage.Report -> ReportScreen(snapshot = runnerSnapshot)
                            }
                        }
                    }
                    if (settingsExpanded) {
                        SettingsPanel(
                            modifier = Modifier.width(360.dp),
                            themePreference = settingsState.themePreference,
                            languagePreference = settingsState.languagePreference,
                            onThemeChange = { AppSettingsStore.updateTheme(context, it) },
                            onLanguageChange = { AppSettingsStore.updateLanguage(context, it) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingsButton(
    onOpenSettings: () -> Unit,
) {
    FilledTonalIconButton(onClick = onOpenSettings) {
        Icon(
            imageVector = Icons.Outlined.Settings,
            contentDescription = stringResource(R.string.settings_button),
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
                text = stringResource(page.titleRes),
                modifier = Modifier.weight(1f),
                style = if (page == currentPage) ButtonStyle.Button else ButtonStyle.OutlinedButton,
                size = ButtonSize.Large,
            )
        }
    }
}
