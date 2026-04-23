package com.smarttest.mobile.runner

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.smarttest.mobile.runner.cases.power.AutoRebootSessionStore

class AutoRebootResumeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action.orEmpty()
        if (action != Intent.ACTION_BOOT_COMPLETED && action != Intent.ACTION_LOCKED_BOOT_COMPLETED) {
            return
        }

        val session = AutoRebootSessionStore(context).load()
        if (session == null) return
        if (!session.active || !session.awaitingPostBootCheck) {
            return
        }
        Log.i(
            "AutoRebootResume",
            "boot receiver resume requestId=${session.requestId}, trigger=${session.trigger}, " +
                "cycles=${session.totalCycles}, completed=${session.completedCycles}",
        )

        SmartTestRunnerService.enqueueRun(
            context = context,
            request = TestRunRequest(
                caseIds = listOf("auto_reboot"),
                parameterOverrides = mapOf(
                    "auto_reboot:cycle_count" to session.totalCycles.toString(),
                    "auto_reboot:interval_sec" to session.intervalSec.toString(),
                ),
                source = session.source,
                trigger = session.trigger,
                requestId = session.requestId,
            ),
        )
        SmartTestUiLauncher.launchMainActivity(context)
    }
}
