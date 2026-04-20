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
            id = "platform_media",
            title = "Platform Stability and Media",
            summary = "Covers CPU, storage, DDR, thermal control, and audio/video validation for long-run stability and issue isolation.",
            cases = listOf(
                TestCaseDefinition(
                    id = "cpu_freq_switch",
                    title = "CPU Frequency Switching",
                    objective = "Verify that every configured frequency point can switch and run without freezing or crashing.",
                    checks = listOf(
                        "Configurable frequency set",
                        "No device freeze during switching",
                        "Abnormal scenes can be preserved",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("freq_set", "Frequency Set", "For example: 1.0/1.4/1.8GHz", "1.0/1.4/1.8GHz"),
                        TestParameterDefinition("stay_time", "Dwell Time", "For example: 10 min", "10 min"),
                    ),
                ),
                TestCaseDefinition(
                    id = "emmc_rw",
                    title = "eMMC Repeated Read and Write",
                    objective = "Continuously copy, read back, and compare data in /data until remaining free space drops below the configured threshold.",
                    checks = listOf(
                        "Create source file",
                        "Loop copy into /data",
                        "Read back each file",
                        "Validate with cmp",
                        "Clean up by cycle",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("loop_count", "Loop Count", "Shell LOOP_NUM, default 180", "180"),
                        TestParameterDefinition("source_profile", "Source Profile", "random1 / random2, default random1", "random1"),
                        TestParameterDefinition("source_size_kb", "Source Size (KB)", "dd count, default 51200", "51200"),
                        TestParameterDefinition("min_free_kb", "Minimum Free Space (KB)", "Free-space threshold, default 307200", "307200"),
                        TestParameterDefinition("work_dir", "Working Directory", "Default /data/local/tmp/smarttest/emmc_rw", "/data/local/tmp/smarttest/emmc_rw"),
                    ),
                ),
                TestCaseDefinition(
                    id = "ddr_stress",
                    title = "DDR Stress",
                    objective = "Run DDR stress validation and confirm the device does not reboot or crash.",
                    checks = listOf(
                        "Switchable stress strategy",
                        "Automatic reboot/crash log record",
                        "Total runtime statistics",
                    ),
                ),
                TestCaseDefinition(
                    id = "thermal_control",
                    title = "Thermal Control Logic",
                    objective = "Verify frequency throttling, core throttling, and recovery logic.",
                    checks = listOf(
                        "Configurable thresholds",
                        "Visible throttle and recovery time points",
                        "Visible core-count recovery state",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("down_threshold", "Throttle Threshold", "For example: 92C", "92C"),
                        TestParameterDefinition("resume_threshold", "Recovery Threshold", "For example: 78C", "78C"),
                    ),
                ),
                TestCaseDefinition(
                    id = "av_codec_loop",
                    title = "Audio and Video Codec Loop",
                    objective = "Loop local video playback and compare YUV output to detect silent rendering regressions.",
                    checks = listOf(
                        "Loop playback",
                        "YUV comparison result",
                        "Timestamp abnormal scenes",
                    ),
                ),
                TestCaseDefinition(
                    id = "live_channel_switch",
                    title = "Live Channel Auto Switching",
                    objective = "Measure channel switching count and duration, then calculate the average result.",
                    checks = listOf(
                        "Total switch count",
                        "Average switch duration",
                        "Highlight timeout switches",
                    ),
                ),
                TestCaseDefinition(
                    id = "camera_codec",
                    title = "Camera H264/H265 Encode and Decode",
                    objective = "Run encoding on the built-in or USB camera and timestamp abnormalities automatically.",
                    checks = listOf(
                        "Switchable camera source",
                        "Selectable codec format",
                        "Automatic abnormal markers",
                    ),
                ),
                TestCaseDefinition(
                    id = "audio_loop",
                    title = "Specified Audio File Loop Playback",
                    objective = "Mark the case as failed when audible anomalies are detected.",
                    checks = listOf(
                        "Configurable file and duration",
                        "Manual abnormal marker",
                        "Result included in report",
                    ),
                ),
            ),
        ),
        TestCategoryDefinition(
            id = "power_system",
            title = "Power Cycles and System Recovery",
            summary = "Focuses on power cycles, reboot, suspend and resume, upgrade, and factory reset with strong emphasis on counters and scene preservation.",
            cases = listOf(
                TestCaseDefinition(
                    id = "relay_power_cycle",
                    title = "Relay Power Cycle",
                    objective = "Count power cycles, launcher boot time, display output, and boot-log abnormalities.",
                    checks = listOf(
                        "Configurable cycle count",
                        "Boot time statistics",
                        "LCD / HDMI validation",
                        "Abnormal log capture",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Cycle Count", "For example: 1000", "1000"),
                    ),
                ),
                TestCaseDefinition(
                    id = "auto_reboot",
                    title = "Auto Reboot",
                    objective = "Count reboot cycles and validate display output plus boot-log health.",
                    checks = listOf(
                        "Total cycle count",
                        "Display output validation",
                        "Boot-log keywords",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Reboot Count", "For example: 20", "20"),
                        TestParameterDefinition("interval_sec", "Interval After Reboot (s)", "For example: 100", "100"),
                    ),
                ),
                TestCaseDefinition(
                    id = "auto_suspend",
                    title = "Auto Suspend",
                    objective = "Count suspend/resume cycles and validate display output and logs after wake-up.",
                    checks = listOf(
                        "Suspend/resume cycle count",
                        "LCD / HDMI validation after wake-up",
                        "Abnormal scene preservation",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Suspend Count", "For example: 20", "20"),
                        TestParameterDefinition("interval_sec", "Suspend Interval (s)", "For example: 100", "100"),
                    ),
                ),
                TestCaseDefinition(
                    id = "ota_loop",
                    title = "High and Low Version Upgrade Loop",
                    objective = "Count successful upgrade rounds across a version matrix.",
                    checks = listOf(
                        "Selectable version matrix",
                        "Upgrade result statistics",
                        "Rollback after failures",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("version_pair", "Version Pair", "For example: A->B->A", "A->B->A"),
                    ),
                ),
                TestCaseDefinition(
                    id = "factory_reset_loop",
                    title = "Automatic Factory Reset",
                    objective = "Count factory reset rounds or run the specified number of resets.",
                    checks = listOf(
                        "Configurable reset count",
                        "System usability after reset",
                        "Log preservation after failure",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("reset_count", "Factory Reset Count", "For example: 1000", "1000"),
                    ),
                ),
            ),
        ),
        TestCategoryDefinition(
            id = "network_wireless",
            title = "Network and Wireless Connectivity",
            summary = "Covers Ethernet, Wi-Fi, and Bluetooth reconnect, scan, stability, and log collection.",
            cases = listOf(
                TestCaseDefinition(
                    id = "eth_toggle",
                    title = "Simulated Ethernet Plug and Unplug",
                    objective = "Toggle eth0 up and down and confirm that IP can be acquired after link up.",
                    checks = listOf(
                        "Interface up/down control",
                        "IP acquisition result",
                        "Failure scene preservation",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("interface", "Network Interface", "For example: eth0", "eth0"),
                    ),
                ),
                TestCaseDefinition(
                    id = "network_regression",
                    title = "Network Regression",
                    objective = "Measure IP acquisition after boot or reboot and optionally run long-duration ping validation.",
                    checks = listOf(
                        "IP acquisition time after boot",
                        "IP acquisition time after reboot",
                        "Long-duration ping",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("ping_target", "Ping Target", "For example: 8.8.8.8", "8.8.8.8"),
                    ),
                ),
                TestCaseDefinition(
                    id = "wifi_power_reconnect",
                    title = "Wi-Fi Reconnect After Power Cycle",
                    objective = "Measure Wi-Fi reconnect duration and preserve the scene when timeout or failure occurs.",
                    checks = listOf(
                        "Configurable test count",
                        "Reconnect duration statistics",
                        "Automatic timeout marker after 1 minute",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("wifi_count", "Test Count", "For example: 1000", "1000"),
                        TestParameterDefinition("wifi_ssid", "Target AP", "For example: Lab-5G", "Lab-5G"),
                    ),
                ),
                TestCaseDefinition(
                    id = "wifi_reboot_reconnect",
                    title = "Wi-Fi Reconnect After Reboot",
                    objective = "Reuse Wi-Fi reconnect validation and focus on the reboot scenario.",
                    checks = listOf(
                        "Same criteria as power-cycle scenario",
                        "Preserve failure scene",
                    ),
                ),
                TestCaseDefinition(
                    id = "wifi_onoff_scan",
                    title = "Wi-Fi On and Off Scan",
                    objective = "Repeatedly toggle Wi-Fi on and off and validate the state after each transition.",
                    checks = listOf(
                        "Configurable cycle count",
                        "State validation after disabling",
                        "State validation after enabling",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Cycle Count", "For example: 1000", "1000"),
                    ),
                ),
                TestCaseDefinition(
                    id = "bt_power_reconnect",
                    title = "Bluetooth Reconnect After Power Cycle",
                    objective = "Measure Bluetooth device reconnect time and capture logs when abnormalities happen.",
                    checks = listOf(
                        "Configurable Bluetooth target",
                        "Reconnect duration statistics",
                        "Automatic log capture on timeout",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("bt_count", "Test Count", "For example: 1000", "1000"),
                        TestParameterDefinition("bt_target", "Bluetooth Target", "For example: Speaker-A", "Speaker-A"),
                    ),
                ),
                TestCaseDefinition(
                    id = "bt_reboot",
                    title = "Bluetooth Reconnect After Reboot",
                    objective = "Validate Bluetooth device reconnect logic after reboot.",
                    checks = listOf(
                        "Configurable cycle count",
                        "Reconnect duration and success rate",
                    ),
                ),
                TestCaseDefinition(
                    id = "bt_onoff_scan",
                    title = "Bluetooth On and Off Scan",
                    objective = "Repeatedly toggle Bluetooth on and off and validate the state after each transition.",
                    checks = listOf(
                        "Configurable cycle count",
                        "State validation after disabling",
                        "State validation after enabling",
                    ),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "Cycle Count", "For example: 1000", "1000"),
                    ),
                ),
            ),
        ),
    )

    private val caseMap: Map<String, Pair<TestCategoryDefinition, TestCaseDefinition>> =
        categories.flatMap { category -> category.cases.map { case -> case.id to (category to case) } }.toMap()

    fun findCase(caseId: String): Pair<TestCategoryDefinition, TestCaseDefinition>? = caseMap[caseId]
}
