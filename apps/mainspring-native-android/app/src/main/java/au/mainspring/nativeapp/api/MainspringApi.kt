package au.mainspring.nativeapp.api

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface MainspringApi {
    @POST("v1/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("v1/auth/session")
    suspend fun session(): SessionResponse

    @GET("v1/customers")
    suspend fun listCustomers(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "full_name",
        @Query("sort_dir") sortDir: String = "asc",
        @Query("q") q: String? = null,
    ): List<CustomerRead>

    @GET("v1/customers/{id}")
    suspend fun getCustomer(@Path("id") id: String): CustomerRead

    @GET("v1/repair-jobs")
    suspend fun listRepairJobs(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "created_at",
        @Query("sort_dir") sortDir: String = "desc",
        @Query("q") q: String? = null,
    ): List<RepairJobRead>

    @GET("v1/repair-jobs/{jobId}")
    suspend fun getRepairJob(@Path("jobId") jobId: String): RepairJobRead

    @GET("v1/repair-jobs/{jobId}/status-history")
    suspend fun getRepairJobStatusHistory(@Path("jobId") jobId: String): List<JobStatusHistoryRead>

    @GET("v1/repair-jobs/{jobId}/sms-log")
    suspend fun getRepairJobSmsLog(@Path("jobId") jobId: String): List<SmsLogRead>

    @POST("v1/repair-jobs/{jobId}/status")
    suspend fun postRepairJobStatus(
        @Path("jobId") jobId: String,
        @Body body: RepairJobStatusUpdate,
    ): RepairJobRead

    @POST("v1/repair-jobs/{jobId}/note")
    suspend fun postRepairJobNote(
        @Path("jobId") jobId: String,
        @Body body: JobNotePayload,
    ): Response<ResponseBody>

    @POST("v1/repair-jobs/{jobId}/claim")
    suspend fun postRepairJobClaim(@Path("jobId") jobId: String): RepairJobRead

    @POST("v1/repair-jobs/{jobId}/release")
    suspend fun postRepairJobRelease(@Path("jobId") jobId: String): RepairJobRead

    @GET("v1/attachments")
    suspend fun listAttachments(
        @Query("repair_job_id") repairJobId: String,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0,
    ): List<AttachmentRead>

    @GET("v1/attachments/download-link/{storage_key}")
    suspend fun getAttachmentDownloadLink(
        @Path("storage_key") storageKey: String,
    ): AttachmentDownloadLinkResponse

    @GET("v1/quotes")
    suspend fun listQuotes(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "created_at",
        @Query("sort_dir") sortDir: String = "desc",
        @Query("status") status: String? = null,
    ): List<QuoteRead>

    @GET("v1/quotes/{quoteId}/line-items")
    suspend fun getQuoteLineItems(@Path("quoteId") quoteId: String): List<QuoteLineItemRead>

    @POST("v1/quotes/{quoteId}/send")
    suspend fun postQuoteSend(@Path("quoteId") quoteId: String): QuoteSendResponse

    @GET("v1/invoices")
    suspend fun listInvoices(): List<InvoiceRead>

    @GET("v1/invoices/{invoiceId}")
    suspend fun getInvoice(@Path("invoiceId") invoiceId: String): InvoiceWithPayments

    @GET("v1/inbox")
    suspend fun listInbox(
        @Query("limit") limit: Int = 80,
        @Query("offset") offset: Int = 0,
    ): List<TenantEventLogRead>

    @GET("v1/shoe-repair-jobs")
    suspend fun listShoeRepairJobs(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 200,
    ): List<ShoeRepairJobRead>

    @GET("v1/shoe-repair-jobs/{jobId}")
    suspend fun getShoeRepairJob(@Path("jobId") jobId: String): ShoeRepairJobRead

    @GET("v1/shoe-repair-jobs/{jobId}/status-history")
    suspend fun getShoeRepairJobStatusHistory(@Path("jobId") jobId: String): List<ShoeJobStatusHistoryRead>

    @POST("v1/shoe-repair-jobs/{jobId}/status")
    suspend fun postShoeRepairJobStatus(
        @Path("jobId") jobId: String,
        @Body body: RepairJobStatusUpdate,
    ): ShoeRepairJobRead

    @POST("v1/shoe-repair-jobs/{jobId}/note")
    suspend fun postShoeRepairJobNote(
        @Path("jobId") jobId: String,
        @Body body: JobNotePayload,
    ): Response<ResponseBody>

    @GET("v1/auto-key-jobs")
    suspend fun listAutoKeyJobs(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 200,
    ): List<AutoKeyJobRead>

    @GET("v1/auto-key-jobs/{jobId}")
    suspend fun getAutoKeyJob(@Path("jobId") jobId: String): AutoKeyJobRead

    @POST("v1/auto-key-jobs/{jobId}/status")
    suspend fun postAutoKeyJobStatus(
        @Path("jobId") jobId: String,
        @Body body: RepairJobStatusUpdate,
    ): AutoKeyJobRead
}
