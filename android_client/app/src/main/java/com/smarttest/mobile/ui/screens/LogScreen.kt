package com.smarttest.mobile.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.abs
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
    currentLoop: Int?,
    totalLoops: Int?,
    currentStage: String,
) {
    val logListState = rememberLazyListState()
    LaunchedEffect(logLines.size) {
        if (logLines.isNotEmpty()) {
            logListState.animateScrollToItem(logLines.lastIndex)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(start = 20.dp, end = 20.dp, bottom = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
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
                if (currentLoop != null && totalLoops != null && totalLoops > 0) {
                    Text(
                        text = "Loop $currentLoop / $totalLoops",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (currentStage.isNotBlank()) {
                    Text(
                        text = currentStage,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            color = Color(0xFF111827),
            shape = MaterialTheme.shapes.large,
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
            ) {
                if (logLines.isEmpty()) {
                    Text(
                        text = stringResource(R.string.log_waiting),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFFE5E7EB),
                        fontFamily = FontFamily.Monospace,
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(end = 10.dp),
                        state = logListState,
                        contentPadding = PaddingValues(bottom = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        itemsIndexed(logLines) { _, line ->
                            Text(
                                text = line,
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFE5E7EB),
                                fontFamily = FontFamily.Monospace,
                                lineHeight = 20.sp,
                            )
                        }
                    }
                    LogScrollbar(
                        modifier = Modifier
                            .align(Alignment.CenterEnd)
                            .fillMaxHeight(),
                        totalItems = logLines.size,
                        listState = logListState,
                    )
                }
            }
        }
    }
}

@Composable
private fun LogScrollbar(
    modifier: Modifier = Modifier,
    totalItems: Int,
    listState: androidx.compose.foundation.lazy.LazyListState,
) {
    if (totalItems <= 0) return

    val density = LocalDensity.current
    val metrics by remember(totalItems, listState) {
        derivedStateOf {
            val layoutInfo = listState.layoutInfo
            val visibleItems = layoutInfo.visibleItemsInfo
            if (visibleItems.isEmpty()) {
                return@derivedStateOf null
            }
            val viewportHeightPx = (layoutInfo.viewportEndOffset - layoutInfo.viewportStartOffset).coerceAtLeast(1)
            val averageItemHeightPx = visibleItems.map { it.size }.average().toFloat().coerceAtLeast(1f)
            val estimatedContentHeightPx = max(
                viewportHeightPx.toFloat(),
                averageItemHeightPx * totalItems,
            )
            val thumbHeightPx = max(
                with(density) { 36.dp.toPx() },
                viewportHeightPx * (viewportHeightPx / estimatedContentHeightPx),
            )
            val scrollOffsetPx =
                visibleItems.first().index * averageItemHeightPx + abs(visibleItems.first().offset.toFloat())
            val maxScrollPx = max(1f, estimatedContentHeightPx - viewportHeightPx)
            val maxThumbOffsetPx = max(0f, viewportHeightPx - thumbHeightPx)
            val thumbOffsetPx = min(maxThumbOffsetPx, (scrollOffsetPx / maxScrollPx) * maxThumbOffsetPx)
            ScrollbarMetrics(
                thumbHeight = with(density) { thumbHeightPx.toDp() },
                thumbOffset = with(density) { thumbOffsetPx.toDp() },
            )
        }
    }

    val resolved = metrics ?: return
    Box(
        modifier = modifier
            .width(8.dp)
            .fillMaxHeight()
            .padding(start = 2.dp)
            .clip(MaterialTheme.shapes.small),
    ) {
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .padding(vertical = 2.dp)
                .fillMaxWidth(),
        )
        Box(
            modifier = Modifier
                .padding(top = resolved.thumbOffset)
                .fillMaxWidth()
                .heightIn(min = resolved.thumbHeight)
                .clip(MaterialTheme.shapes.small),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(MaterialTheme.shapes.small)
                    .background(Color(0x66E5E7EB)),
            )
        }
    }
}

private data class ScrollbarMetrics(
    val thumbHeight: Dp,
    val thumbOffset: Dp,
)

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
