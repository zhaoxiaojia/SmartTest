package com.smarttest.mobile.runner.cases.power

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import com.smarttest.mobile.logging.SmartTestLog

object AutoSuspendDebugLogger {
    private const val TAG = "AutoSuspendDebug"
    fun append(@Suppress("UNUSED_PARAMETER") context: Context, message: String, error: Throwable? = null) {
        SmartTestLog.warning(TAG, message, error)
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

}
