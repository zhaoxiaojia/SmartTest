package com.smarttest.mobile.logging

import android.util.Log
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

object SmartTestLog {
    internal fun format(timestamp: String, level: String, tag: String, message: String,
                        domain: String = "android", requestId: String = "", caseNodeid: String = "", stepId: String = ""): String {
        val identities = listOf("request_id" to requestId, "case_nodeid" to caseNodeid, "step_id" to stepId)
            .filter { it.second.isNotBlank() }.joinToString(" ") { "${it.first}=${it.second}" }
        val body = if (identities.isEmpty()) message else "$message $identities"
        return "$timestamp [mobile] [$domain] [$level] [$tag] $body"
    }

    private fun write(level: String, tag: String, message: String, error: Throwable? = null,
                      domain: String = "android", requestId: String = "", caseNodeid: String = "", stepId: String = "") {
        val line = format(OffsetDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME), level, tag, message, domain, requestId, caseNodeid, stepId)
        when (level) {
            "ERROR", "CRITICAL" -> Log.e(tag, line, error)
            "WARNING" -> Log.w(tag, line, error)
            "DEBUG" -> Log.d(tag, line, error)
            else -> Log.i(tag, line, error)
        }
    }

    fun info(tag: String, message: String) = write("INFO", tag, message)
    fun warning(tag: String, message: String, error: Throwable? = null) = write("WARNING", tag, message, error)
    fun error(tag: String, message: String, error: Throwable? = null) = write("ERROR", tag, message, error)
    fun debug(tag: String, message: String) = write("DEBUG", tag, message)
}
