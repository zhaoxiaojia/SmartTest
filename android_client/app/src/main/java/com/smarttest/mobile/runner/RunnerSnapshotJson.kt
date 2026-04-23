package com.smarttest.mobile.runner

import org.json.JSONArray
import org.json.JSONObject

object RunnerSnapshotJson {
    fun serialize(snapshot: RunnerSnapshot): String {
        val root = JSONObject()
        root.put("phase", snapshot.phase.name)
        root.put("isRunning", snapshot.isRunning)
        root.put("lastCommandSummary", snapshot.lastCommandSummary)
        root.put("logCount", snapshot.logLines.size)
        root.put("logLines", JSONArray(snapshot.logLines))
        root.put("runningCases", JSONArray(snapshot.runningCases.map(::runningCaseJson)))
        root.put("activeRequest", snapshot.activeRequest?.let(::requestJson) ?: JSONObject.NULL)
        root.put("report", snapshot.report?.let(::reportJson) ?: JSONObject.NULL)
        root.put("currentLoop", snapshot.currentLoop ?: JSONObject.NULL)
        root.put("totalLoops", snapshot.totalLoops ?: JSONObject.NULL)
        root.put("currentStage", snapshot.currentStage)
        return root.toString()
    }

    private fun requestJson(request: TestRunRequest): JSONObject {
        return JSONObject().apply {
            put("caseIds", JSONArray(request.caseIds))
            put("parameterOverrides", JSONObject(request.parameterOverrides))
            put("source", request.source)
            put("trigger", request.trigger)
            put("requestId", request.requestId)
        }
    }

    private fun runningCaseJson(runningCase: RunningCase): JSONObject {
        return JSONObject().apply {
            put("id", runningCase.id)
            put("title", runningCase.title)
            put("category", runningCase.category)
            put(
                "parameters",
                JSONArray(
                    runningCase.parameters.map { (key, value) ->
                        JSONObject().apply {
                            put("key", key)
                            put("value", value)
                        }
                    },
                ),
            )
        }
    }

    private fun reportJson(report: RunReport): JSONObject {
        return JSONObject().apply {
            put("batchLabel", report.batchLabel)
            put("requestId", report.requestId)
            put("totalCount", report.totalCount)
            put("successCount", report.successCount)
            put("failedCount", report.failedCount)
            put("statusText", report.statusText)
        }
    }
}
