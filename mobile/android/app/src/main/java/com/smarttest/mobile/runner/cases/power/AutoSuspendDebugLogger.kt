package com.smarttest.mobile.runner.cases.power

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

object AutoSuspendDebugLogger {
    private const val TAG = "AutoSuspendDebug"
    private const val FILE_NAME = "auto_suspend_debug.log"
    private val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS")

    fun append(context: Context, message: String, error: Throwable? = null) {
        val line = buildString {
            append("[")
            append(LocalDateTime.now().format(formatter))
            append("] ")
            append(message)
            if (error != null) {
                append(" | error=")
                append(error.javaClass.name)
                append(": ")
                append(error.message ?: "<empty>")
                var cause = error.cause
                while (cause != null) {
                    append(" | cause=")
                    append(cause.javaClass.name)
                    append(": ")
                    append(cause.message ?: "<empty>")
                    cause = cause.cause
                }
            }
        }
        Log.w(TAG, line, error)
        runCatching {
            val file = resolveFile(context)
            file.parentFile?.mkdirs()
            file.appendText(line + "\n")
        }
    }

    fun logPackagePermissions(context: Context) {
        val packageInfo = loadPackageInfo(context) ?: run {
            append(context, "packageInfo unavailable for ${context.packageName}")
            return
        }
        val requested = packageInfo.requestedPermissions ?: emptyArray()
        val flags = packageInfo.requestedPermissionsFlags ?: IntArray(0)
        if (requested.isEmpty()) {
            append(context, "requestedPermissions=<empty>")
            return
        }
        requested.forEachIndexed { index, permission ->
            val granted = if (index < flags.size) {
                flags[index] and PackageInfo.REQUESTED_PERMISSION_GRANTED != 0
            } else {
                false
            }
            append(context, "requestedPermission[$index]=$permission granted=$granted")
        }
    }

    fun logPublicFilePath(context: Context) {
        append(context, "debugFile=${resolveFile(context).absolutePath}")
    }

    private fun loadPackageInfo(context: Context): PackageInfo? {
        val pm = context.packageManager
        return runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getPackageInfo(
                    context.packageName,
                    PackageManager.PackageInfoFlags.of(PackageManager.GET_PERMISSIONS.toLong()),
                )
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(context.packageName, PackageManager.GET_PERMISSIONS)
            }
        }.getOrNull()
    }

    private fun resolveFile(context: Context): File {
        val root = context.getExternalFilesDir(null) ?: context.filesDir
        return File(root, FILE_NAME)
    }
}
