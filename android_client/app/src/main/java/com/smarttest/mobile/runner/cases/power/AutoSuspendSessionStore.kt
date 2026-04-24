package com.smarttest.mobile.runner.cases.power

import android.content.Context

data class AutoSuspendSession(
    val totalCycles: Int,
    val intervalSec: Long,
    val completedCycles: Int,
    val awaitingResume: Boolean,
    val source: String,
    val trigger: String,
    val requestId: String,
) {
    fun matchesRequest(
        totalCycles: Int,
        intervalSec: Long,
        source: String,
        trigger: String,
        requestId: String,
    ): Boolean {
        return this.totalCycles == totalCycles &&
            this.intervalSec == intervalSec &&
            this.source == source &&
            this.trigger == trigger &&
            this.requestId == requestId
    }

    fun isRecoverable(): Boolean {
        if (totalCycles <= 0 || intervalSec <= 0L) {
            return false
        }
        if (completedCycles < 0 || completedCycles > totalCycles) {
            return false
        }
        return awaitingResume || completedCycles < totalCycles
    }
}

class AutoSuspendSessionStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    fun load(): AutoSuspendSession? {
        if (!preferences.contains(KEY_TOTAL_CYCLES)) {
            return null
        }
        return AutoSuspendSession(
            totalCycles = preferences.getInt(KEY_TOTAL_CYCLES, 0),
            intervalSec = preferences.getLong(KEY_INTERVAL_SEC, 0L),
            completedCycles = preferences.getInt(KEY_COMPLETED_CYCLES, 0),
            awaitingResume = preferences.getBoolean(KEY_AWAITING_RESUME, false),
            source = preferences.getString(KEY_SOURCE, "alarm") ?: "alarm",
            trigger = preferences.getString(KEY_TRIGGER, "auto_suspend_alarm") ?: "auto_suspend_alarm",
            requestId = preferences.getString(KEY_REQUEST_ID, "manual") ?: "manual",
        )
    }

    fun save(session: AutoSuspendSession) {
        preferences.edit()
            .putInt(KEY_TOTAL_CYCLES, session.totalCycles)
            .putLong(KEY_INTERVAL_SEC, session.intervalSec)
            .putInt(KEY_COMPLETED_CYCLES, session.completedCycles)
            .putBoolean(KEY_AWAITING_RESUME, session.awaitingResume)
            .putString(KEY_SOURCE, session.source)
            .putString(KEY_TRIGGER, session.trigger)
            .putString(KEY_REQUEST_ID, session.requestId)
            .apply()
    }

    fun clear() {
        preferences.edit().clear().apply()
    }

    companion object {
        private const val PREF_NAME = "smarttest.auto_suspend"
        private const val KEY_TOTAL_CYCLES = "total_cycles"
        private const val KEY_INTERVAL_SEC = "interval_sec"
        private const val KEY_COMPLETED_CYCLES = "completed_cycles"
        private const val KEY_AWAITING_RESUME = "awaiting_resume"
        private const val KEY_SOURCE = "source"
        private const val KEY_TRIGGER = "trigger"
        private const val KEY_REQUEST_ID = "request_id"
    }
}
