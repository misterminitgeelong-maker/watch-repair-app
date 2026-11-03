package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

/** GET/PATCH /v1/settings/shop-identity (manager+). */
data class ShopIdentity(
    val name: String = "",
    val abn: String? = null,
    @SerializedName("shop_phone") val shopPhone: String? = null,
    @SerializedName("shop_email") val shopEmail: String? = null,
    @SerializedName("payment_instructions") val paymentInstructions: String? = null,
    @SerializedName("business_address") val businessAddress: String? = null,
    @SerializedName("logo_url") val logoUrl: String? = null,
    @SerializedName("brand_color") val brandColor: String? = null,
    @SerializedName("shop_number") val shopNumber: String? = null,
    val region: String = "AU",
    @SerializedName("default_currency") val defaultCurrency: String = "AUD",
    val timezone: String = "Australia/Melbourne",
)

/** Only the fields the app edits. The server treats a blank string as "clear", so blanks are sent as-is. */
data class ShopIdentityUpdate(
    val abn: String? = null,
    @SerializedName("shop_phone") val shopPhone: String? = null,
    @SerializedName("shop_email") val shopEmail: String? = null,
    @SerializedName("payment_instructions") val paymentInstructions: String? = null,
    @SerializedName("logo_url") val logoUrl: String? = null,
    @SerializedName("brand_color") val brandColor: String? = null,
)

data class NotificationPrefs(
    @SerializedName("email_quote_approved") val quoteApproved: Boolean = false,
    @SerializedName("email_invoice_paid") val invoicePaid: Boolean = false,
    @SerializedName("email_sms_reply") val smsReply: Boolean = false,
    @SerializedName("email_daily_digest") val dailyDigest: Boolean = false,
    @SerializedName("email_weekly_sales_report") val weeklySales: Boolean = false,
    @SerializedName("email_monthly_sales_report") val monthlySales: Boolean = false,
    @SerializedName("last_weekly_sales_report_sent_at") val lastWeeklySentAt: String? = null,
    @SerializedName("last_monthly_sales_report_sent_at") val lastMonthlySentAt: String? = null,
)

data class IntegrationHealth(
    @SerializedName("twilio_configured") val twilioConfigured: Boolean = false,
    @SerializedName("last_sms_sent_at") val lastSmsSentAt: String? = null,
    @SerializedName("last_sms_failed_at") val lastSmsFailedAt: String? = null,
    @SerializedName("stripe_configured") val stripeConfigured: Boolean = false,
    @SerializedName("stripe_connect_ready") val stripeConnectReady: Boolean? = null,
    @SerializedName("sendgrid_configured") val sendgridConfigured: Boolean = false,
    @SerializedName("attachment_backend") val attachmentBackend: String = "",
)

data class CategorySales(
    val jobs: Int = 0,
    @SerializedName("billed_cents") val billedCents: Long = 0,
    @SerializedName("revenue_cents") val revenueCents: Long = 0,
    @SerializedName("cost_cents") val costCents: Long = 0,
    @SerializedName("outstanding_cents") val outstandingCents: Long = 0,
)

data class CategorySummary(val watch: CategorySales? = null, val shoe: CategorySales? = null, val mobile: CategorySales? = null)

data class ActivityEvent(
    val id: String = "",
    @SerializedName("actor_email") val actorEmail: String? = null,
    @SerializedName("entity_type") val entityType: String = "",
    @SerializedName("event_type") val eventType: String = "",
    @SerializedName("event_summary") val summary: String = "",
    @SerializedName("created_at") val createdAt: String = "",
)

data class CustomerOrderImportResult(
    @SerializedName("dry_run") val dryRun: Boolean = true,
    @SerializedName("total_rows") val totalRows: Int = 0,
    val imported: Int = 0,
    val skipped: Int = 0,
    @SerializedName("skipped_reasons") val skippedReasons: Map<String, Int>? = null,
)

/** Owner/manager admin endpoints that sit outside the day-to-day job flow. */
interface OwnerAdminApi {
    @GET("v1/settings/shop-identity") suspend fun shopIdentity(): ShopIdentity
    @PATCH("v1/settings/shop-identity") suspend fun updateShopIdentity(@Body body: ShopIdentityUpdate): ShopIdentity
    @GET("v1/me/notification-preferences") suspend fun notificationPrefs(): NotificationPrefs
    @PATCH("v1/me/notification-preferences") suspend fun updateNotificationPrefs(@Body body: com.google.gson.JsonObject): NotificationPrefs
    @GET("v1/tenant/integration-health") suspend fun integrationHealth(): IntegrationHealth
    @GET("v1/reports/category-summary") suspend fun categorySummary(@Query("period") period: String, @Query("reference_date") referenceDate: String): CategorySummary
    @Streaming @GET("v1/reports/export/sales") suspend fun exportSales(@Query("category") category: String, @Query("period") period: String, @Query("reference_date") referenceDate: String): ResponseBody
    @GET("v1/reports/activity") suspend fun activity(@Query("limit") limit: Int = 50): List<ActivityEvent>
    @DELETE("v1/users/{id}") suspend fun deleteTeamUser(@Path("id") id: String): Response<Unit>

    @Multipart @POST("v1/customer-orders/import/sheets")
    suspend fun orderImportSheets(@Part file: MultipartBody.Part): List<String>
    @Multipart @POST("v1/customer-orders/import")
    suspend fun importCustomerOrders(@Part file: MultipartBody.Part, @Query("dry_run") dryRun: Boolean, @Query("sheet_name") sheetName: String? = null): CustomerOrderImportResult
}
