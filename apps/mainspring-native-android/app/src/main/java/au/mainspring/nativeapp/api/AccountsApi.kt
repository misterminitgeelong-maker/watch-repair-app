package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET

data class BillingPlanLimits(
    @SerializedName("max_users") val maxUsers: Int = 0,
    @SerializedName("max_repair_jobs") val maxRepairJobs: Int = 0,
    @SerializedName("max_shoe_jobs") val maxShoeJobs: Int = 0,
    @SerializedName("max_auto_key_jobs") val maxAutoKeyJobs: Int = 0,
)
data class BillingLimitsUsage(
    val users: Int = 0,
    @SerializedName("repair_jobs") val repairJobs: Int = 0,
    @SerializedName("shoe_jobs") val shoeJobs: Int = 0,
    @SerializedName("auto_key_jobs") val autoKeyJobs: Int = 0,
)
data class BillingLimits(
    @SerializedName("plan_code") val planCode: String,
    val limits: BillingPlanLimits = BillingPlanLimits(),
    val usage: BillingLimitsUsage = BillingLimitsUsage(),
    @SerializedName("stripe_configured") val stripeConfigured: Boolean = false,
    @SerializedName("stripe_subscription_id") val stripeSubscriptionId: String? = null,
    @SerializedName("xero_connected") val xeroConnected: Boolean? = null,
    @SerializedName("xero_connection_status") val xeroConnectionStatus: String? = null,
)

/** Read-only billing endpoints used by the native Accounts screen. */
interface AccountsApi {
    @GET("v1/billing/limits") suspend fun billingLimits(): BillingLimits
}
