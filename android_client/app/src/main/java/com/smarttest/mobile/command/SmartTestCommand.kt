package com.smarttest.mobile.command

import android.content.Context
import android.content.Intent
import android.util.Log
import com.smarttest.mobile.runner.TestRunRequest

object SmartTestCommand {
    const val ACTION_RUN = "com.smarttest.mobile.action.RUN"
    const val ACTION_STOP = "com.smarttest.mobile.action.STOP"
    const val ACTION_STATUS = "com.smarttest.mobile.action.STATUS"

    const val EXTRA_CASE_ID = "case_id"
    const val EXTRA_CASE_IDS = "case_ids"
    const val EXTRA_PARAMS = "params"
    const val EXTRA_SOURCE = "source"
    const val EXTRA_TRIGGER = "trigger"

    fun buildRunRequest(intent: Intent): TestRunRequest? {
        val directCase = intent.getStringExtra(EXTRA_CASE_ID)?.trim().orEmpty()
        val caseIds = buildList {
            if (directCase.isNotEmpty()) add(directCase)
            addAll(
                intent.getStringExtra(EXTRA_CASE_IDS)
                    .orEmpty()
                    .split(",")
                    .map(String::trim)
                    .filter(String::isNotEmpty),
            )
        }.distinct()

        if (caseIds.isEmpty()) {
            Log.w("SmartTestCommand", "RUN command is missing case_id or case_ids")
            return null
        }

        return TestRunRequest(
            caseIds = caseIds,
            parameterOverrides = parseParameters(intent.getStringExtra(EXTRA_PARAMS).orEmpty()),
            source = intent.getStringExtra(EXTRA_SOURCE)?.trim().orEmpty().ifBlank { "adb" },
            trigger = intent.getStringExtra(EXTRA_TRIGGER)?.trim().orEmpty().ifBlank { "am start" },
        )
    }

    fun describeIntent(intent: Intent): String {
        return buildString {
            append(intent.action ?: "NO_ACTION")
            val caseId = intent.getStringExtra(EXTRA_CASE_ID).orEmpty()
            val caseIds = intent.getStringExtra(EXTRA_CASE_IDS).orEmpty()
            if (caseId.isNotBlank()) append(" case_id=$caseId")
            if (caseIds.isNotBlank()) append(" case_ids=$caseIds")
        }
    }

    fun exampleRunIntent(context: Context): Intent {
        return Intent(context, CommandActivity::class.java).apply {
            action = ACTION_RUN
            putExtra(EXTRA_CASE_ID, "wifi_reboot_reconnect")
            putExtra(
                EXTRA_PARAMS,
                "wifi_reboot_reconnect:wifi_count=1000;wifi_reboot_reconnect:wifi_ssid=Lab-5G",
            )
            putExtra(EXTRA_SOURCE, "ui")
            putExtra(EXTRA_TRIGGER, "button")
        }
    }

    private fun parseParameters(raw: String): Map<String, String> {
        if (raw.isBlank()) return emptyMap()
        return raw.split(";", "\n")
            .map(String::trim)
            .filter(String::isNotEmpty)
            .mapNotNull { item ->
                val index = item.indexOf('=')
                if (index <= 0 || index == item.lastIndex) return@mapNotNull null
                item.substring(0, index).trim() to item.substring(index + 1).trim()
            }
            .filter { (key, _) -> ":" in key }
            .toMap()
    }
}
