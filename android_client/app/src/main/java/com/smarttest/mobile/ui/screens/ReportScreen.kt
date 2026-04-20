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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.theme.token.controlTokens.CardType
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button
import com.smarttest.mobile.R
import com.smarttest.mobile.runner.RunnerSnapshot

@Composable
fun ReportScreen(
    snapshot: RunnerSnapshot,
) {
    val report = snapshot.report
    val metrics = if (report == null) {
        listOf(
            ReportMetric(stringResource(R.string.report_metric_platform), "8 / 8", com.smarttest.mobile.ui.theme.SmartBlue),
            ReportMetric(stringResource(R.string.report_metric_system), "4 / 5", MaterialTheme.colorScheme.error),
            ReportMetric(stringResource(R.string.report_metric_network), "6 / 8", com.smarttest.mobile.ui.theme.Grey120),
        )
    } else {
        listOf(
            ReportMetric(stringResource(R.string.report_metric_total), "${report.totalCount}", MaterialTheme.colorScheme.primary),
            ReportMetric(stringResource(R.string.report_metric_passed), "${report.successCount}", MaterialTheme.colorScheme.tertiary),
            ReportMetric(stringResource(R.string.report_metric_failed), "${report.failedCount}", MaterialTheme.colorScheme.error),
        )
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            BasicCard(
                modifier = Modifier.fillMaxWidth(),
                cardType = CardType.Elevated,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    androidx.compose.material3.Text(
                        text = stringResource(R.string.report_heading),
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    androidx.compose.material3.Text(
                        text = report?.statusText ?: stringResource(R.string.report_empty),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {}, text = stringResource(R.string.report_export_pdf), style = ButtonStyle.Button)
                        Button(onClick = {}, text = stringResource(R.string.report_share_link), style = ButtonStyle.OutlinedButton)
                    }
                }
            }
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                metrics.forEach { metric ->
                    BasicCard(modifier = Modifier.weight(1f)) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            androidx.compose.material3.Text(
                                text = metric.label,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            androidx.compose.material3.Text(
                                text = metric.value,
                                style = MaterialTheme.typography.headlineMedium,
                                color = metric.accent,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                }
            }
        }
        item {
            BasicCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    androidx.compose.material3.Text(
                        text = stringResource(R.string.report_command_history),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    androidx.compose.material3.Text(
                        text = snapshot.lastCommandSummary.ifBlank { stringResource(R.string.report_no_command) },
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (snapshot.runningCases.isNotEmpty()) {
                        TokenPill(
                            text = stringResource(R.string.report_last_batch, snapshot.runningCases.size),
                            background = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                            foreground = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        }
    }
}
