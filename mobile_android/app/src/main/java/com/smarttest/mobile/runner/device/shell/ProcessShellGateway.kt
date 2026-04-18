package com.smarttest.mobile.runner.device.shell

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import java.io.IOException
import java.util.concurrent.TimeUnit

class ProcessShellGateway : ShellGateway {
    override suspend fun exec(
        command: String,
        asRoot: Boolean,
        timeoutMs: Long,
    ): ShellResult = withContext(Dispatchers.IO) {
        val startedAt = System.currentTimeMillis()
        val process = try {
            ProcessBuilder(
                if (asRoot) "su" else "sh",
                "-c",
                command,
            ).start()
        } catch (error: IOException) {
            return@withContext ShellResult(
                success = false,
                exitCode = null,
                stdout = "",
                stderr = error.message ?: error.javaClass.simpleName,
                startedAtMs = startedAt,
                finishedAtMs = System.currentTimeMillis(),
            )
        }

        coroutineScope {
            val stdoutReader = async(Dispatchers.IO) {
                process.inputStream.bufferedReader().use { it.readText().trim() }
            }
            val stderrReader = async(Dispatchers.IO) {
                process.errorStream.bufferedReader().use { it.readText().trim() }
            }

            val finished = process.waitFor(timeoutMs, TimeUnit.MILLISECONDS)
            if (!finished) {
                process.destroyForcibly()
            }

            val exitCode = if (finished) process.exitValue() else null
            ShellResult(
                success = finished && exitCode == 0,
                exitCode = exitCode,
                stdout = stdoutReader.await(),
                stderr = stderrReader.await().ifBlank {
                    if (finished) "" else "Timed out after ${timeoutMs}ms"
                },
                startedAtMs = startedAt,
                finishedAtMs = System.currentTimeMillis(),
            )
        }
    }
}
