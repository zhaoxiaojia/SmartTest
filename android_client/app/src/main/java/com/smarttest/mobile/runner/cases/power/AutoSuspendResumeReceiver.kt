package com.smarttest.mobile.runner.cases.power

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.util.Base64
import com.smarttest.mobile.command.CommandActivity
import com.smarttest.mobile.command.SmartTestCommand
import org.json.JSONObject

class AutoSuspendResumeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != ACTION_RESUME) {
            return
        }
        val appContext = context.applicationContext
        val session = AutoSuspendSessionStore(appContext).load()
        AutoSuspendDebugLogger.append(
            appContext,
            "resume receiver fired action=${intent.action} elapsedNow=${SystemClock.elapsedRealtime()} " +
                "uptimeNow=${SystemClock.uptimeMillis()} requestId=${session?.requestId ?: "<missing>"} " +
                "completedCycles=${session?.completedCycles ?: -1} awaitingResume=${session?.awaitingResume ?: false}",
        )
        runCatching {
            AutoSuspendPowerController.wakeUp(appContext)
        }.onFailure {
            AutoSuspendDebugLogger.append(appContext, "resume receiver wakeUp failed", it)
        }
        if (session == null || !session.isRecoverable()) {
            AutoSuspendDebugLogger.append(appContext, "resume receiver ignored: no recoverable session")
            return
        }
        val sessionAgeMs = (SystemClock.elapsedRealtime() - session.sleepRequestElapsedRealtimeMs).coerceAtLeast(0L)
        AutoSuspendDebugLogger.append(
            appContext,
            "resume receiver session ageMs=$sessionAgeMs requestId=${session.requestId}",
        )

        val params = JSONObject().apply {
            put("auto_suspend:cycle_count", session.totalCycles.toString())
            put("auto_suspend:interval_sec", session.intervalSec.toString())
        }
        val encodedParams = Base64.encodeToString(
            params.toString().toByteArray(Charsets.UTF_8),
            Base64.URL_SAFE or Base64.NO_WRAP,
        ).trimEnd('=')
        val commandIntent = Intent(appContext, CommandActivity::class.java).apply {
            action = SmartTestCommand.ACTION_RUN
            putExtra(SmartTestCommand.EXTRA_CASE_ID, "auto_suspend")
            putExtra(SmartTestCommand.EXTRA_PARAMS_B64, encodedParams)
            putExtra(SmartTestCommand.EXTRA_SOURCE, session.source)
            putExtra(SmartTestCommand.EXTRA_TRIGGER, session.trigger)
            putExtra(SmartTestCommand.EXTRA_REQUEST_ID, session.requestId)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }
        appContext.startActivity(commandIntent)
        AutoSuspendDebugLogger.append(
            appContext,
            "resume receiver dispatched CommandActivity requestId=${session.requestId} " +
                "params={auto_suspend:cycle_count=${session.totalCycles},auto_suspend:interval_sec=${session.intervalSec}}",
        )
    }

    companion object {
        const val ACTION_RESUME = "com.smarttest.mobile.action.AUTO_SUSPEND_RESUME"
    }
}
