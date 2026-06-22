package com.smarttest.mobile.runner

data class TestParameterDefinition(
    val id: String,
    val label: String,
    val hint: String,
    val defaultValue: String,
)

data class TestCaseDefinition(
    val id: String,
    val title: String,
    val objective: String,
    val checks: List<String>,
    val parameters: List<TestParameterDefinition> = emptyList(),
)

data class TestCategoryDefinition(
    val id: String,
    val title: String,
    val summary: String,
    val cases: List<TestCaseDefinition>,
)

object SmartTestCatalog {
    val categories: List<TestCategoryDefinition> = listOf(
        TestCategoryDefinition(
            id = "system",
            title = "System",
            summary = "Implemented system stability cases.",
            cases = listOf(
                TestCaseDefinition(
                    id = "emmc_rw",
                    title = "eMMC Repeated Read and Write",
                    objective = "Continuously copy, read back, and compare data in the DUT work directory.",
                    checks = listOf("Create source file", "Copy file", "Read back file", "Compare file"),
                    parameters = listOf(
                        TestParameterDefinition("loop_count", "Loop Count", "Default 180", "180"),
                        TestParameterDefinition("source_profile", "Source Profile", "random1 / random2", "random1"),
                        TestParameterDefinition("source_size_kb", "Source Size (KB)", "Default 51200", "51200"),
                        TestParameterDefinition("min_free_kb", "Minimum Free Space (KB)", "Default 307200", "307200"),
                        TestParameterDefinition("work_dir", "Working Directory", "Default /data/local/tmp/smarttest/emmc_rw", "/data/local/tmp/smarttest/emmc_rw"),
                    ),
                ),
                TestCaseDefinition(
                    id = "auto_reboot",
                    title = "Auto Reboot",
                    objective = "Run repeated reboot cycles and verify DUT recovery.",
                    checks = listOf("Reboot", "Wait for resume", "Network recovery", "Bluetooth recovery"),
                    parameters = powerCycleParameters(),
                ),
                TestCaseDefinition(
                    id = "auto_suspend",
                    title = "Auto Suspend",
                    objective = "Run repeated suspend/resume cycles and verify DUT recovery.",
                    checks = listOf("Suspend", "Resume", "Network recovery", "Bluetooth recovery"),
                    parameters = powerCycleParameters(),
                ),
            ),
        ),
        TestCategoryDefinition(
            id = "wifi_bt",
            title = "Wi-Fi / Bluetooth",
            summary = "Implemented radio on/off cases.",
            cases = listOf(
                TestCaseDefinition(
                    id = "wifi_onoff_scan",
                    title = "Wi-Fi On and Off Scan",
                    objective = "Repeatedly toggle Wi-Fi and verify reconnect behavior.",
                    checks = listOf("Disable Wi-Fi", "Enable Wi-Fi", "Ping target"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Cycle Count", "Default 2", "2"),
                        TestParameterDefinition("on_wait_sec", "On Wait (s)", "Wait after Wi-Fi is enabled", "5"),
                        TestParameterDefinition("off_wait_sec", "Off Wait (s)", "Wait after Wi-Fi is disabled", "5"),
                        TestParameterDefinition("ping_target", "Ping Target", "Required for reconnect check", ""),
                    ),
                ),
                TestCaseDefinition(
                    id = "bt_onoff_scan",
                    title = "Bluetooth On and Off Scan",
                    objective = "Repeatedly toggle Bluetooth and verify target reconnection.",
                    checks = listOf("Disable Bluetooth", "Enable Bluetooth", "Verify target"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Cycle Count", "Default 2", "2"),
                        TestParameterDefinition("on_wait_sec", "On Wait (s)", "Wait after Bluetooth is enabled", "5"),
                        TestParameterDefinition("off_wait_sec", "Off Wait (s)", "Wait after Bluetooth is disabled", "5"),
                        TestParameterDefinition("bt_target", "Bluetooth Target", "Required connected Bluetooth target or None", ""),
                    ),
                ),
            ),
        ),
    )
}

private fun powerCycleParameters(): List<TestParameterDefinition> {
    return listOf(
        TestParameterDefinition("cycle_count", "Loop Count", "Default 20", "20"),
        TestParameterDefinition("interval_sec", "Interval (s)", "Default 100", "100"),
        TestParameterDefinition("ping_target", "Ping Target", "Optional ping target", ""),
        TestParameterDefinition("bt_target", "Bluetooth Target", "Optional connected Bluetooth target or None", ""),
    )
}
