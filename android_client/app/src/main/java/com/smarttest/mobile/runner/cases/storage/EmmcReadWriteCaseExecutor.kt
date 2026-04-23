package com.smarttest.mobile.runner.cases.storage

import android.os.StatFs
import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseExecutionResult
import com.smarttest.mobile.runner.cases.TestCaseExecutor
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.security.SecureRandom

class EmmcReadWriteCaseExecutor : TestCaseExecutor {
    override val caseId: String = "emmc_rw"

    override suspend fun execute(context: TestCaseExecutionContext): TestCaseExecutionResult {
        val loopCount = context.intParameter("loop_count", 180)
        val sourceProfile = context.parameter("source_profile", "random1")
        val sourceSizeKb = context.longParameter("source_size_kb", 51_200L)
        val minFreeKb = context.longParameter("min_free_kb", 307_200L)
        val requestedWorkDir = context.parameter("work_dir", "/data/local/tmp/smarttest/emmc_rw")
        val rootAvailable = probeRootShell(context)
        val workDir = resolveWorkDir(context, requestedWorkDir)
        val sourceFile = File(workDir, "source.bin")

        var cycle = 0
        var copyCount = 0
        var copyErrors = 0
        var readErrors = 0
        var checkErrors = 0

        context.log(
            "Start eMMC repeated read/write: loop=$loopCount, profile=$sourceProfile, " +
                "sourceSize=${sourceSizeKb}KB, minFree=${minFreeKb}KB, workDir=${workDir.absolutePath}, root=$rootAvailable",
        )

        cleanupGeneratedFiles(workDir, sourceFile)

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

            for (index in 0 until loopCount) {
                currentCoroutineContext().ensureActive()
                cycle = index + 1
                context.log("cycle $cycle/$loopCount")
                val freeSizeKb = freeSpaceKb(workDir)
                if (freeSizeKb == null) {
                    return TestCaseExecutionResult(
                        passed = false,
                        summary = "Failed to read free space for ${workDir.absolutePath}",
                    )
                }

                if (freeSizeKb <= minFreeKb) {
                    context.log(
                        "Free space ${freeSizeKb}KB is below threshold ${minFreeKb}KB; stop before copy ${copyCount + 1}",
                    )
                    break
                }

                val outFile = File(workDir, "source_${copyCount}.bin")
                context.log("copy ${copyCount + 1}/$loopCount: free=${freeSizeKb}KB target=${outFile.name}")

                val copyOk = runIo("copy_file", context) {
                    copyFile(sourceFile, outFile)
                }
                if (!copyOk) {
                    copyErrors += 1
                }

                val readOk = runIo("read_file", context) {
                    consumeFile(outFile)
                }
                if (!readOk) {
                    readErrors += 1
                }

                val checkOk = runIo("cmp_file", context) {
                    compareFiles(sourceFile, outFile)
                }
                if (!checkOk) {
                    checkErrors += 1
                }

                copyCount += 1
            }
        } finally {
            cleanupGeneratedFiles(workDir, sourceFile)
        }

