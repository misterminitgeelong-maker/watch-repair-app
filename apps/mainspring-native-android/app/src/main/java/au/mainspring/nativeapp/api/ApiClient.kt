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

    private val logging: HttpLoggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
    }

    private val plainClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    private val refreshRetrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(plainClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
    }

    private val refreshApi: RefreshApi by lazy {
        refreshRetrofit.create(RefreshApi::class.java)
    }

    private val mainClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor())
            .addInterceptor(logging)
            .authenticator(TokenAuthenticator(refreshApi))
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    val api: MainspringApi by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(mainClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(MainspringApi::class.java)
    }
}
