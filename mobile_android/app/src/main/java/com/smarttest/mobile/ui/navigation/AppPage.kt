package com.smarttest.mobile.ui.navigation

enum class AppPage(
    val title: String,
    val subtitle: String,
) {
    Cases(
        title = "用例",
        subtitle = "按三大类管理测试项，勾选后自动加入待测列表。",
    ),
    Log(
        title = "日志",
        subtitle = "由测试框架统一接管运行状态和日志输出。",
    ),
    Report(
        title = "报告",
        subtitle = "汇总最近一次批次结果，并为导出预留结构。",
    ),
}
