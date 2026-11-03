package au.mainspring.nativeapp
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import android.net.Uri
import java.io.ByteArrayOutputStream

internal fun orientedPhotoBitmap(bytes: ByteArray, maxDimension: Int): Bitmap {
 val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
 BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
 require(bounds.outWidth > 0 && bounds.outHeight > 0) { "This file is not a readable photo." }
 var sample = 1
 while(bounds.outWidth / sample > maxDimension * 2 || bounds.outHeight / sample > maxDimension * 2) sample *= 2
 val decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample }) ?: error("Could not read photo.")
 val orientation = try { ExifInterface(bytes.inputStream()).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL) } catch(_: Exception) { ExifInterface.ORIENTATION_NORMAL }
 val transform = Matrix().apply { when(orientation) {
  ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> setScale(-1f, 1f)
  ExifInterface.ORIENTATION_ROTATE_180 -> setRotate(180f)
  ExifInterface.ORIENTATION_FLIP_VERTICAL -> setScale(1f, -1f)
  ExifInterface.ORIENTATION_TRANSPOSE -> { setRotate(90f); postScale(-1f, 1f) }
  ExifInterface.ORIENTATION_ROTATE_90 -> setRotate(90f)
  ExifInterface.ORIENTATION_TRANSVERSE -> { setRotate(-90f); postScale(-1f, 1f) }
  ExifInterface.ORIENTATION_ROTATE_270 -> setRotate(-90f)
 } }
 val rotated = if(transform.isIdentity) decoded else Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height, transform, true).also { if(it !== decoded) decoded.recycle() }
 val ratio = minOf(1.0, maxDimension.toDouble() / maxOf(rotated.width, rotated.height))
 return if(ratio == 1.0) rotated else Bitmap.createScaledBitmap(rotated, maxOf(1, (rotated.width * ratio).toInt()), maxOf(1, (rotated.height * ratio).toInt()), true).also { if(it !== rotated) rotated.recycle() }
}
internal fun preparedIntakePhoto(context: Context, uri: Uri): ByteArray {
 val raw = context.contentResolver.openInputStream(uri)?.use { readPhotoBounded(it) } ?: error("Photo unavailable. Reselect it.")
 val bitmap = orientedPhotoBitmap(raw, 2000)
 return try { ByteArrayOutputStream().use { output -> require(bitmap.compress(Bitmap.CompressFormat.JPEG, 85, output)) { "Could not prepare photo." }; output.toByteArray() } } finally { bitmap.recycle() }
}
