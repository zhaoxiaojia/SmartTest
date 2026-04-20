package com.smarttest.mobile.runner

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.smarttest.mobile.R
import com.smarttest.mobile.command.SmartTestCommand
import com.smarttest.mobile.runner.cases.power.AutoRebootSessionStore
import com.smarttest.mobile.runner.device.SmartDeviceEnvironment
import com.smarttest.mobile.runner.device.SmartDeviceEnvironmentFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class SmartTestRunnerService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var runJob: Job? = null

    protected fun createEnvironment(): SmartDeviceEnvironment {
        return SmartDeviceEnvironmentFactory.create(applicationContext)
    }

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            SmartTestCommand.ACTION_RUN -> {
                val request = SmartTestCommand.buildRunRequest(intent)
                if (request != null) {
                    handleRun(request)
                } else {
                    Log.w("SmartTestRunner", "RUN request is missing")
                }
            }

            SmartTestCommand.ACTION_STOP -> handleStop(intent.getStringExtra(EXTRA_REASON).orEmpty())
            SmartTestCommand.ACTION_STATUS -> handleStatus(intent.getStringExtra(EXTRA_REASON).orEmpty())
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        serviceScope.cancel()
        super.onDestroy()
    }

    private fun handleRun(request: TestRunRequest) {
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(getString(R.string.runner_notification_idle)),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )

        val cases = RunRequestResolver.resolveCases(request)
        if (cases.isEmpty()) {
            SmartTestRunStore.appendLog("No runnable cases were resolved from the RUN request")
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return
        }

        runJob?.cancel()
        SmartTestRunStore.startRun(request, cases)
        val environment = createEnvironment()
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification("${cases.size} cases running"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )

        runJob = serviceScope.launch {
            try {
                val execution = RunBatchExecutor.execute(
                    appContext = applicationContext,
                    request = request,
                    cases = cases,
                    environment = environment,
                )
                if (execution.pendingResume) {
                    return@launch
                }
                SmartTestRunStore.finishRun(
                    statusText = if (execution.failedCount == 0) {
                        "Batch finished successfully"
                    } else {
                        "Batch finished with ${execution.failedCount} failed case(s)"
                    },
                    failedCount = execution.failedCount,
                )
            } catch (_: CancellationException) {
                SmartTestRunStore.resetToIdle("Run cancelled")
            } finally {
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
    }

    private fun handleStop(reason: String) {
        val stopReason = reason.ifBlank { "am start STOP" }
        AutoRebootSessionStore(applicationContext).clear()
        SmartTestRunStore.markStopping(stopReason)
        runJob?.cancel()
        runJob = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun handleStatus(reason: String) {
        val summary = reason.ifBlank { "am start STATUS" }
        SmartTestRunStore.markStatus(summary)
        Log.i("SmartTestRunner", "STATUS -> ${SmartTestRunStore.state.value}")
    }

    private fun buildNotification(contentText: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .setContentTitle(getString(R.string.runner_notification_title))
            .setContentText(contentText)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.runner_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.runner_channel_description)
        }
        manager.createNotificationChannel(channel)
    }

    companion object {
        private const val CHANNEL_ID = "smarttest.runner"
        private const val NOTIFICATION_ID = 1001
        private const val EXTRA_REASON = "reason"

        fun enqueueRun(context: Context, request: TestRunRequest) {
            val intent = Intent(context, SmartTestRunnerService::class.java).apply {
                action = SmartTestCommand.ACTION_RUN
                putExtra(SmartTestCommand.EXTRA_CASE_IDS, request.caseIds.joinToString(","))
                putExtra(
                    SmartTestCommand.EXTRA_PARAMS,
                    request.parameterOverrides.entries.joinToString(";") { "${it.key}=${it.value}" },
                )
                putExtra(SmartTestCommand.EXTRA_SOURCE, request.source)
                putExtra(SmartTestCommand.EXTRA_TRIGGER, request.trigger)
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun enqueueStop(context: Context, reason: String) {
            val intent = Intent(context, SmartTestRunnerService::class.java).apply {
                action = SmartTestCommand.ACTION_STOP
                putExtra(EXTRA_REASON, reason)
            }
            context.startService(intent)
        }

        fun enqueueStatus(context: Context, reason: String) {
            val intent = Intent(context, SmartTestRunnerService::class.java).apply {
                action = SmartTestCommand.ACTION_STATUS
                putExtra(EXTRA_REASON, reason)
            }
            context.startService(intent)
        }
    }
}
