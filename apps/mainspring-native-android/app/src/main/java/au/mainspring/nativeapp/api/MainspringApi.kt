package au.mainspring.nativeapp.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface MainspringApi {
    @POST("v1/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("v1/auth/session")
    suspend fun session(@Header("Authorization") authorization: String): SessionResponse
}
