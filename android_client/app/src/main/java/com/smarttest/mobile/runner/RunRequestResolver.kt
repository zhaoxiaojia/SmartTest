package com.smarttest.mobile.runner

object RunRequestResolver {
    fun resolveCases(request: TestRunRequest): List<RunningCase> {
        return request.caseIds.mapNotNull { caseId ->
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
    }
}
