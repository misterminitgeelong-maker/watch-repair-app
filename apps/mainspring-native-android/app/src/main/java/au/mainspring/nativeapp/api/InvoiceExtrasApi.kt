package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** Mobile-services (auto key) invoice row as returned by the tenant-wide list; mirrors web `AutoKeyInvoice`. */
data class MobileListedInvoice(
    val id: String,
    @SerializedName("auto_key_job_id") val jobId: String,
    @SerializedName("invoice_number") val number: String,
    val status: String,
    @SerializedName("total_cents") val totalCents: Int = 0,
    val currency: String = "AUD",
    @SerializedName("created_at") val createdAt: String = "",
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("job_number") val jobNumber: String? = null,
)

/** Xero / online-payment fields of a watch invoice (read-only). */
data class InvoiceXeroInfo(
    @SerializedName("xero_invoice_id") val xeroInvoiceId: String? = null,
    @SerializedName("xero_sync_status") val syncStatus: String? = null,
    @SerializedName("xero_sync_error") val syncError: String? = null,
    @SerializedName("xero_synced_at") val syncedAt: String? = null,
    @SerializedName("xero_online_invoice_url") val onlineUrl: String? = null,
)

data class InvoiceXeroEnvelope(val invoice: InvoiceXeroInfo? = null)

interface InvoiceExtrasApi {
    @GET("v1/auto-key-jobs/invoices")
    suspend fun listAllMobileInvoices(@Query("limit") limit: Int = 500, @Query("offset") offset: Int = 0): List<MobileListedInvoice>

    @GET("v1/invoices/{invoiceId}")
    suspend fun invoiceXero(@Path("invoiceId") invoiceId: String): InvoiceXeroEnvelope

    /** Manager+ only. Clears the failed state and re-runs the sync; returns the flat invoice with refreshed xero_* fields. */
    @POST("v1/invoices/{invoiceId}/xero/retry")
    suspend fun retryXero(@Path("invoiceId") invoiceId: String): InvoiceXeroInfo
}
