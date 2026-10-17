package au.mainspring.nativeapp
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File
/** Delete only camera files owned by this app, after every retained draft releases them. */
internal fun deleteUnusedOwnedPhoto(value: String) {
 val context = TokenStore.context() ?: return
 try {
  val uri = Uri.parse(value)
  if(uri.scheme != "content" || uri.authority != "${context.packageName}.intake" || uri.pathSegments.size != 2 || uri.pathSegments[0] != "intake_photos") return
  if(TokenStore.referencesPhoto(value)) return
  val directory = File(context.filesDir, "intake-photos").canonicalFile
  val file = File(directory, uri.pathSegments.last()).canonicalFile
  if(file.parentFile == directory && file.isFile) file.delete()
 } catch(_: Exception) { /* A retained file can be cleaned at a later explicit draft finish/sign-out. */ }
}
internal fun cleanupUnusedOwnedPhotos() {
 val context = TokenStore.context() ?: return
 try {
  val directory = File(context.filesDir, "intake-photos").canonicalFile
  directory.listFiles()?.filter { it.isFile && it.canonicalFile.parentFile == directory }?.forEach {
   deleteUnusedOwnedPhoto(FileProvider.getUriForFile(context, "${context.packageName}.intake", it).toString())
  }
 } catch(_: Exception) { }
}
