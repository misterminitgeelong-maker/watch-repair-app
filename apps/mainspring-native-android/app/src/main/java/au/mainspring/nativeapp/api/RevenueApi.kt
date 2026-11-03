package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import com.google.gson.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** Mobile services "Revenue control" queue and follow-up. Obtain via ApiClient.service(RevenueApi::class.java). */
interface RevenueApi {
    @GET("v1/revenue-control") suspend fun revenueControl(
        @Query("state") state: String = "due",
        @Query("kind") kind: String? = null,
        @Query("owner") owner: String? = null,
        @Query("search") search: String? = null,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0,
    ): RevenueResponse
    /** Body is a JsonObject so owner / next_follow_up_at can be sent as explicit nulls. */
    @PUT("v1/revenue-control/{key}/follow-up") suspend fun saveFollowUp(@Path("key") key: String, @Body body: JsonObject): RevenueItem
}

data class RevenueItem(
    val key: String,
    val kind: String,
    @SerializedName("job_id") val jobId: String,
    @SerializedName("job_number") val jobNumber: String,
    val title: String = "",
    @SerializedName("customer_name") val customerName: String = "",
    @SerializedName("owner_name") val ownerName: String? = null,
    @SerializedName("amount_cents") val amountCents: Int? = null,
    val currency: String = "AUD",
    @SerializedName("deposit_cents") val depositCents: Int = 0,
    @SerializedName("age_days") val ageDays: Int = 0,
    @SerializedName("due_at") val dueAt: String? = null,
    val due: Boolean = false,
    val priority: String = "normal",
    @SerializedName("next_action") val nextAction: String = "",
    val note: String? = null,
    @SerializedName("owner_user_id") val ownerUserId: String? = null,
    @SerializedName("last_contact_at") val lastContactAt: String? = null,
    val version: Int = 0,
)

data class RevenueOwner(val id: String, val name: String = "")

data class RevenueBucket(
    val kind: String,
    val count: Int = 0,
    @SerializedName("due_count") val dueCount: Int = 0,
    @SerializedName("amount_cents") val amountCents: Int = 0,
    @SerializedName("unknown_amount_count") val unknownAmountCount: Int = 0,
)

data class RevenueResponse(
    val items: List<RevenueItem> = emptyList(),
    val total: Int = 0,
    val limit: Int = 50,
    val offset: Int = 0,
    val buckets: List<RevenueBucket> = emptyList(),
    val timezone: String? = null,
    val warnings: List<String> = emptyList(),
    val owners: List<RevenueOwner> = emptyList(),
)
