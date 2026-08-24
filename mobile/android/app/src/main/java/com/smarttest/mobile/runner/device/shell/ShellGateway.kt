package com.smarttest.mobile.runner.device.shell

data class ShellResult(
    val success: Boolean,
    val exitCode: Int?,
    val stdout: String,
    val stderr: String,
    val startedAtMs: Long,
    val finishedAtMs: Long,
) {
    val durationMs: Long
        get() = finishedAtMs - startedAtMs
}

interface ShellGateway {
    suspend fun exec(
        command: String,
        asRoot: Boolean = false,
        timeoutMs: Long = 15_000L,
    ): ShellResult
}
