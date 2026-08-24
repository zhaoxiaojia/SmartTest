package com.smarttest.mobile.runner

import android.content.Context
import java.io.File

object SmartTestPublicSnapshotFile {
    private const val FILE_NAME = "runner_snapshot.json"

    fun resolve(context: Context): File? {
        val externalDir = context.getExternalFilesDir(null) ?: return null
        return File(externalDir, FILE_NAME)
    }
}