        val passed = copyErrors == 0 && readErrors == 0 && checkErrors == 0
        val summary = buildString {
            append("eMMC repeated read/write finished: ")
            append("$cycle cycles, $copyCount copies, ")
            append("copy_err=$copyErrors, read_err=$readErrors, check_err=$checkErrors")
        }
        context.log(summary)
        return TestCaseExecutionResult(
            passed = passed,
            summary = if (passed) "$summary, PASS" else "$summary, FAIL",
        )
    }

    private suspend fun probeRootShell(context: TestCaseExecutionContext): Boolean {
        val probe = context.execShell(
            label = "probe_root",
            command = "id",
            requireRoot = true,
        )
        if (probe.result.success) {
            context.log("Root shell is available on DUT")
            return true
        }
        val details = probe.result.stderr.ifBlank { probe.result.stdout }.ifBlank { "unknown root probe failure" }
        context.log("Root shell is not available; use app-scoped file I/O mode. details=$details")
        return false
    }

    private fun resolveWorkDir(
        context: TestCaseExecutionContext,
        requestedWorkDir: String,
    ): File {
        val requested = File(requestedWorkDir)
        if (canUseDirectory(requested)) {
            return requested
        }

        val fallbackRoot = context.appContext.getExternalFilesDir(null) ?: context.appContext.filesDir
        val fallback = File(fallbackRoot, "smarttest/emmc_rw")
        require(canUseDirectory(fallback)) {
            "Unable to create writable fallback work directory: ${fallback.absolutePath}"
        }
        context.log(
            "Requested work directory is not writable by the app; fallback from ${requested.absolutePath} to ${fallback.absolutePath}",
        )
        return fallback
    }

    private fun canUseDirectory(directory: File): Boolean {
        return try {
            if (!directory.exists() && !directory.mkdirs()) {
                return false
            }
            val probe = File(directory, ".smarttest_probe")
            FileOutputStream(probe).use { stream ->
                stream.write(byteArrayOf(0x53, 0x54))
                stream.fd.sync()
            }
            probe.delete()
            true
        } catch (_: IOException) {
            false
        }
    }

    private suspend fun createSourceFile(
        context: TestCaseExecutionContext,
        sourceProfile: String,
        sourceFile: File,
        sourceSizeKb: Long,
    ): TestCaseExecutionResult {
        return try {
            writeSourceFile(sourceProfile, sourceFile, sourceSizeKb)
            context.log("Created source file ${sourceFile.absolutePath} with profile=$sourceProfile")
            TestCaseExecutionResult(
                passed = true,
                summary = "Source file created",
            )
        } catch (error: Exception) {
            TestCaseExecutionResult(
                passed = false,
                summary = "Failed to create source file: ${error.message ?: error.javaClass.simpleName}",
            )
        }
    }

    private suspend fun writeSourceFile(
        sourceProfile: String,
        sourceFile: File,
        sourceSizeKb: Long,
    ) {
        val totalBytes = sourceSizeKb.coerceAtLeast(1L) * 1024L
        val random = SecureRandom()
        val pattern = when (sourceProfile.lowercase()) {
            "pattern1" -> byteArrayOf(0x55.toByte())
            "pattern2" -> byteArrayOf(0x55.toByte(), 0x2A.toByte(), 0x00, 0x7F)
            else -> null
        }
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        var written = 0L
        FileOutputStream(sourceFile).use { output ->
            while (written < totalBytes) {
                currentCoroutineContext().ensureActive()
                val remaining = (totalBytes - written).coerceAtMost(buffer.size.toLong()).toInt()
                if (pattern == null) {
                    random.nextBytes(buffer)
                } else {
                    fillPattern(buffer, pattern)
                }
                output.write(buffer, 0, remaining)
                written += remaining
            }
            output.fd.sync()
        }
    }

    private fun fillPattern(buffer: ByteArray, pattern: ByteArray) {
        var index = 0
        while (index < buffer.size) {
            buffer[index] = pattern[index % pattern.size]
            index += 1
        }
    }

    private suspend fun copyFile(source: File, target: File) {
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        FileInputStream(source).use { input ->
            FileOutputStream(target).use { output ->
                while (true) {
                    currentCoroutineContext().ensureActive()
                    val read = input.read(buffer)
                    if (read <= 0) {
                        break
                    }
                    output.write(buffer, 0, read)
                }
                output.fd.sync()
            }
        }
    }

    private suspend fun consumeFile(source: File) {
        BufferedInputStream(FileInputStream(source)).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                currentCoroutineContext().ensureActive()
                val read = input.read(buffer)
                if (read == -1) {
                    break
                }
                // Consume the file fully to simulate a read pass.
            }
        }
    }

    private suspend fun compareFiles(first: File, second: File): Boolean {
        if (first.length() != second.length()) {
            return false
        }

        BufferedInputStream(FileInputStream(first)).use { left ->
            BufferedInputStream(FileInputStream(second)).use { right ->
                val leftBuffer = ByteArray(DEFAULT_BUFFER_SIZE)
                val rightBuffer = ByteArray(DEFAULT_BUFFER_SIZE)
                while (true) {
                    currentCoroutineContext().ensureActive()
                    val leftRead = left.read(leftBuffer)
                    val rightRead = right.read(rightBuffer)
                    if (leftRead != rightRead) {
                        return false
                    }
                    if (leftRead == -1) {
                        return true
                    }
                    for (index in 0 until leftRead) {
                        if (leftBuffer[index] != rightBuffer[index]) {
                            return false
                        }
                    }
                }
            }
        }
    }

    private fun freeSpaceKb(directory: File): Long? {
        return runCatching {
            val statFs = StatFs(directory.absolutePath)
            statFs.availableBytes / 1024L
        }.getOrNull()
    }

    private fun cleanupGeneratedCopies(workDir: File) {
        workDir.listFiles()
            ?.filter { file -> file.name.startsWith("source_") && file.name.endsWith(".bin") }
            ?.forEach { file -> file.delete() }
    }

    private fun cleanupGeneratedFiles(workDir: File, sourceFile: File) {
        cleanupGeneratedCopies(workDir)
        if (sourceFile.exists()) {
            sourceFile.delete()
        }
    }

    private suspend inline fun runIo(
        label: String,
        context: TestCaseExecutionContext,
        block: () -> Any,
    ): Boolean {
        return try {
            block()
            true
        } catch (error: Exception) {
            context.log("$label failed: ${error.message ?: error.javaClass.simpleName}")
            false
        }
    }
}
