package au.mainspring.nativeapp.api

import au.mainspring.nativeapp.BuildConfig
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    private val gson = GsonBuilder()
        .setLenient()
        .create()

    val api: MainspringApi by lazy {
        val log = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        val http = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor())
            .addInterceptor(log)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(MainspringApi::class.java)
    }
}
