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
        subtitle = "只打印运行过程信息，不在这里介入执行流程。",
    ),
    Report(
        title = "报告",
        subtitle = "汇总结果、定位失败项，并为后续导出预留结构。",
    ),
}
