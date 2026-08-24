package com.smarttest.mobile.runner

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.ParcelFileDescriptor

class SmartTestStatusProvider : ContentProvider() {
    override fun onCreate(): Boolean = true

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor? = null

    override fun getType(uri: Uri): String {
        requireSnapshotUri(uri)
        return "application/json"
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0

    override fun update(
        uri: Uri,
        values: ContentValues?,
        selection: String?,
        selectionArgs: Array<out String>?,
    ): Int = 0

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        requireSnapshotUri(uri)
        val snapshotJson = RunnerSnapshotJson.serialize(SmartTestRunStore.state.value)
        val pipe = ParcelFileDescriptor.createPipe()
        val readSide = pipe[0]
        val writeSide = pipe[1]
        ParcelFileDescriptor.AutoCloseOutputStream(writeSide).use { output ->
            output.write(snapshotJson.toByteArray(Charsets.UTF_8))
            output.flush()
        }
        return readSide
    }

    private fun requireSnapshotUri(uri: Uri) {
        require(uri.authority == AUTHORITY) { "Unsupported authority: ${uri.authority}" }
        val path = uri.path?.trim('/').orEmpty()
        require(path == PATH_SNAPSHOT) { "Unsupported path: $path" }
    }

    companion object {
        const val AUTHORITY = "com.smarttest.mobile.status"
        private const val PATH_SNAPSHOT = "snapshot"
    }
}
