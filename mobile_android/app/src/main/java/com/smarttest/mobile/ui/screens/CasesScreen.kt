package com.smarttest.mobile.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.microsoft.fluentui.theme.token.controlTokens.ButtonSize
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.theme.token.controlTokens.CardType
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button
import com.microsoft.fluentui.tokenized.controls.TextField
import com.smarttest.mobile.ui.theme.Grey10
import com.smarttest.mobile.ui.theme.Grey20
import com.smarttest.mobile.ui.theme.SmartBlue

@Composable
fun CasesScreen(
    categories: List<CaseCategory>,
    selectedCases: List<Pair<String, CaseTemplate>>,
    selectedCaseIds: List<String>,
    expandedCaseId: String?,
    parameterValues: Map<String, String>,
    onToggleCase: (CaseTemplate) -> Unit,
    onExpandCase: (String) -> Unit,
    onParameterChange: (String, String, String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        if (selectedCases.isNotEmpty()) {
            SelectedQueueCard(selectedCases = selectedCases)
        }

        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(bottom = 120.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            items(categories) { category ->
                CaseCategoryCard(
                    category = category,
                    selectedCaseIds = selectedCaseIds,
                    expandedCaseId = expandedCaseId,
                    parameterValues = parameterValues,
                    onToggleCase = onToggleCase,
                    onExpandCase = onExpandCase,
                    onParameterChange = onParameterChange,
                )
            }
        }
    }
}

@Composable
fun CasesBottomBar(
    selectedCount: Int,
    onStartRun: () -> Unit,
) {
    Surface(shadowElevation = 10.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "待测 $selectedCount 项",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = if (selectedCount == 0) "请选择至少一项用例" else "开始后将自动跳转到日志页",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Button(
                onClick = onStartRun,
                text = "开始测试",
                style = ButtonStyle.Button,
                size = ButtonSize.Large,
                enabled = selectedCount > 0,
            )
        }
    }
}

@Composable
private fun SelectedQueueCard(
    selectedCases: List<Pair<String, CaseTemplate>>,
) {
    BasicCard(
        modifier = Modifier.fillMaxWidth(),
        cardType = CardType.Elevated,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "待测列表",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            selectedCases.forEachIndexed { index, (_, case) ->
                Surface(
                    color = Grey10.copy(alpha = 0.78f),
                    shape = MaterialTheme.shapes.medium,
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 14.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        TokenPill(
                            text = "${index + 1}",
                            background = SmartBlue.copy(alpha = 0.14f),
                            foreground = SmartBlue,
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = case.title,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CaseCategoryCard(
    category: CaseCategory,
    selectedCaseIds: List<String>,
    expandedCaseId: String?,
    parameterValues: Map<String, String>,
    onToggleCase: (CaseTemplate) -> Unit,
    onExpandCase: (String) -> Unit,
    onParameterChange: (String, String, String) -> Unit,
) {
    BasicCard(
        modifier = Modifier.fillMaxWidth(),
        cardType = CardType.Elevated,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = category.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = category.summary,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        lineHeight = 20.sp,
                    )
                }
                Spacer(modifier = Modifier.width(12.dp))
                TokenPill(
                    text = "${category.cases.size} 项",
                    background = category.accent.copy(alpha = 0.14f),
                    foreground = category.accent,
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                category.cases.chunked(3).forEach { rowCases ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        rowCases.forEach { case ->
                            CaseGridItemCard(
                                case = case,
                                isSelected = selectedCaseIds.contains(case.id),
                                isExpanded = expandedCaseId == case.id &&
                                    selectedCaseIds.contains(case.id) &&
                                    case.parameters.isNotEmpty(),
                                parameterValues = parameterValues,
                                onToggleCase = onToggleCase,
                                onExpandCase = onExpandCase,
                                onParameterChange = onParameterChange,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        repeat(3 - rowCases.size) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CaseGridItemCard(
    case: CaseTemplate,
    isSelected: Boolean,
    isExpanded: Boolean,
    parameterValues: Map<String, String>,
    onToggleCase: (CaseTemplate) -> Unit,
    onExpandCase: (String) -> Unit,
    onParameterChange: (String, String, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        color = if (isSelected) Grey20 else Grey10.copy(alpha = 0.82f),
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onToggleCase(case) },
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    text = case.title,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.width(8.dp))
                Checkbox(
                    checked = isSelected,
                    onCheckedChange = { onToggleCase(case) },
                    colors = CheckboxDefaults.colors(
                        checkedColor = SmartBlue,
                        uncheckedColor = MaterialTheme.colorScheme.outline,
                        checkmarkColor = Color.White,
                    ),
                )
            }

            Spacer(modifier = Modifier.height(44.dp))

            if (isSelected && case.parameters.isNotEmpty()) {
                Button(
                    onClick = { onExpandCase(case.id) },
                    text = if (isExpanded) "收起参数" else "展开参数",
                    style = ButtonStyle.TextButton,
                )
            } else {
                Spacer(modifier = Modifier.height(4.dp))
            }

            if (isExpanded) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    case.parameters.forEach { parameter ->
                        val key = "${case.id}:${parameter.id}"
                        TextField(
                            value = parameterValues[key] ?: parameter.defaultValue,
                            onValueChange = { onParameterChange(case.id, parameter.id, it) },
                            label = parameter.label,
                            hintText = parameter.hint,
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun TokenPill(
    text: String,
    background: Color,
    foreground: Color,
) {
    Surface(
        color = background,
        shape = MaterialTheme.shapes.medium,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            style = MaterialTheme.typography.bodySmall,
            color = foreground,
            fontWeight = FontWeight.Medium,
        )
    }
}
