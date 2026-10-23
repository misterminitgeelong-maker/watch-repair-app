package au.mainspring.nativeapp.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
fun PhotoThumbnail(uri: String, description: String) {
    val resolver = LocalContext.current.contentResolver
    val bitmap by produceState<Bitmap?>(null, uri) {
        value = withContext(Dispatchers.IO) {
            try {
                val parsed = Uri.parse(uri)
                val bytes = resolver.openInputStream(parsed)?.use { au.mainspring.nativeapp.readPhotoBounded(it) }
                bytes?.let { au.mainspring.nativeapp.orientedPhotoBitmap(it, 600) }
            } catch (_: java.io.IOException) { null }
            catch (_: SecurityException) { null }
            catch (_: RuntimeException) { null }
        }
    }
    bitmap?.let { Image(it.asImageBitmap(), contentDescription = description,
        modifier = Modifier.fillMaxWidth().height(160.dp), contentScale = ContentScale.Fit) }
        ?: Text("Photo selected · preview unavailable")
}
