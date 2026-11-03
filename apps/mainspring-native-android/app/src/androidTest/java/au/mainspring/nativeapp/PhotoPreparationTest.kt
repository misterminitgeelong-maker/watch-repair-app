package au.mainspring.nativeapp
import android.graphics.Bitmap
import androidx.exifinterface.media.ExifInterface
import androidx.test.platform.app.InstrumentationRegistry
import java.io.ByteArrayOutputStream
import java.io.File
import org.junit.*
class PhotoPreparationTest {
 @Test fun cameraExifRotationIsAppliedBeforeUpload() {
  val context = InstrumentationRegistry.getInstrumentation().targetContext
  val file = File.createTempFile("orientation", ".jpg", context.cacheDir)
  try {
   val bitmap = Bitmap.createBitmap(40, 20, Bitmap.Config.ARGB_8888)
   file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it) }; bitmap.recycle()
   ExifInterface(file.absolutePath).apply { setAttribute(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_ROTATE_90.toString()); saveAttributes() }
   val rotated = orientedPhotoBitmap(file.readBytes(), 2000)
   Assert.assertEquals(20, rotated.width); Assert.assertEquals(40, rotated.height); rotated.recycle()
  } finally { file.delete() }
 }
 @Test fun oversizedImageIsResizedWithoutChangingAspectRatio() {
  val bitmap = Bitmap.createBitmap(2400, 600, Bitmap.Config.ARGB_8888)
  val bytes = ByteArrayOutputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it); it.toByteArray() }; bitmap.recycle()
  val resized = orientedPhotoBitmap(bytes, 2000)
  Assert.assertEquals(2000, resized.width); Assert.assertEquals(500, resized.height); resized.recycle()
 }
 @Test fun nonImageIsRejectedBeforeUpload() {
  try { orientedPhotoBitmap("invalid image".toByteArray(), 2000); Assert.fail("Invalid bytes accepted") }
  catch(_: IllegalArgumentException) { }
 }
 @Test fun cameraCleanupPreservesOtherDraftReferencesAndExternalFiles() {
  val context = InstrumentationRegistry.getInstrumentation().targetContext
  TokenStore.init(context); TokenStore.clear(); TokenStore.setDraftScope("photo-test", "user")
  val folder = File(context.filesDir, "intake-photos").apply { mkdirs() }
  val owned = File.createTempFile("retained-", ".jpg", folder)
  val outside = File.createTempFile("outside-", ".jpg", context.cacheDir)
  try {
   val uri = androidx.core.content.FileProvider.getUriForFile(context, "${context.packageName}.intake", owned).toString()
   TokenStore.saveShoeDraft(com.google.gson.Gson().toJson(mapOf("pair.0.photo" to uri)))
   deleteUnusedOwnedPhoto(uri); Assert.assertTrue(owned.exists())
   TokenStore.clearShoeDraft(); deleteUnusedOwnedPhoto(uri); Assert.assertFalse(owned.exists())
   deleteUnusedOwnedPhoto(android.net.Uri.fromFile(outside).toString()); Assert.assertTrue(outside.exists())
  } finally { owned.delete(); outside.delete(); TokenStore.clear() }
 }
}
