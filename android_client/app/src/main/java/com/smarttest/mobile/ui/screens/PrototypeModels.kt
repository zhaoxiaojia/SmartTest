package com.smarttest.mobile.ui.screens

import androidx.compose.ui.graphics.Color

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

@Suppress("UNUSED_PARAMETER")
fun buildCaseCategories(
    tertiaryAccent: Color,
    errorAccent: Color,
): List<CaseCategory> {
    return emptyList()
}
