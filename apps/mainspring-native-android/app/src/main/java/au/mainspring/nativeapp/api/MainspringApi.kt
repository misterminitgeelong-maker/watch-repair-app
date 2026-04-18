package au.mainspring.nativeapp.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface MainspringApi {
    @POST("v1/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("v1/auth/session")
    suspend fun session(): SessionResponse

    @GET("v1/customers")
    suspend fun listCustomers(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "full_name",
        @Query("sort_dir") sortDir: String = "asc",
        @Query("q") q: String? = null,
    ): List<CustomerRead>

    @GET("v1/customers/{id}")
    suspend fun getCustomer(@Path("id") id: String): CustomerRead

    @GET("v1/repair-jobs")
    suspend fun listRepairJobs(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "created_at",
        @Query("sort_dir") sortDir: String = "desc",
        @Query("q") q: String? = null,
    ): List<RepairJobRead>
}
