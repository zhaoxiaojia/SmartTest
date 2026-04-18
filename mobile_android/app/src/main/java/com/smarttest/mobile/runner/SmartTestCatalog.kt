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
            title = "平台稳定性与多媒体",
            summary = "覆盖 CPU、存储、DDR、温控和音视频能力，目标是长稳和异常定位。",
            cases = listOf(
                TestCaseDefinition(
                    id = "cpu_freq_switch",
                    title = "CPU 不同频点切换",
                    objective = "确保每个频点都能正常工作，无死机等异常。",
                    checks = listOf("频点切换可配置", "切换过程中不死机", "异常现场可保留"),
                    parameters = listOf(
                        TestParameterDefinition("freq_set", "频点集合", "例如 1.0/1.4/1.8GHz", "1.0/1.4/1.8GHz"),
                        TestParameterDefinition("stay_time", "单档时长", "例如 10 min", "10 min"),
                    ),
                ),
                TestCaseDefinition(
                    id = "emmc_rw",
                    title = "eMMC 反复读写",
                    objective = "按项目现网脚本重复在 /data 分区做拷贝、回读和 cmp 校验，直到剩余空间低于阈值。",
                    checks = listOf("创建源文件", "循环拷贝到 /data", "逐文件回读", "cmp 校验", "按周期清理"),
                    parameters = listOf(
                        TestParameterDefinition("loop_count", "循环次数", "脚本 LOOP_NUM，默认 180", "180"),
                        TestParameterDefinition("source_profile", "源文件模式", "random1 / random2，当前默认 random1", "random1"),
                        TestParameterDefinition("source_size_kb", "源文件大小(KB)", "脚本 dd count，默认 51200", "51200"),
                        TestParameterDefinition("min_free_kb", "最小剩余空间(KB)", "脚本阈值，默认 307200", "307200"),
                        TestParameterDefinition("work_dir", "工作目录", "默认 /data/local/tmp/smarttest/emmc_rw", "/data/local/tmp/smarttest/emmc_rw"),
                    ),
                ),
                TestCaseDefinition(
                    id = "ddr_stress",
                    title = "DDR Stress",
                    objective = "DDR Stress 测试，无系统崩溃 / 重启等异常。",
                    checks = listOf("压力策略可切换", "崩溃重启自动记录", "统计总运行时长"),
                ),
                TestCaseDefinition(
                    id = "thermal_control",
                    title = "温控逻辑",
                    objective = "验证降频降核和恢复逻辑是否正常。",
                    checks = listOf("阈值可配置", "降频 / 恢复时间点可见", "核数恢复状态可见"),
                    parameters = listOf(
                        TestParameterDefinition("down_threshold", "降频阈值", "例如 92°C", "92°C"),
                        TestParameterDefinition("resume_threshold", "恢复阈值", "例如 78°C", "78°C"),
                    ),
                ),
                TestCaseDefinition(
                    id = "av_codec_loop",
                    title = "音视频编解码",
                    objective = "本地视频循环播放，通过 YUV 对比确认没有软件回退。",
                    checks = listOf("循环播放", "YUV 对比结果", "异常时间戳记录"),
                ),
                TestCaseDefinition(
                    id = "live_channel_switch",
                    title = "直播自动切台",
                    objective = "统计切台次数、切台时长并计算平均值。",
                    checks = listOf("切台总次数", "平均切台时长", "超时切台标红"),
                ),
                TestCaseDefinition(
                    id = "camera_codec",
                    title = "Camera H264/H265 编解码",
                    objective = "内置或 USB camera 编码，异常时记录时间戳。",
                    checks = listOf("相机源可切换", "编码格式可选", "异常自动打点"),
                ),
                TestCaseDefinition(
                    id = "audio_loop",
                    title = "指定音频文件循环播放",
                    objective = "当声音有异常时判定 Fail。",
                    checks = listOf("文件和时长可配置", "异常可人工标记", "结果进入报告"),
                ),
            ),
        ),
        TestCategoryDefinition(
            id = "power_system",
            title = "电源循环与系统维护",
            summary = "聚焦开关机、重启、待机唤醒、升级和恢复出厂，强调次数统计与现场保留。",
            cases = listOf(
                TestCaseDefinition(
                    id = "relay_power_cycle",
                    title = "继电器开关机",
                    objective = "统计开关机次数、到 Launcher 时长、显示输出和日志异常。",
                    checks = listOf("次数可配置", "启动时长统计", "LCD / HDMI 检查", "日志异常采集"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "开关机次数", "例如 1000", "1000"),
                    ),
                ),
                TestCaseDefinition(
                    id = "auto_reboot",
                    title = "AutoReboot",
                    objective = "统计重启次数，并检测画面输出和开机日志异常。",
                    checks = listOf("总次数统计", "画面输出验证", "异常日志关键字"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "重启次数", "例如 20", "20"),
                        TestParameterDefinition("interval_sec", "重启后间隔(s)", "例如 100", "100"),
                    ),
                ),
                TestCaseDefinition(
                    id = "auto_suspend",
                    title = "Autosuspend",
                    objective = "统计待机唤醒次数，并验证唤醒后的画面输出和日志状态。",
                    checks = listOf("待机唤醒次数", "唤醒后 LCD / HDMI 检查", "异常现场保留"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "待机次数", "例如 20", "20"),
                        TestParameterDefinition("interval_sec", "待机间隔(s)", "例如 100", "100"),
                    ),
                ),
                TestCaseDefinition(
                    id = "ota_loop",
                    title = "高低版本循环升级",
                    objective = "统计升级总次数。",
                    checks = listOf("版本矩阵可选", "升级结果统计", "失败版本回滚"),
                    parameters = listOf(
                        TestParameterDefinition("version_pair", "版本组合", "例如 A->B->A", "A->B->A"),
                    ),
                ),
                TestCaseDefinition(
                    id = "factory_reset_loop",
                    title = "自动恢复出厂测试",
                    objective = "统计恢复出厂总次数或设置指定次数。",
                    checks = listOf("次数可配置", "恢复后系统可用性", "异常后保留日志"),
                    parameters = listOf(
                        TestParameterDefinition("reset_count", "恢复出厂次数", "例如 1000", "1000"),
                    ),
                ),
            ),
        ),
        TestCategoryDefinition(
            id = "network_wireless",
            title = "网络与无线连接",
            summary = "围绕 Ethernet、Wi-Fi、Bluetooth 的回连、扫描、稳定性和日志抓取。",
            cases = listOf(
                TestCaseDefinition(
                    id = "eth_toggle",
                    title = "模拟网络插拔",
                    objective = "控制 eth0 Up/Down，确认 Up 后是否能获取 IP 地址。",
                    checks = listOf("接口上下线控制", "IP 获取结果", "失败现场保留"),
                    parameters = listOf(
                        TestParameterDefinition("interface", "网络接口", "例如 eth0", "eth0"),
                    ),
                ),
                TestCaseDefinition(
                    id = "network_regression",
                    title = "网络测试",
                    objective = "检查开关机 / Reboot 后 IP 获取时长，并支持长时间 Ping。",
                    checks = listOf("开关机获取 IP 时长", "Reboot 获取 IP 时长", "长时间 Ping"),
                    parameters = listOf(
                        TestParameterDefinition("ping_target", "Ping 目标", "例如 8.8.8.8", "8.8.8.8"),
                    ),
                ),
                TestCaseDefinition(
                    id = "wifi_power_reconnect",
                    title = "Wi-Fi 继电器开关机回连",
                    objective = "统计 Wi-Fi 回连时长，超时或失败时保留现场。",
                    checks = listOf("测试次数可配置", "回连时长统计", "超过 1 分钟自动标记"),
                    parameters = listOf(
                        TestParameterDefinition("wifi_count", "测试次数", "例如 1000", "1000"),
                        TestParameterDefinition("wifi_ssid", "目标 AP", "例如 Lab-5G", "Lab-5G"),
                    ),
                ),
                TestCaseDefinition(
                    id = "wifi_reboot_reconnect",
                    title = "Wi-Fi Reboot 回连",
                    objective = "复用 Wi-Fi 回连逻辑，针对重启场景验证。",
                    checks = listOf("与开关机场景同口径", "失败时保留现场"),
                ),
                TestCaseDefinition(
                    id = "wifi_onoff_scan",
                    title = "Wi-Fi OnOff 检测",
                    objective = "反复执行 Wi-Fi 开关切换，并在每次切换后检查当前状态。",
                    checks = listOf("切换次数配置", "关闭后状态检查", "开启后状态检查"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "切换次数", "例如 1000", "1000"),
                    ),
                ),
                TestCaseDefinition(
                    id = "bt_power_reconnect",
                    title = "BT 继电器开关机回连",
                    objective = "统计蓝牙设备回连时长，异常时自动抓取相关日志。",
                    checks = listOf("蓝牙设备可配置", "回连时长统计", "超时自动抓 log"),
                    parameters = listOf(
                        TestParameterDefinition("bt_count", "测试次数", "例如 1000", "1000"),
                        TestParameterDefinition("bt_target", "蓝牙目标", "例如 Speaker-A", "Speaker-A"),
                    ),
                ),
                TestCaseDefinition(
                    id = "bt_reboot",
                    title = "BT Reboot",
                    objective = "重启后验证蓝牙设备回连逻辑。",
                    checks = listOf("次数可配置", "回连时长与成功率"),
                ),
                TestCaseDefinition(
                    id = "bt_onoff_scan",
                    title = "BT OnOff 检测",
                    objective = "反复执行蓝牙开关切换，并在每次切换后检查当前状态。",
                    checks = listOf("切换次数配置", "关闭后状态检查", "开启后状态检查"),
                    parameters = listOf(
                        TestParameterDefinition("cycle_count", "切换次数", "例如 1000", "1000"),
                    ),
                ),
            ),
        ),
    )

    private val caseMap: Map<String, Pair<TestCategoryDefinition, TestCaseDefinition>> =
        categories.flatMap { category -> category.cases.map { case -> case.id to (category to case) } }.toMap()

    fun findCase(caseId: String): Pair<TestCategoryDefinition, TestCaseDefinition>? = caseMap[caseId]
}
