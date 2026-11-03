package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

/** Customer merge, loyalty and order deletion. Obtain with `ApiClient.service(CustomerExtrasApi::class.java)`. */
interface CustomerExtrasApi {
    @POST("v1/customers/merge") suspend fun mergeCustomers(@Body body: CustomerMergeRequest): Response<Unit>
    @GET("v1/loyalty/customers/{id}") suspend fun loyaltyProfile(@Path("id") id: String): LoyaltyProfile
    @POST("v1/loyalty/customers/{id}/adjust") suspend fun adjustLoyalty(@Path("id") id: String, @Body body: LoyaltyAdjustRequest): LoyaltyProfile
    @DELETE("v1/customer-orders/{id}") suspend fun deleteCustomerOrder(@Path("id") id: String): Response<Unit>
}

data class CustomerMergeRequest(
    @SerializedName("primary_customer_id") val primaryCustomerId: String,
    @SerializedName("duplicate_customer_id") val duplicateCustomerId: String,
)
data class LoyaltyAdjustRequest(@SerializedName("points_delta") val pointsDelta: Int, val note: String)
data class LoyaltyProfile(val loyalty: LoyaltyInfo, @SerializedName("recent_ledger") val recentLedger: List<LoyaltyLedgerEntry> = emptyList())
data class LoyaltyInfo(
    @SerializedName("tier_name") val tierName: String? = null,
    @SerializedName("tier_label") val tierLabel: String? = null,
    @SerializedName("points_balance") val pointsBalance: Int = 0,
    @SerializedName("points_dollar_value") val pointsDollarValue: Double? = null,
    @SerializedName("rolling_12m_spend_cents") val rolling12mSpendCents: Long = 0,
)
data class LoyaltyLedgerEntry(
    val id: String? = null,
    @SerializedName("entry_type") val entryType: String? = null,
    @SerializedName("points_delta") val pointsDelta: Int = 0,
    val note: String? = null,
    @SerializedName("occurred_at") val occurredAt: String? = null,
)

/** Job statuses the web customer page treats as finished (CustomerDetailPage.tsx). */
val CUSTOMER_COMPLETED_STATUSES = setOf("completed", "awaiting_collection", "collected")
val CUSTOMER_NON_ACTIVE_STATUSES = CUSTOMER_COMPLETED_STATUSES + "no_go"
