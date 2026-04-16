package com.smarttest.mobile.ui.screens

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.smarttest.mobile.runner.SmartTestCatalog
import com.smarttest.mobile.runner.TestCaseDefinition
import com.smarttest.mobile.runner.TestCategoryDefinition
import com.smarttest.mobile.runner.TestParameterDefinition
import com.smarttest.mobile.ui.theme.Grey120
import com.smarttest.mobile.ui.theme.SmartBlue

data class CaseParameterTemplate(
    val id: String,
    val label: String,
    val hint: String,
    val defaultValue: String,
)

data class CaseTemplate(
    val id: String,
    val title: String,
    val objective: String,
    val checks: List<String>,
    val parameters: List<CaseParameterTemplate> = emptyList(),
)

data class CaseCategory(
    val id: String,
    val title: String,
    val summary: String,
    val accent: Color,
    val cases: List<CaseTemplate>,
)

data class ReportMetric(
    val label: String,
    val value: String,
    val accent: Color,
)

@Composable
fun buildCaseCategories(): List<CaseCategory> {
    return SmartTestCatalog.categories.map { category ->
        category.toUiCategory(accentFor(category.id))
    }
}

private fun TestCategoryDefinition.toUiCategory(accent: Color): CaseCategory {
    return CaseCategory(
        id = id,
        title = title,
        summary = summary,
        accent = accent,
        cases = cases.map(TestCaseDefinition::toUiCase),
    )
}

private fun TestCaseDefinition.toUiCase(): CaseTemplate {
    return CaseTemplate(
        id = id,
        title = title,
        objective = objective,
        checks = checks,
        parameters = parameters.map(TestParameterDefinition::toUiParameter),
    )
}

private fun TestParameterDefinition.toUiParameter(): CaseParameterTemplate {
    return CaseParameterTemplate(
        id = id,
        label = label,
        hint = hint,
        defaultValue = defaultValue,
    )
}

@Composable
private fun accentFor(categoryId: String): Color {
    return when (categoryId) {
        "platform_media" -> SmartBlue
        "power_system" -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.error
    }
}

fun reportMetrics(accentError: Color): List<ReportMetric> {
    return listOf(
        ReportMetric("平台类", "8 / 8", SmartBlue),
        ReportMetric("系统类", "4 / 5", accentError),
        ReportMetric("网络类", "6 / 8", Grey120),
    )
}
