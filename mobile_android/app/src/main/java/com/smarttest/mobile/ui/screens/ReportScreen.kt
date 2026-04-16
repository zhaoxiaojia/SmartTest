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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.theme.token.controlTokens.CardType
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button
import com.smarttest.mobile.runner.RunnerSnapshot

@Composable
fun ReportScreen(
    snapshot: RunnerSnapshot,
) {
    val report = snapshot.report
    val metrics = if (report == null) {
        reportMetrics(MaterialTheme.colorScheme.error)
    } else {
        listOf(
            ReportMetric("总数", "${report.totalCount}", MaterialTheme.colorScheme.primary),
            ReportMetric("成功", "${report.successCount}", MaterialTheme.colorScheme.tertiary),
            ReportMetric("失败", "${report.failedCount}", MaterialTheme.colorScheme.error),
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
                        text = "执行报告",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    androidx.compose.material3.Text(
                        text = report?.statusText ?: "报告页已接入测试框架，当前还没有完成过的批次。",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {}, text = "导出 PDF", style = ButtonStyle.Button)
                        Button(onClick = {}, text = "分享链接", style = ButtonStyle.OutlinedButton)
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
                        text = "命令触发记录",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    androidx.compose.material3.Text(
                        text = snapshot.lastCommandSummary.ifBlank { "当前没有收到命令触发记录。" },
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (snapshot.runningCases.isNotEmpty()) {
                        TokenPill(
                            text = "最近批次 ${snapshot.runningCases.size} 项",
                            background = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                            foreground = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        }
    }
}
