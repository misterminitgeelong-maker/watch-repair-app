package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import retrofit2.http.*

data class ParentShop(@SerializedName("tenant_id") val id: String, @SerializedName("tenant_slug") val slug: String,
    @SerializedName("tenant_name") val name: String, @SerializedName("shop_number") val number: String? = null,
    @SerializedName("plan_code") val plan: String, @SerializedName("network_role") val networkRole: String,
    @SerializedName("owner_email") val ownerEmail: String, val region: String? = null)
data class ShopLinkRequest(val id: String, @SerializedName("parent_account_name") val parentName: String,
    @SerializedName("tenant_name") val tenantName: String, @SerializedName("tenant_slug") val slug: String,
    val status: String, @SerializedName("created_at") val createdAt: String)
data class MyShopsSummary(@SerializedName("parent_account_id") val id: String, @SerializedName("parent_account_name") val name: String,
    @SerializedName("my_role") val role: String? = null, @SerializedName("site_count") val siteCount: Int,
    @SerializedName("pending_link_requests") val pending: List<ShopLinkRequest> = emptyList())
data class ParentShopsPage(val sites: List<ParentShop>, val total: Int)
data class ParentActivity(val id: String, @SerializedName("event_summary") val summary: String, @SerializedName("created_at") val createdAt: String)
data class ShopUsageRow(@SerializedName("tenant_name") val name: String, @SerializedName("shop_number") val number: String? = null,
    @SerializedName("accepted_bookings_count") val accepted: Int, @SerializedName("pending_count") val pending: Int)
data class ShopUsage(val month: String, @SerializedName("booking_tenant_count") val count: Int, val shops: List<ShopUsageRow>)
interface MyShopsApi {
    @GET("v1/parent-accounts/me") suspend fun summary(): MyShopsSummary
    @GET("v1/parent-accounts/me/sites") suspend fun shops(@Query("limit") limit: Int = 50, @Query("offset") offset: Int = 0, @Query("search") search: String? = null): ParentShopsPage
    @GET("v1/parent-accounts/me/activity") suspend fun activity(@Query("limit") limit: Int = 30): List<ParentActivity>
    @GET("v1/parent-accounts/me/shop-booking-usage") suspend fun usage(@Query("month") month: String): ShopUsage
    @POST("v1/parent-accounts/me/link-tenant") suspend fun link(@Body body: JsonObject): MyShopsSummary
    @POST("v1/parent-accounts/me/create-tenant") suspend fun create(@Body body: JsonObject): MyShopsSummary
    @DELETE("v1/parent-accounts/me/sites/{id}") suspend fun unlink(@Path("id") id: String): MyShopsSummary
    @GET("v1/network-link-requests") suspend fun invitations(): List<ShopLinkRequest>
    @POST("v1/network-link-requests/{id}/{action}") suspend fun invitation(@Path("id") id: String, @Path("action") action: String): ShopLinkRequest
}
