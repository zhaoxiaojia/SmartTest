package com.smarttest.mobile.runner.cases.storage

import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

class EmmcReadWriteCaseExecutor : TestCaseExecutor {
    override val caseId: String = "emmc_rw"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val loopCount = context.intParameter("loop_count", 180)
        val sourceProfile = context.parameter("source_profile", "random1")
        val sourceSizeKb = context.longParameter("source_size_kb", 51_200L)
        val minFreeKb = context.longParameter("min_free_kb", 307_200L)
        val workDir = context.parameter("work_dir", "/data/local/tmp/smarttest/emmc_rw")
        val sourceFile = "$workDir/source.bin"

        var cycle = 0
        var copyCount = 0
        var copyErrors = 0
        var readErrors = 0
        var checkErrors = 0

        context.log(
            "开始 eMMC 反复读写: loop=$loopCount, profile=$sourceProfile, sourceSize=${sourceSizeKb}KB, " +
                "minFree=${minFreeKb}KB, workDir=$workDir",
        )

        context.execShell(
            label = "prepare_workdir",
            command = "mkdir -p '${workDir}' && rm -f '${sourceFile}' '${sourceFile}'_* && sync",
        )

        try {
            val createSource = createSourceFile(
                context = context,
                sourceProfile = sourceProfile,
                sourceFile = sourceFile,
                sourceSizeKb = sourceSizeKb,
            )
            if (!createSource.passed) {
                return createSource
            }

            repeat(loopCount) {
                currentCoroutineContext().ensureActive()
                cycle += 1
                context.log("cycle $cycle/$loopCount")

                while (true) {
                    currentCoroutineContext().ensureActive()
                    val freeResult = context.execShell(
                        label = "free_size",
                        command = "df -k /data | tail -1 | awk '{print \$4}'",
                    )
                    val freeSizeKb = freeResult.result.stdout.lineSequence()
                        .lastOrNull()
                        ?.trim()
                        ?.toLongOrNull()

                    if (!freeResult.result.success || freeSizeKb == null) {
                        context.log("读取 /data 剩余空间失败，stdout='${freeResult.result.stdout}', stderr='${freeResult.result.stderr}'")
                        return TestCaseExecutionResult(
                            passed = false,
                            summary = "读取 /data 剩余空间失败，已中止 eMMC 反复读写",
                        )
                    }

                    if (freeSizeKb <= minFreeKb) {
                        context.log("剩余空间 ${freeSizeKb}KB 低于阈值 ${minFreeKb}KB，本轮停止继续写入")
                        break
                    }

                    val outFile = "${sourceFile}_$copyCount"
                    context.log("开始第 ${copyCount + 1} 次拷贝，当前剩余 ${freeSizeKb}KB")

                    val copyResult = context.execShell(
                        label = "copy_file",
                        command = "dd if='${sourceFile}' of='${outFile}'",
                    )
                    if (!copyResult.result.success) {
                        copyErrors += 1
                        context.log("拷贝失败 exit=${copyResult.result.exitCode}, stderr=${copyResult.result.stderr}")
                    }

                    context.execShell(
                        label = "fsync_outfile",
                        command = "busybox fsync '${outFile}' || sync '${outFile}' || sync",
                    )

                    val readResult = context.execShell(
                        label = "read_file",
                        command = "dd if='${outFile}' of=/dev/null",
                    )
                    if (!readResult.result.success) {
                        readErrors += 1
                        context.log("读取失败 exit=${readResult.result.exitCode}, stderr=${readResult.result.stderr}")
                    }

                    val checkResult = context.execShell(
                        label = "cmp_file",
                        command = "cmp '${sourceFile}' '${outFile}'",
                    )
                    if (!checkResult.result.success) {
                        checkErrors += 1
                        context.log("校验失败 exit=${checkResult.result.exitCode}, stderr=${checkResult.result.stderr}")
                    }

                    copyCount += 1
                }

                context.execShell(
                    label = "cleanup_cycle",
                    command = "rm -f '${sourceFile}'_* && sync",
                )
            }
        } finally {
            context.execShell(
                label = "cleanup_final",
                command = "rm -f '${sourceFile}' '${sourceFile}'_* && sync",
            )
        }

        val passed = copyErrors == 0 && readErrors == 0 && checkErrors == 0
        val summary = buildString {
            append("eMMC 反复读写完成: ")
            append("$cycle cycles, $copyCount copies, ")
            append("copy_err=$copyErrors, read_err=$readErrors, check_err=$checkErrors")
        }
        context.log(summary)
        return TestCaseExecutionResult(
            passed = passed,
            summary = if (passed) "$summary, PASS" else "$summary, FAIL",
        )
    }

    private suspend fun createSourceFile(
        context: TestCaseExecutionContext,
        sourceProfile: String,
        sourceFile: String,
        sourceSizeKb: Long,
    ): TestCaseExecutionResult {
        val profile = sourceProfile.lowercase()
        if (profile == "pattern1" || profile == "pattern2") {
            context.log("当前版本仅迁移项目里正在使用的随机源文件路径，pattern1/pattern2 暂未接入")
            return TestCaseExecutionResult(
                passed = false,
                summary = "未实现的 source_profile=$sourceProfile",
            )
        }

        if (profile == "random2") {
            context.log("原项目脚本中 random2 注释为 2k，但实际实现与 random1 相同，这里保持一致迁移")
        }

        val sdkResult = context.execShell(
            label = "get_sdk_version",
            command = "getprop ro.build.version.sdk",
        )
        val sdkVersion = sdkResult.result.stdout.trim().toIntOrNull() ?: 0

        val blockPath = if (sdkVersion == 28) {
            val systemBlock = context.execShell(
                label = "detect_system_block",
                command = "if [ -f /dev/block/system ]; then echo /dev/block/system; else echo /dev/block/by-name/system; fi",
            )
            systemBlock.result.stdout.lineSequence().lastOrNull()?.trim().orEmpty()
        } else {
            "/dev/block/by-name/super"
        }

        if (blockPath.isBlank()) {
            return TestCaseExecutionResult(
                passed = false,
                summary = "未找到可用的块设备作为随机源文件输入",
            )
        }

        val createResult = context.execShell(
            label = "create_source_file",
            command = "dd if='${blockPath}' of='${sourceFile}' bs=1024 count=${sourceSizeKb} && sync",
        )
        if (!createResult.result.success) {
            return TestCaseExecutionResult(
                passed = false,
                summary = "创建源文件失败: ${createResult.result.stderr.ifBlank { createResult.result.stdout }}",
            )
        }

        context.log("已创建源文件 $sourceFile，来源块设备 $blockPath")
        return TestCaseExecutionResult(
            passed = true,
            summary = "源文件创建成功",
        )
    }
}
