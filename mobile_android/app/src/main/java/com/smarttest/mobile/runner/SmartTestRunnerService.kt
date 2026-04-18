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
import com.smarttest.mobile.runner.cases.TestCaseExecutionContext
import com.smarttest.mobile.runner.cases.TestCaseRegistry
import com.smarttest.mobile.runner.cases.power.AutoRebootSessionStore
import com.smarttest.mobile.runner.device.SmartDeviceRuntime
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

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            SmartTestCommand.ACTION_RUN -> {
                val request = buildRequest(intent)
                if (request != null) {
                    handleRun(request)
                } else {
                    Log.w("SmartTestRunner", "RUN 指令缺少请求体")
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

        val resolvedCases = request.caseIds.mapNotNull { caseId ->
            val (category, case) = SmartTestCatalog.findCase(caseId) ?: return@mapNotNull null
            RunningCase(
                id = case.id,
                title = case.title,
                category = category.title,
                parameters = case.parameters.map { parameter ->
                    parameter.label to (
                        request.parameterOverrides["${case.id}:${parameter.id}"]
                            ?: parameter.defaultValue
                        )
                },
            )
        }

        if (resolvedCases.isEmpty()) {
            SmartTestRunStore.appendLog("未解析到有效用例，忽略本次 RUN 指令")
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return
        }

        runJob?.cancel()
        SmartTestRunStore.startRun(request, resolvedCases)
        val environment = SmartDeviceRuntime.get(this)
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification("${resolvedCases.size} 项测试执行中"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )

        runJob = serviceScope.launch {
            var failedCount = 0
            try {
                resolvedCases.forEach { runningCase ->
                    val executor = TestCaseRegistry.find(runningCase.id)
                    if (executor == null) {
                        failedCount += 1
                        SmartTestRunStore.appendLog("[${runningCase.title}] 未实现对应执行器")
                        return@forEach
                    }

                    SmartTestRunStore.appendLog("[${runningCase.category}] ${runningCase.title} 开始执行")
                    if (runningCase.parameters.isNotEmpty()) {
                        SmartTestRunStore.appendLog(
                            "参数: ${runningCase.parameters.joinToString(" / ") { "${it.first}=${it.second}" }}",
                        )
                    }

                    val result = executor.execute(
                        TestCaseExecutionContext(
                            appContext = applicationContext,
                            environment = environment,
                            request = request,
                            runningCase = runningCase,
                            logger = SmartTestRunStore::appendLog,
                        ),
                    )

                    SmartTestRunStore.appendLog(result.summary)
                    if (result.pendingResume) {
                        return@launch
                    }
                    if (!result.passed) {
                        failedCount += 1
                    }
                }

                SmartTestRunStore.finishRun(
                    statusText = if (failedCount == 0) {
                        "批次执行完成，所有已实现用例均通过"
                    } else {
                        "批次执行完成，失败 $failedCount 项"
                    },
                    failedCount = failedCount,
                )
            } catch (_: CancellationException) {
                SmartTestRunStore.resetToIdle("测试已停止")
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

        private fun buildRequest(intent: Intent): TestRunRequest? {
            val caseIds = intent.getStringExtra(SmartTestCommand.EXTRA_CASE_IDS)
                .orEmpty()
                .split(",")
                .map(String::trim)
                .filter(String::isNotEmpty)
            if (caseIds.isEmpty()) return null

            return TestRunRequest(
                caseIds = caseIds,
                parameterOverrides = intent.getStringExtra(SmartTestCommand.EXTRA_PARAMS)
                    .orEmpty()
                    .split(";", "\n")
                    .map(String::trim)
                    .filter(String::isNotEmpty)
                    .mapNotNull { item ->
                        val index = item.indexOf('=')
                        if (index <= 0 || index == item.lastIndex) return@mapNotNull null
                        item.substring(0, index).trim() to item.substring(index + 1).trim()
                    }
                    .filter { (key, _) -> ":" in key }
                    .toMap(),
                source = intent.getStringExtra(SmartTestCommand.EXTRA_SOURCE).orEmpty().ifBlank { "adb" },
                trigger = intent.getStringExtra(SmartTestCommand.EXTRA_TRIGGER).orEmpty().ifBlank { "am start" },
            )
        }
    }
}
