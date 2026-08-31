package com.smarttest.mobile.ui.screens

import androidx.compose.ui.graphics.Color
import com.smarttest.mobile.runner.SmartTestCatalog

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

fun buildCaseCategories(
    tertiaryAccent: Color,
    errorAccent: Color,
): List<CaseCategory> {
    return SmartTestCatalog.categories.mapIndexed { index, category ->
        CaseCategory(
            id = category.id,
            title = category.title,
            summary = category.summary,
            accent = if (index % 2 == 0) tertiaryAccent else errorAccent,
            cases = category.cases.map { case ->
                CaseTemplate(
                    id = case.id,
                    title = case.title,
                    objective = case.objective,
                    checks = case.checks,
                    parameters = case.parameters.map { parameter ->
                        CaseParameterTemplate(
                            id = parameter.id,
                            label = parameter.label,
                            hint = parameter.hint,
                            defaultValue = parameter.defaultValue,
                        )
                    },
                )
            },
        )
    }
}
