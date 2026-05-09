package com.smarttest.mobile.runner

object RunRequestResolver {
    fun resolveCases(request: TestRunRequest): List<RunningCase> {
        return request.caseIds.map { caseId ->
            val parameterValues = request.parameterOverrides
                .mapNotNull { (key, value) ->
                    val prefix = "$caseId:"
                    if (key.startsWith(prefix)) key.removePrefix(prefix) to value else null
                }
                .toMap()
            RunningCase(
                id = caseId,
                title = caseId,
                category = "",
                parameters = parameterValues.map { (id, value) -> id to value },
                parameterValues = parameterValues,
            )
        }
    }
}
