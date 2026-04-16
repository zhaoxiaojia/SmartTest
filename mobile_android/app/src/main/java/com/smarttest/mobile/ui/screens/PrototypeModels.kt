package com.smarttest.mobile.ui.screens

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
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
    val title: String,
    val summary: String,
    val accent: Color,
    val cases: List<CaseTemplate>,
)

data class RunningCase(
    val title: String,
    val category: String,
    val parameters: List<Pair<String, String>>,
)

data class ReportMetric(
    val label: String,
    val value: String,
    val accent: Color,
)

@Composable
fun buildCaseCategories(): List<CaseCategory> {
    return listOf(
        CaseCategory(
            title = "平台稳定性与多媒体",
            summary = "覆盖 CPU、存储、DDR、温控和音视频能力，目标是长稳和异常定位。",
            accent = SmartBlue,
            cases = listOf(
                CaseTemplate(
                    id = "cpu_freq_switch",
                    title = "CPU 不同频点切换",
                    objective = "确保每个频点都能 work，无死机等异常。",
                    checks = listOf("频点切换可配置", "切换过程中不死机", "异常现场可保留"),
                    parameters = listOf(
                        CaseParameterTemplate("freq_set", "频点集合", "例如 1.0/1.4/1.8GHz", "1.0/1.4/1.8GHz"),
                        CaseParameterTemplate("stay_time", "单档时长", "例如 10 min", "10 min"),
                    ),
                ),
                CaseTemplate(
                    id = "emmc_rw",
                    title = "eMMC 反复读写",
                    objective = "读写 12H 无异常。",
                    checks = listOf("运行时长可配置", "读写错误单独统计", "异常后保留现场"),
                    parameters = listOf(
                        CaseParameterTemplate("duration", "运行时长", "例如 12 h", "12 h"),
                        CaseParameterTemplate("block_size", "块大小", "例如 4M", "4M"),
                    ),
                ),
                CaseTemplate(
                    id = "ddr_stress",
                    title = "DDR Stress",
                    objective = "DDR Stress 测试，无系统崩溃 / 重启等异常。",
                    checks = listOf("压力策略可切换", "崩溃重启自动记录", "统计总运行时长"),
                ),
                CaseTemplate(
                    id = "thermal_control",
                    title = "温控逻辑",
                    objective = "调节温控阈值，验证降频降核再恢复逻辑是否正常。",
                    checks = listOf("阈值可配置", "降频/恢复时间点可见", "核数恢复状态可见"),
                    parameters = listOf(
                        CaseParameterTemplate("down_threshold", "降频阈值", "例如 92°C", "92°C"),
                        CaseParameterTemplate("resume_threshold", "恢复阈值", "例如 78°C", "78°C"),
                    ),
                ),
                CaseTemplate(
                    id = "av_codec_loop",
                    title = "音视频编解码",
                    objective = "本地视频循环播放，通过对比 YUV 值确认软件没有回退。",
                    checks = listOf("循环播放", "YUV 对比结果", "异常时截图/时间戳"),
                ),
                CaseTemplate(
                    id = "live_channel_switch",
                    title = "直播自动切台",
                    objective = "统计切台次数、切台时长并计算平均值。",
                    checks = listOf("切台总次数", "平均切台时长", "超时切台标红"),
                ),
                CaseTemplate(
                    id = "camera_codec",
                    title = "通过 Camera H264/H265 编解码",
                    objective = "使用内置或 USB camera 编码，异常时记录时间戳。",
                    checks = listOf("相机源可切换", "编码格式可选", "异常时自动打点"),
                ),
                CaseTemplate(
                    id = "audio_loop",
                    title = "指定音频文件循环播放",
                    objective = "当声音有异常则判 Fail。",
                    checks = listOf("文件和时长可配置", "异常可人工标记", "结果进入报告"),
                ),
            ),
        ),
        CaseCategory(
            title = "电源循环与系统维护",
            summary = "聚焦开关机、重启、待机唤醒、升级和恢复出厂，强调次数统计与现场保留。",
            accent = MaterialTheme.colorScheme.tertiary,
            cases = listOf(
                CaseTemplate(
                    id = "relay_power_cycle",
                    title = "继电器开关机",
                    objective = "统计次数、开机到 Launcher 的时长，检测画面输出和日志异常。",
                    checks = listOf("次数可配置", "启动时长统计", "LCD/HDMI 检查", "日志异常采集"),
                    parameters = listOf(
                        CaseParameterTemplate("cycle_count", "开关机次数", "例如 1000", "1000"),
                    ),
                ),
                CaseTemplate(
                    id = "auto_reboot",
                    title = "AutoReboot",
                    objective = "统计重启次数，每次检测画面输出和开机日志异常。",
                    checks = listOf("总次数统计", "画面输出验证", "异常日志关键字"),
                    parameters = listOf(
                        CaseParameterTemplate("reboot_count", "重启次数", "例如 1000", "1000"),
                    ),
                ),
                CaseTemplate(
                    id = "auto_suspend",
                    title = "Autosuspend",
                    objective = "统计待机唤醒次数，每次唤醒后检测画面输出和日志状态。",
                    checks = listOf("待机唤醒次数", "唤醒后 LCD/HDMI 检查", "异常现场保留"),
                    parameters = listOf(
                        CaseParameterTemplate("suspend_count", "待机唤醒次数", "例如 1000", "1000"),
                    ),
                ),
                CaseTemplate(
                    id = "ota_loop",
                    title = "高低版本循环升级",
                    objective = "统计升级总次数。",
                    checks = listOf("版本矩阵可选", "升级结果统计", "失败版本回溯"),
                    parameters = listOf(
                        CaseParameterTemplate("version_pair", "版本组合", "例如 A->B->A", "A->B->A"),
                    ),
                ),
                CaseTemplate(
                    id = "factory_reset_loop",
                    title = "自动恢复出厂测试",
                    objective = "统计恢复出厂总次数或者设置指定次数。",
                    checks = listOf("次数可配置", "恢复后系统可用性", "异常后保留日志"),
                    parameters = listOf(
                        CaseParameterTemplate("reset_count", "恢复出厂次数", "例如 1000", "1000"),
                    ),
                ),
            ),
        ),
        CaseCategory(
            title = "网络与无线连接",
            summary = "围绕 Ethernet、Wi‑Fi、Bluetooth 的回连、扫描、稳定性和日志抓取。",
            accent = MaterialTheme.colorScheme.error,
            cases = listOf(
                CaseTemplate(
                    id = "eth_toggle",
                    title = "模拟网络插拔",
                    objective = "命令 eth0 Up/Down，确认 up 后是否能获取 IP 地址。",
                    checks = listOf("接口上下线控制", "IP 获取结果", "失败现场保留"),
                    parameters = listOf(
                        CaseParameterTemplate("interface", "网络接口", "例如 eth0", "eth0"),
                    ),
                ),
                CaseTemplate(
                    id = "network_regression",
                    title = "网络测试",
                    objective = "检查开关机 / Reboot 后 IP 获取时长，并支持长时间 Ping。",
                    checks = listOf("开关机获取 IP 时长", "Reboot 获取 IP 时长", "长时间 Ping"),
                    parameters = listOf(
                        CaseParameterTemplate("ping_target", "Ping 目标", "例如 8.8.8.8", "8.8.8.8"),
                    ),
                ),
                CaseTemplate(
                    id = "wifi_power_reconnect",
                    title = "Wi‑Fi 继电器开关机回连",
                    objective = "统计 Wi‑Fi 回连时长，超时或无法回连时保留现场。",
                    checks = listOf("测试次数可配置", "回连时长统计", "超过 1 分钟自动标记"),
                    parameters = listOf(
                        CaseParameterTemplate("wifi_count", "测试次数", "例如 1000", "1000"),
                        CaseParameterTemplate("wifi_ssid", "目标 AP", "例如 Lab-5G", "Lab-5G"),
                    ),
                ),
                CaseTemplate(
                    id = "wifi_reboot_reconnect",
                    title = "Wi‑Fi Reboot 回连",
                    objective = "复用 Wi‑Fi 回连逻辑，针对重启场景验证。",
                    checks = listOf("与开关机场景同口径", "失败时保留现场"),
                ),
                CaseTemplate(
                    id = "wifi_onoff_scan",
                    title = "Wi‑Fi OnOff 检测（1000 次）",
                    objective = "检测扫描 AP 个数不小于阈值判 Pass。",
                    checks = listOf("执行次数配置", "AP 阈值配置", "扫描结果统计"),
                    parameters = listOf(
                        CaseParameterTemplate("ap_threshold", "AP 阈值", "例如 20", "20"),
                    ),
                ),
                CaseTemplate(
                    id = "bt_power_reconnect",
                    title = "BT 继电器开关机回连",
                    objective = "统计蓝牙设备回连时长，异常时保留现场并自动抓 log。",
                    checks = listOf("蓝牙设备可配置", "回连时长统计", "超时自动抓 log"),
                    parameters = listOf(
                        CaseParameterTemplate("bt_count", "测试次数", "例如 1000", "1000"),
                        CaseParameterTemplate("bt_target", "蓝牙目标", "例如 Speaker-A", "Speaker-A"),
                    ),
                ),
                CaseTemplate(
                    id = "bt_reboot",
                    title = "BT Reboot（1000 次）",
                    objective = "重启后验证蓝牙设备回连逻辑。",
                    checks = listOf("次数可配置", "回连时长与成功率"),
                ),
                CaseTemplate(
                    id = "bt_onoff_scan",
                    title = "BT OnOff 检测（1000 次）",
                    objective = "检测扫描蓝牙设备个数不小于阈值判 Pass。",
                    checks = listOf("执行次数配置", "设备数阈值", "异常时保留日志"),
                    parameters = listOf(
                        CaseParameterTemplate("bt_threshold", "设备数阈值", "例如 10", "10"),
                    ),
                ),
            ),
        ),
    )
}

fun reportMetrics(accentError: Color): List<ReportMetric> {
    return listOf(
        ReportMetric("平台类", "8 / 8", SmartBlue),
        ReportMetric("系统类", "4 / 5", accentError),
        ReportMetric("网络类", "6 / 8", Grey120),
    )
}
