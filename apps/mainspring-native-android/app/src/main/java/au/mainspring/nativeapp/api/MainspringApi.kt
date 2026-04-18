package au.mainspring.nativeapp.api

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

    @POST("v1/repair-jobs/{jobId}/status")
    suspend fun postRepairJobStatus(
        @Path("jobId") jobId: String,
        @Body body: RepairJobStatusUpdate,
    ): RepairJobRead

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

    @GET("v1/auto-key-jobs")
    suspend fun listAutoKeyJobs(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 200,
    ): List<AutoKeyJobRead>

    @GET("v1/auto-key-jobs/{jobId}")
    suspend fun getAutoKeyJob(@Path("jobId") jobId: String): AutoKeyJobRead
}
