package au.mainspring.nativeapp.api

import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.POST

/** Synchronous refresh only — used from [TokenAuthenticator], not the main suspend API. */
interface RefreshApi {
    @POST("v1/auth/refresh")
    fun refresh(@Body body: RefreshRequest): Call<TokenResponse>
}
