package au.mainspring.nativeapp.api

import retrofit2.http.GET

data class InboxCountResponse(val count: Int = 0)

/** Dashboard-only endpoints kept out of MainspringApi. */
interface DashboardExtrasApi {
    @GET("v1/inbox/count")
    suspend fun getInboxCount(): InboxCountResponse
}
