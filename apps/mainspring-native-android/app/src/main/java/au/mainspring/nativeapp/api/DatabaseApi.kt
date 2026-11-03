package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Query
import retrofit2.http.Streaming

data class GstCategory(
    @SerializedName("invoice_count") val invoiceCount: Int = 0,
    @SerializedName("subtotal_cents") val subtotalCents: Long = 0,
    @SerializedName("gst_cents") val gstCents: Long = 0,
    @SerializedName("total_cents") val totalCents: Long = 0,
)

data class GstSummaryResponse(
    val watch: GstCategory? = null,
    val mobile: GstCategory? = null,
    val combined: GstCategory? = null,
)

/** Result of POST /v1/import/csv. The server reports aggregate skip reasons, not one entry per row. */
data class CsvImportResponse(
    @SerializedName("import_id") val importId: String? = null,
    val imported: Int = 0,
    val skipped: Int = 0,
    @SerializedName("customers_created") val customersCreated: Int = 0,
    @SerializedName("total_rows") val totalRows: Int = 0,
    @SerializedName("skipped_reasons") val skippedReasons: Map<String, Int>? = null,
    @SerializedName("dry_run") val dryRun: Boolean = false,
    @SerializedName("duplicate_customer_rows_in_file") val duplicateCustomerRows: Int? = null,
    @SerializedName("source_sheet") val sourceSheet: String? = null,
    @SerializedName("import_target") val importTarget: String? = null,
)

/** Database page endpoints: CSV exports, my-data JSON, GST summary and CSV import. */
interface DatabaseApi {
    @Streaming @GET("v1/reports/export/jobs") suspend fun exportJobs(): ResponseBody
    @Streaming @GET("v1/reports/export/customers") suspend fun exportCustomers(): ResponseBody
    @Streaming @GET("v1/reports/export/invoices") suspend fun exportInvoices(): ResponseBody
    @Streaming @GET("v1/auth/export-my-data") suspend fun exportMyData(): ResponseBody
    @GET("v1/reports/gst-summary")
    suspend fun getGstSummary(@Query("period") period: String, @Query("reference_date") referenceDate: String): GstSummaryResponse

    @Multipart @POST("v1/import/csv")
    suspend fun importCsv(
        @Part file: MultipartBody.Part,
        @Query("import_target") importTarget: String,
        @Query("dry_run") dryRun: Boolean,
        @Query("sheet_name") sheetName: String? = null,
    ): CsvImportResponse
}
