package com.smarttest.mobile.runner.device.log

import com.smarttest.mobile.runner.device.model.CommandRecord
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

interface CommandRecorder {
    val records: StateFlow<List<CommandRecord>>

    fun record(record: CommandRecord)

    fun recent(limit: Int = 50): List<CommandRecord>
}

class InMemoryCommandRecorder : CommandRecorder {
    private val mutableRecords = MutableStateFlow<List<CommandRecord>>(emptyList())

    override val records: StateFlow<List<CommandRecord>>
        get() = mutableRecords.asStateFlow()

    override fun record(record: CommandRecord) {
        mutableRecords.update { current -> (current + record).takeLast(MAX_RECORDS) }
    }

    override fun recent(limit: Int): List<CommandRecord> {
        return mutableRecords.value.takeLast(limit.coerceAtLeast(1))
    }

    private companion object {
        private const val MAX_RECORDS = 500
    }
}
