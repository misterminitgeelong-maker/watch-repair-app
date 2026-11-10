package au.mainspring.nativeapp.api

import retrofit2.http.GET
import retrofit2.http.Query

/** Paginated directory contract, including the same filters as the web operational list. */
interface MobileDirectoryApi {
    @GET("v1/auto-key-jobs/page") suspend fun page(
        @Query("q") query: String? = null, @Query("directory") directory: String = "active",
        @Query("status") status: String? = null, @Query("category") category: String? = null,
        @Query("assigned_user_id") technician: String? = null, @Query("focus") focus: String? = null,
        @Query("date_field") dateField: String? = null, @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null, @Query("limit") limit: Int = 50, @Query("offset") offset: Int = 0,
    ): MobileJobPage
}
