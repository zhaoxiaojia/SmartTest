package com.smarttest.mobile.logging

import org.junit.Assert.assertEquals
import org.junit.Test

class SmartTestLogTest {
    @Test
    fun formatsSharedProtocolAndIdentities() {
        assertEquals(
            "2026-08-25T10:00:00+08:00 [mobile] [android] [WARNING] [Runner] stopped request_id=req-1 case_nodeid=case-1 step_id=step-1",
            SmartTestLog.format(
                "2026-08-25T10:00:00+08:00", "WARNING", "Runner", "stopped",
                requestId = "req-1", caseNodeid = "case-1", stepId = "step-1",
            ),
        )
    }
}
