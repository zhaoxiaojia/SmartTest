package com.smarttest.mobile.runner

import android.content.Context
import java.io.File

object SmartTestRunSnapshotFile {
    private const val FILE_NAME = "runner_snapshot.json"

    fun resolve(context: Context): File = File(context.filesDir, FILE_NAME)
}
