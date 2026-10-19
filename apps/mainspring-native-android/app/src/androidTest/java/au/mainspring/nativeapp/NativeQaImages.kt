package au.mainspring.nativeapp
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.test.platform.app.InstrumentationRegistry
import android.graphics.Bitmap
/** Save emulator QA captures outside the test app, which Gradle uninstalls after instrumentation. */
fun saveNativeQaImage(node: SemanticsNodeInteraction, name: String) {
 if(android.os.Build.VERSION.SDK_INT < 29) return
 val context = InstrumentationRegistry.getInstrumentation().targetContext
 val values = android.content.ContentValues().apply {
  put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, name); put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/png")
  put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, "Pictures/Mainspring-native-QA"); put(android.provider.MediaStore.Images.Media.IS_PENDING, 1)
 }
 val uri = context.contentResolver.insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)!!
 context.contentResolver.openOutputStream(uri)!!.use { node.captureToImage().asAndroidBitmap().compress(Bitmap.CompressFormat.PNG, 100, it) }
 context.contentResolver.update(uri, android.content.ContentValues().apply { put(android.provider.MediaStore.Images.Media.IS_PENDING, 0) }, null, null)
}
