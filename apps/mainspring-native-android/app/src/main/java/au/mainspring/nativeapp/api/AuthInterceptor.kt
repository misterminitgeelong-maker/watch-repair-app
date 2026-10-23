package au.mainspring.nativeapp.api
import au.mainspring.nativeapp.TokenStore
import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

data class SessionGenerationTag(val generation: Long)
class SessionChangedException: IOException("Your sign-in changed. Reopen this screen under the current account.")
/** A service instance belongs to one sign-in; token rotation within that sign-in remains supported. */
class AuthInterceptor(private val generation: Long): Interceptor {
 override fun intercept(chain: Interceptor.Chain): Response {
  val snapshot = TokenStore.sessionSnapshot()
  if(snapshot.generation != generation) throw SessionChangedException()
  val request = chain.request(); val path = request.url.encodedPath
  val public = path.endsWith("/v1/auth/login") || path.endsWith("/v1/auth/multi-site-login")
  val builder = request.newBuilder().tag(SessionGenerationTag::class.java, SessionGenerationTag(generation))
  if(!public && snapshot.access != null) builder.header("Authorization", "Bearer ${snapshot.access}")
  return chain.proceed(builder.build())
 }
}
