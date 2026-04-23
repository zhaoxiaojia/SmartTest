package com.smarttest.mobile.command

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log
import com.smarttest.mobile.runner.SmartTestRunnerService
import com.smarttest.mobile.runner.SmartTestUiLauncher

class CommandActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        dispatch(intent)
        finish()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        dispatch(intent)
        finish()
    }

    private fun dispatch(intent: Intent?) {
        if (intent == null) return
        com.smarttest.mobile.runner.SmartTestRunStore.initialize(this)
        when (intent.action) {
            SmartTestCommand.ACTION_RUN -> {
                val request = SmartTestCommand.buildRunRequest(intent) ?: return
                Log.i(
                    "SmartTestCommand",
                    "dispatch RUN requestId=${request.requestId}, source=${request.source}, " +
                        "trigger=${request.trigger}, cases=${request.caseIds}, params=${request.parameterOverrides}",
                )
                SmartTestRunnerService.enqueueRun(this, request)
                launchMainActivity()
            }

            SmartTestCommand.ACTION_STOP -> {
                SmartTestRunnerService.enqueueStop(this, SmartTestCommand.describeIntent(intent))
            }

            SmartTestCommand.ACTION_STATUS -> {
                SmartTestRunnerService.enqueueStatus(this, SmartTestCommand.describeIntent(intent))
            }

            else -> {
                Log.w("SmartTestCommand", "Unknown command: ${intent.action}")
            }
        }
    }

    private fun launchMainActivity() {
        SmartTestUiLauncher.launchMainActivity(this)
    }
}
