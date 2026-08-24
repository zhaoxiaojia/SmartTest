package com.smarttest.mobile.ui.navigation

import androidx.annotation.StringRes
import com.smarttest.mobile.R

enum class AppPage(
    @StringRes val titleRes: Int,
    @StringRes val subtitleRes: Int,
) {
    Cases(
        titleRes = R.string.page_cases,
        subtitleRes = R.string.page_cases_subtitle,
    ),
    Log(
        titleRes = R.string.page_log,
        subtitleRes = R.string.page_log_subtitle,
    ),
    Report(
        titleRes = R.string.page_report,
        subtitleRes = R.string.page_report_subtitle,
    ),
}
