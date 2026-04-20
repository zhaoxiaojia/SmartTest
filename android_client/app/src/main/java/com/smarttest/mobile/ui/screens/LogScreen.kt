package com.smarttest.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microsoft.fluentui.theme.token.controlTokens.ButtonSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button
import com.smarttest.mobile.R
import com.smarttest.mobile.runner.RunningCase

@Composable
fun LogScreen(
    runningCases: List<RunningCase>,
    logLines: List<String>,
    isRunning: Boolean,
    statusText: String,
    commandSummary: String,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 120.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            BasicCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        text = stringResource(R.string.log_heading),
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = if (isRunning) {
                            stringResource(R.string.log_running_hint)
                        } else {
                            stringResource(R.string.log_idle_hint)
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = stringResource(R.string.log_status, statusText),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (commandSummary.isNotBlank()) {
                        Text(
                            text = stringResource(R.string.log_last_command, commandSummary),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (runningCases.isNotEmpty()) {
                        Text(
                            text = stringResource(
                                R.string.log_current_batch,
                                runningCases.joinToString(" / ") { it.title },
                            ),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
        item {
            Surface(
                color = Color(0xFF111827),
                shape = MaterialTheme.shapes.large,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (logLines.isEmpty()) {
                        Text(
                            text = stringResource(R.string.log_waiting),
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFE5E7EB),
                            fontFamily = FontFamily.Monospace,
                        )
                    } else {
                        logLines.forEach { line ->
                            Text(
                                text = line,
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFE5E7EB),
                                fontFamily = FontFamily.Monospace,
                                lineHeight = 20.sp,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun LogBottomBar(
    isRunning: Boolean,
    onStopRun: () -> Unit,
) {
    Surface(shadowElevation = 10.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 14.dp),
        ) {
            Button(
                onClick = onStopRun,
                text = if (isRunning) {
                    stringResource(R.string.log_stop_run)
                } else {
                    stringResource(R.string.log_run_stopped)
                },
                modifier = Modifier.fillMaxWidth(),
                style = ButtonStyle.Button,
                size = ButtonSize.Large,
                enabled = isRunning,
            )
        }
    }
}
