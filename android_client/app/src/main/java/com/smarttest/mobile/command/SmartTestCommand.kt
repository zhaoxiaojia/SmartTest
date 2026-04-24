package com.smarttest.mobile.command

import android.content.Context
import android.content.Intent
import android.util.Log
import android.util.Base64
import com.smarttest.mobile.runner.TestRunRequest
import org.json.JSONObject

object SmartTestCommand {
    const val ACTION_RUN = "com.smarttest.mobile.action.RUN"
    const val ACTION_STOP = "com.smarttest.mobile.action.STOP"
    const val ACTION_STATUS = "com.smarttest.mobile.action.STATUS"

    const val EXTRA_CASE_ID = "case_id"
    const val EXTRA_CASE_IDS = "case_ids"
    const val EXTRA_PARAMS = "params"
    const val EXTRA_PARAMS_B64 = "params_b64"
    const val EXTRA_SOURCE = "source"
    const val EXTRA_TRIGGER = "trigger"
    const val EXTRA_REQUEST_ID = "request_id"

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
            parameterOverrides = parseParameters(intent),
            source = intent.getStringExtra(EXTRA_SOURCE)?.trim().orEmpty().ifBlank { "adb" },
            trigger = intent.getStringExtra(EXTRA_TRIGGER)?.trim().orEmpty().ifBlank { "am start" },
            requestId = intent.getStringExtra(EXTRA_REQUEST_ID)?.trim().orEmpty().ifBlank { "manual" },
        )
    }

    fun describeIntent(intent: Intent): String {
        return buildString {
            append(intent.action ?: "NO_ACTION")
            val caseId = intent.getStringExtra(EXTRA_CASE_ID).orEmpty()
            val caseIds = intent.getStringExtra(EXTRA_CASE_IDS).orEmpty()
            val requestId = intent.getStringExtra(EXTRA_REQUEST_ID).orEmpty()
            if (caseId.isNotBlank()) append(" case_id=$caseId")
            if (caseIds.isNotBlank()) append(" case_ids=$caseIds")
            if (requestId.isNotBlank()) append(" request_id=$requestId")
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
            putExtra(EXTRA_REQUEST_ID, "example-run")
        }
    }

    private fun parseParameters(intent: Intent): Map<String, String> {
        val encoded = intent.getStringExtra(EXTRA_PARAMS_B64).orEmpty()
        if (encoded.isNotBlank()) {
            decodeBase64Parameters(encoded)?.let { return it }
        }
        val raw = intent.getStringExtra(EXTRA_PARAMS).orEmpty()
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

    private fun decodeBase64Parameters(encoded: String): Map<String, String>? {
        return runCatching {
            val normalized = encoded.padEnd(((encoded.length + 3) / 4) * 4, '=')
            val decoded = String(Base64.decode(normalized, Base64.URL_SAFE or Base64.NO_WRAP), Charsets.UTF_8)
            val json = JSONObject(decoded)
            buildMap {
                val keys = json.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    val value = json.optString(key).trim()
                    if (":" in key && value.isNotEmpty()) {
                        put(key, value)
                    }
                }
            }
        }.onFailure {
            Log.w("SmartTestCommand", "Invalid params_b64 payload", it)
        }.getOrNull()
    }
}
