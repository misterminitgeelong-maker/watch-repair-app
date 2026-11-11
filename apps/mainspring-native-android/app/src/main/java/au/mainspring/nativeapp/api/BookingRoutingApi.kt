package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Query

data class BookingRouteOption(@SerializedName("tenant_id") val id: String, @SerializedName("tenant_name") val name: String,
    @SerializedName("routing_rule") val rule: String? = null)
data class CoverageContact(@SerializedName("hq_contact") val contact: String? = null)
interface BookingRoutingApi {
    @GET("v1/shop-mobile-bookings/suggest-operator") suspend fun suggest(@Query("suburb") suburb: String, @Query("state_code") state: String): BookingRouteOption?
    @GET("v1/shop-mobile-bookings/coverage-contact") suspend fun coverage(): CoverageContact
}
