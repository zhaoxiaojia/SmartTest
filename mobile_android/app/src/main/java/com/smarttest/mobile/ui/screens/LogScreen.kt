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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microsoft.fluentui.theme.token.controlTokens.ButtonSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button
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
                        text = "运行日志",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = if (isRunning) {
                            "当前由测试框架接管执行，日志页只显示运行过程，不介入控制逻辑。"
                        } else {
                            "当前没有运行中的任务，你可以通过 UI 或 am start 指令再次触发测试。"
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = "状态: $statusText",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (commandSummary.isNotBlank()) {
                        Text(
                            text = "最近命令: $commandSummary",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (runningCases.isNotEmpty()) {
                        Text(
                            text = "当前批次: ${runningCases.joinToString(" / ") { it.title }}",
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
                            text = "等待日志输出...",
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
                text = if (isRunning) "停止测试" else "测试已停止",
                modifier = Modifier.fillMaxWidth(),
                style = ButtonStyle.Button,
                size = ButtonSize.Large,
                enabled = isRunning,
            )
        }
    }
}
