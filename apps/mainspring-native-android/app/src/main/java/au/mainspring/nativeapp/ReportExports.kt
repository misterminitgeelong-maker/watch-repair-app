package au.mainspring.nativeapp

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Save the exact server export through the location chosen in Android's document picker. */
suspend fun saveReportExport(context: Context, uri: Uri, bytes: ByteArray) = withContext(Dispatchers.IO) {
    context.contentResolver.openOutputStream(uri, "wt")?.use { it.write(bytes) }
        ?: throw java.io.IOException("The chosen location cannot be written.")
}
