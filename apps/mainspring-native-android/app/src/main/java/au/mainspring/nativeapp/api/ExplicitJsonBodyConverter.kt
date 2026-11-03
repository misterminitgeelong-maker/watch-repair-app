package au.mainspring.nativeapp.api
import com.google.gson.JsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Converter
import retrofit2.Retrofit
import java.lang.reflect.Type

/** Preserve explicit null fields in PATCH documents without changing nullable create defaults. */
class ExplicitJsonBodyConverter: Converter.Factory() {
 override fun requestBodyConverter(type: Type, parameterAnnotations: Array<Annotation>, methodAnnotations: Array<Annotation>, retrofit: Retrofit): Converter<*, RequestBody>? {
  if(type != JsonObject::class.java) return null
  return Converter<JsonObject, RequestBody> { it.toString().toRequestBody("application/json; charset=UTF-8".toMediaType()) }
 }
}
