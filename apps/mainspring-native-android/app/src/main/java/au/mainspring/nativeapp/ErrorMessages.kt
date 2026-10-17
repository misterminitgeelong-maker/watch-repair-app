package au.mainspring.nativeapp
import com.google.gson.JsonParser
import retrofit2.HttpException
/** Render the current API's plain detail and validation messages without exposing HTML error pages. */
fun Exception.userMessage(): String {
 if(this is au.mainspring.nativeapp.api.SessionChangedException) return message.orEmpty()
 if(this is HttpException) {
  val detail = try {
   val raw = response()?.errorBody()?.string().orEmpty().take(16_000)
   JsonParser.parseString(raw).asJsonObject["detail"]
  } catch(_: Exception) { null }
  if(detail?.isJsonPrimitive == true && detail.asJsonPrimitive.isString) return when(val text = detail.asString) {
   "stale_write" -> "This record has changed. Refresh and review it before saving."
   else -> text.take(2000)
  }
  if(detail?.isJsonArray == true) return detail.asJsonArray.take(4).joinToString("\n") { row -> try {
   val item = row.asJsonObject; val field = item["loc"]?.asJsonArray?.lastOrNull()?.asString
   listOfNotNull(field, item["msg"]?.asString).joinToString(": ")
  } catch(_: Exception) { "Check the entered fields." } }
  return when(code()) { 401 -> "Your session has expired. Sign in again."; 403 -> "Your account cannot perform this action."; 404 -> "This record could not be found."; 429 -> "Too many requests. Try again shortly."; else -> "The service returned an error (${code()}). Try again after refreshing." }
 }
 if(this is java.io.IOException) return "Cannot reach your shop. Check your connection and try again."
 return message?.take(2000) ?: "This action could not be completed."
}
