package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

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
    @SerializedName("xero_configured") val xeroConfigured: Boolean? = null,
    @SerializedName("xero_connected") val xeroConnected: Boolean? = null,
    @SerializedName("xero_connection_status") val xeroConnectionStatus: String? = null,
)

/** Read-only billing endpoints used by the native Accounts screen. */
interface AccountsApi {
    @GET("v1/billing/limits") suspend fun billingLimits(): BillingLimits
}

/** Sign-out calls carry an explicit token because the local session is already gone when they run. */
interface SignOutApi {
    @POST("v1/auth/logout") suspend fun logout(@Header("Authorization") bearer: String): Response<Unit>
    @DELETE("v1/me/devices") suspend fun unregisterDevice(@Header("Authorization") bearer: String, @Query("token") token: String): Response<Unit>
}

/** Best-effort server-side sign-out: never throws, never blocks the local sign-out. */
object SignOutClient {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun revokeInBackground(baseUrl: String, accessToken: String, deviceToken: String?) {
        scope.launch { revoke(baseUrl, accessToken, deviceToken) }
    }

    /** Removes the push device (only if one is stored), then revokes the refresh session. */
    suspend fun revoke(baseUrl: String, accessToken: String, deviceToken: String?) {
        val api = try {
            Retrofit.Builder().baseUrl(if(baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
                .client(OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(10, TimeUnit.SECONDS).build())
                .addConverterFactory(retrofit2.converter.gson.GsonConverterFactory.create()).build().create(SignOutApi::class.java)
        } catch(e: Exception) { return }
        val bearer = "Bearer $accessToken"
        if(!deviceToken.isNullOrBlank()) {
            try { api.unregisterDevice(bearer, deviceToken) } catch(e: CancellationException) { throw e } catch(_: Exception) {}
        }
        try { api.logout(bearer) } catch(e: CancellationException) { throw e } catch(_: Exception) {}
    }
}
