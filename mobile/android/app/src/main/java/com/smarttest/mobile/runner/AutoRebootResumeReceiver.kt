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

        val sessionStore = AutoRebootSessionStore(context)
        val session = sessionStore.load()
        if (session == null) return
        if (!session.active || !session.awaitingPostBootCheck) {
            return
        }
        val pendingCycle = session.completedCycles + 1
        val dispatchToken = "${session.requestId}:$pendingCycle"
        if (session.resumeDispatchToken == dispatchToken) {
            Log.i(
                "AutoRebootResume",
                "ignore duplicate boot resume dispatch action=$action requestId=${session.requestId}, cycle=$pendingCycle",
            )
            return
        }
        sessionStore.save(session.copy(resumeDispatchToken = dispatchToken))
        Log.i(
            "AutoRebootResume",
            "boot receiver resume requestId=${session.requestId}, trigger=${session.trigger}, " +
                "cycles=${session.totalCycles}, completed=${session.completedCycles}, pendingCycle=$pendingCycle",
        )

        SmartTestRunnerService.enqueueRun(
            context = context,
            request = TestRunRequest(
                caseIds = listOf("auto_reboot"),
                parameterOverrides = mapOf(
                    "auto_reboot:cycle_count" to session.totalCycles.toString(),
                    "auto_reboot:interval_sec" to session.intervalSec.toString(),
                    "auto_reboot:ping_target" to session.pingTarget,
                    "auto_reboot:bt_target" to session.bluetoothTarget,
                ),
                source = session.source,
                trigger = session.trigger,
                requestId = session.requestId,
            ),
        )
        SmartTestUiLauncher.launchMainActivity(context)
    }
}
