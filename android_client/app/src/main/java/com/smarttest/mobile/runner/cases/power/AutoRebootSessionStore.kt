package com.smarttest.mobile.runner.cases.power

import android.content.Context

data class AutoRebootSession(
    val active: Boolean,
    val totalCycles: Int,
    val intervalSec: Long,
    val completedCycles: Int,
    val awaitingPostBootCheck: Boolean,
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
        if (!active || totalCycles <= 0 || intervalSec <= 0L) {
            return false
        }
        if (completedCycles < 0 || completedCycles > totalCycles) {
            return false
        }
        return awaitingPostBootCheck || completedCycles < totalCycles
    }
}

class AutoRebootSessionStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    fun load(): AutoRebootSession? {
        if (!preferences.getBoolean(KEY_ACTIVE, false)) {
            return null
        }
        return AutoRebootSession(
            active = true,
            totalCycles = preferences.getInt(KEY_TOTAL_CYCLES, 0),
            intervalSec = preferences.getLong(KEY_INTERVAL_SEC, 0L),
            completedCycles = preferences.getInt(KEY_COMPLETED_CYCLES, 0),
            awaitingPostBootCheck = preferences.getBoolean(KEY_AWAITING_POST_BOOT, false),
            source = preferences.getString(KEY_SOURCE, "boot") ?: "boot",
            trigger = preferences.getString(KEY_TRIGGER, "boot_completed") ?: "boot_completed",
            requestId = preferences.getString(KEY_REQUEST_ID, "manual") ?: "manual",
        )
    }

    fun save(session: AutoRebootSession) {
        preferences.edit()
            .putBoolean(KEY_ACTIVE, session.active)
            .putInt(KEY_TOTAL_CYCLES, session.totalCycles)
            .putLong(KEY_INTERVAL_SEC, session.intervalSec)
            .putInt(KEY_COMPLETED_CYCLES, session.completedCycles)
            .putBoolean(KEY_AWAITING_POST_BOOT, session.awaitingPostBootCheck)
            .putString(KEY_SOURCE, session.source)
            .putString(KEY_TRIGGER, session.trigger)
            .putString(KEY_REQUEST_ID, session.requestId)
            .apply()
    }

    fun clear() {
        preferences.edit().clear().apply()
    }

    companion object {
        private const val PREF_NAME = "smarttest.auto_reboot"
        private const val KEY_ACTIVE = "active"
        private const val KEY_TOTAL_CYCLES = "total_cycles"
        private const val KEY_INTERVAL_SEC = "interval_sec"
        private const val KEY_COMPLETED_CYCLES = "completed_cycles"
        private const val KEY_AWAITING_POST_BOOT = "awaiting_post_boot"
        private const val KEY_SOURCE = "source"
        private const val KEY_TRIGGER = "trigger"
        private const val KEY_REQUEST_ID = "request_id"
    }
}
