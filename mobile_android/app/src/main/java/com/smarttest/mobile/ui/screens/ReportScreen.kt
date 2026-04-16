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
import com.microsoft.fluentui.theme.token.controlTokens.CardType
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button

@Composable
fun ReportScreen() {
    val metrics = reportMetrics(MaterialTheme.colorScheme.error)

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
                        text = "报告页沿用同一套风格，但重心转到分类汇总、失败聚焦和导出动作。",
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
                        text = "失败聚焦",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    androidx.compose.material3.Text(
                        text = "Wi‑Fi Reboot 回连在第 143 次循环中超过 1 分钟未恢复，当前已保留现场并等待日志归档。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    TokenPill(
                        text = "高优先级",
                        background = MaterialTheme.colorScheme.error.copy(alpha = 0.12f),
                        foreground = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}
