package com.smarttest.mobile.runner.cases.power

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import java.lang.reflect.Method

object AutoSuspendPowerController {
    fun scheduleResumeAlarm(
        context: Context,
        delaySec: Long,
        requestId: String,
    ) {
        val appContext = context.applicationContext
        AutoSuspendDebugLogger.append(
            appContext,
            "scheduleResumeAlarm delaySec=$delaySec requestId=$requestId " +
                "nowWall=${System.currentTimeMillis()} nowElapsed=${SystemClock.elapsedRealtime()} " +
                "nowUptime=${SystemClock.uptimeMillis()}",
        )
        val alarmManager = appContext.getSystemService(AlarmManager::class.java)
            ?: error("AlarmManager is unavailable")
        val triggerAtMillis = System.currentTimeMillis() + (delaySec * 1000L)
        AutoSuspendDebugLogger.append(
            appContext,
            "scheduleResumeAlarm triggerAtWall=$triggerAtMillis requestId=$requestId",
        )
        val pendingIntent = resumePendingIntent(appContext)
        alarmManager.cancel(pendingIntent)
        runCatching {
            alarmManager.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                triggerAtMillis,
                pendingIntent,
            )
        }.recoverCatching {
            Log.w("AutoSuspendPower", "Exact alarm unavailable, fallback to inexact RTC wakeup", it)
            AutoSuspendDebugLogger.append(appContext, "setExactAndAllowWhileIdle rejected; fallback to AlarmManager.set", it)
            alarmManager.set(
                AlarmManager.RTC_WAKEUP,
                triggerAtMillis,
                pendingIntent,
            )
        }.getOrElse { error ->
            throw IllegalStateException("Unable to schedule auto suspend resume alarm", error)
        }
    }

    fun cancelResumeAlarm(context: Context) {
        val appContext = context.applicationContext
        val alarmManager = appContext.getSystemService(AlarmManager::class.java) ?: return
        alarmManager.cancel(resumePendingIntent(appContext))
        AutoSuspendDebugLogger.append(
            appContext,
            "cancelResumeAlarm nowWall=${System.currentTimeMillis()} nowElapsed=${SystemClock.elapsedRealtime()}",
        )
    }

    fun goToSleep(context: Context) {
        val appContext = context.applicationContext
        AutoSuspendDebugLogger.logPublicFilePath(appContext)
        AutoSuspendDebugLogger.logPackagePermissions(appContext)
        val powerManager = appContext.getSystemService(PowerManager::class.java)
            ?: error("PowerManager is unavailable")
        AutoSuspendDebugLogger.append(appContext, "goToSleep start interactive=${powerManager.isInteractive}")
        AutoSuspendDebugLogger.append(
            appContext,
            "goToSleep clocks before call elapsed=${SystemClock.elapsedRealtime()} uptime=${SystemClock.uptimeMillis()}",
        )
        invokeHiddenPowerMethod(
            context = appContext,
            powerManager = powerManager,
            methodName = "goToSleep",
            details = "SmartTest auto_suspend",
        )
        AutoSuspendDebugLogger.append(
            appContext,
            "goToSleep return interactive=${powerManager.isInteractive} " +
                "elapsed=${SystemClock.elapsedRealtime()} uptime=${SystemClock.uptimeMillis()}",
        )
    }

    fun wakeUp(context: Context) {
        val appContext = context.applicationContext
        val powerManager = appContext.getSystemService(PowerManager::class.java)
            ?: error("PowerManager is unavailable")
        AutoSuspendDebugLogger.append(appContext, "wakeUp start interactive=${powerManager.isInteractive}")
        AutoSuspendDebugLogger.append(
            appContext,
            "wakeUp clocks before call elapsed=${SystemClock.elapsedRealtime()} uptime=${SystemClock.uptimeMillis()}",
        )
        invokeHiddenPowerMethod(
            context = appContext,
            powerManager = powerManager,
            methodName = "wakeUp",
            details = "SmartTest auto_suspend resume",
        )
        AutoSuspendDebugLogger.append(
            appContext,
            "wakeUp return interactive=${powerManager.isInteractive} " +
                "elapsed=${SystemClock.elapsedRealtime()} uptime=${SystemClock.uptimeMillis()}",
        )
    }

    private fun resumePendingIntent(context: Context): PendingIntent {
        val intent = Intent(context, AutoSuspendResumeReceiver::class.java).apply {
            action = AutoSuspendResumeReceiver.ACTION_RESUME
        }
        return PendingIntent.getBroadcast(
            context,
            1002,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun invokeHiddenPowerMethod(
        context: Context,
        powerManager: PowerManager,
        methodName: String,
        details: String,
    ) {
        val candidateMethods = (PowerManager::class.java.methods + PowerManager::class.java.declaredMethods)
            .filter { it.name == methodName }
            .sortedBy { it.parameterTypes.size }
        AutoSuspendDebugLogger.append(
            context,
            "invokeHiddenPowerMethod method=$methodName candidates=${candidateMethods.size} signatures=${candidateMethods.joinToString(" | ") { it.toGenericString() }}",
        )

        val uptime = SystemClock.uptimeMillis()
        var lastError: Throwable? = null
        for (method in candidateMethods) {
            val args = buildArgs(method, uptime, details) ?: continue
            try {
                method.isAccessible = true
                method.invoke(powerManager, *args)
                AutoSuspendDebugLogger.append(
                    context,
                    "PowerManager.$methodName success signature=${method.toGenericString()} args=${args.contentToString()}",
                )
                return
            } catch (error: Throwable) {
                lastError = error
                Log.w(
                    "AutoSuspendPower",
                    "PowerManager.$methodName failed for signature=${method.toGenericString()} args=${args.contentToString()}",
                    error,
                )
                AutoSuspendDebugLogger.append(
                    context,
                    "PowerManager.$methodName failed signature=${method.toGenericString()} args=${args.contentToString()}",
                    error,
                )
            }
        }

        AutoSuspendDebugLogger.append(
            context,
            "PowerManager.$methodName exhausted all candidates",
            lastError,
        )
        throw IllegalStateException(
            "Unable to invoke PowerManager.$methodName via reflection",
            lastError,
        )
    }

    private fun buildArgs(
        method: Method,
        uptime: Long,
        details: String,
    ): Array<Any?>? {
        val args = mutableListOf<Any?>()
        method.parameterTypes.forEachIndexed { index, type ->
            val value = when (type) {
                java.lang.Long.TYPE,
                java.lang.Long::class.java,
                java.lang.Long::class.javaObjectType -> uptime

                java.lang.Integer.TYPE,
                java.lang.Integer::class.java,
                java.lang.Integer::class.javaObjectType -> 0

                java.lang.Boolean.TYPE,
                java.lang.Boolean::class.java,
                java.lang.Boolean::class.javaObjectType -> false

                String::class.java -> details
                else -> return null
            }
            if (index == 0 && value !is Long) {
                return null
            }
            args += value
        }
        return args.toTypedArray()
    }
}
