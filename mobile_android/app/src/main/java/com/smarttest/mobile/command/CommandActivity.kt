package com.smarttest.mobile.command

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log
import com.smarttest.mobile.runner.SmartTestRunnerService

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
        when (intent.action) {
            SmartTestCommand.ACTION_RUN -> {
                val request = SmartTestCommand.buildRunRequest(intent) ?: return
                SmartTestRunnerService.enqueueRun(this, request)
            }

            SmartTestCommand.ACTION_STOP -> {
                SmartTestRunnerService.enqueueStop(this, SmartTestCommand.describeIntent(intent))
            }

            SmartTestCommand.ACTION_STATUS -> {
                SmartTestRunnerService.enqueueStatus(this, SmartTestCommand.describeIntent(intent))
            }

            else -> {
                Log.w("SmartTestCommand", "未知指令: ${intent.action}")
            }
        }
    }
}
