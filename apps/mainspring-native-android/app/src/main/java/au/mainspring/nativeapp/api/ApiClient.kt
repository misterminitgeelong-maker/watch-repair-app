package au.mainspring.nativeapp.api
import au.mainspring.nativeapp.BuildConfig
import au.mainspring.nativeapp.TokenStore
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
 private val gson = GsonBuilder().setLenient().create()
 private var cached: MainspringApi? = null; private var cachedGeneration = -1L; private var cachedUrl = ""
 fun getEffectiveBaseUrl(): String {
  val raw = (TokenStore.getApiBaseUrl() ?: BuildConfig.API_BASE_URL).trim()
  return if(raw.endsWith('/')) raw else "$raw/"
 }
 private fun clientBuilder() = OkHttpClient.Builder().connectTimeout(30,TimeUnit.SECONDS).readTimeout(30,TimeUnit.SECONDS)
 private fun logging() = HttpLoggingInterceptor().apply { level = if(BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE }
 private val extras = HashMap<Class<*>, Any>(); private var extrasKey = ""
 /** Additional Retrofit service interfaces share the same authenticated client and base URL as [api]. */
 @Suppress("UNCHECKED_CAST") fun <T : Any> service(type: Class<T>): T = synchronized(this) {
  api
  val key = "${TokenStore.sessionGeneration()}|${getEffectiveBaseUrl()}"
  if(key != extrasKey) { extras.clear(); extrasKey = key }
  extras.getOrPut(type) { retrofitFor(type) } as T
 }
 private fun <T : Any> retrofitFor(type: Class<T>): T {
  val generation = TokenStore.sessionGeneration(); val url = getEffectiveBaseUrl()
  val refresh = Retrofit.Builder().baseUrl(url).client(clientBuilder().addInterceptor(logging()).build())
   .addConverterFactory(GsonConverterFactory.create(gson)).build().create(RefreshApi::class.java)
  val main = clientBuilder().addInterceptor(AuthInterceptor(generation)).addInterceptor(logging()).authenticator(TokenAuthenticator(refresh, url)).build()
  return Retrofit.Builder().baseUrl(url).client(main).addConverterFactory(ExplicitJsonBodyConverter())
   .addConverterFactory(GsonConverterFactory.create(gson)).build().create(type)
 }
 val api: MainspringApi get() = synchronized(this) {
  val generation = TokenStore.sessionGeneration(); val url = getEffectiveBaseUrl()
  if(cached != null && cachedGeneration == generation && cachedUrl == url) return@synchronized cached!!
  // Both normal requests and refresh requests keep the origin that issued this session.
  val refresh = Retrofit.Builder().baseUrl(url).client(clientBuilder().addInterceptor(logging()).build())
   .addConverterFactory(GsonConverterFactory.create(gson)).build().create(RefreshApi::class.java)
  val main = clientBuilder().addInterceptor(AuthInterceptor(generation)).addInterceptor(logging()).authenticator(TokenAuthenticator(refresh, url)).build()
  val result = Retrofit.Builder().baseUrl(url).client(main).addConverterFactory(ExplicitJsonBodyConverter())
   .addConverterFactory(GsonConverterFactory.create(gson)).build().create(MainspringApi::class.java)
  cached = result; cachedGeneration = generation; cachedUrl = url; result
 }
}
