package au.mainspring.nativeapp.api

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface MainspringApi {
    /** Registers this phone's push token for the signed-in user (idempotent; the token moves to whoever registered it last). */
    @POST("v1/me/devices") suspend fun registerDevice(@Body body: DeviceRegisterBody): Response<Unit>

    @GET("v1/stock/items") suspend fun stockItems(@Query("search") search: String? = null, @Query("group_code") group: String? = null,
        @Query("hide_zero_stock") hideZero: Boolean = false, @Query("limit") limit: Int = 100, @Query("offset") offset: Int = 0): StockPage
    @GET("v1/reports/period-summary") suspend fun periodReport(@Query("period") period: String, @Query("reference_date") referenceDate: String): PeriodReport
    @retrofit2.http.Streaming @GET("v1/reports/export/period-summary") suspend fun exportPeriodReport(@Query("period") period: String, @Query("reference_date") referenceDate: String): ResponseBody
    @POST("v1/auth/multi-site-login") suspend fun multiSiteLogin(@Body body: MultiSiteLoginRequest): TokenResponse
    @retrofit2.http.PATCH("v1/auth/session/site") suspend fun switchSite(@Body body: SiteSwitchRequest): TokenResponse
    @POST("v1/auto-key-jobs/{id}/arrival-sms") suspend fun arrivalSms(@Path("id") id: String, @Body body: ArrivalSmsRequest): ArrivalSmsResponse
    @retrofit2.http.Multipart @POST("v1/attachments") suspend fun uploadJobPhoto(
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part,
        @Query("repair_job_id") watchId: String? = null,
        @Query("shoe_repair_job_id") shoeId: String? = null,
        @Query("auto_key_job_id") mobileId: String? = null,
        @Query("label") label: String = "job_photo"): AttachmentRead
    @GET("v1/reports/auto-key/commission") suspend fun mobileCommission(@Query("date_from") from: String, @Query("date_to") to: String): com.google.gson.JsonObject
    @POST("v1/users") suspend fun createTeamUser(@Body body: com.google.gson.JsonObject): TeamUser
    @retrofit2.http.PATCH("v1/users/{id}") suspend fun updateTeamUser(@Path("id") id: String,@Body body: com.google.gson.JsonObject): TeamUser
    @GET("v1/vehicle-key-specs/job-context") suspend fun vehicleJobContext(@Query("make") make: String?,@Query("model") model: String?,@Query("year") year: Int?,@Query("job_type") type: String?,@Query("blade_code") blade: String?): com.google.gson.JsonObject
    @GET("v1/users") suspend fun teamUsers(): List<TeamUser>
    @GET("v1/pool")
    suspend fun listDispatchPool(): List<DispatchPoolJob>

    @POST("v1/pool/{id}/claim")
    suspend fun claimDispatchJob(@Path("id") id: String): DispatchClaim
    @GET("v1/mobile-services-pricing/meta") suspend fun pricingMeta(): PricingMeta
    @GET("v1/mobile-services-pricing/oem-makes") suspend fun pricingMakes(): List<String>
    @GET("v1/mobile-services-pricing/oem-keys") suspend fun pricingKeys(@Query("make") make: String): List<PricingRow>
    @GET("v1/mobile-services-pricing/services") suspend fun pricingServices(): List<PricingRow>
    @GET("v1/mobile-services-pricing/garage") suspend fun pricingGarage(): List<PricingRow>
    @retrofit2.http.PATCH("v1/repair-jobs/{id}") suspend fun updateCounterWatch(@Path("id") id: String, @Body fields: com.google.gson.JsonObject): RepairJobRead
    @retrofit2.http.PATCH("v1/shoe-repair-jobs/{id}") suspend fun updateCounterShoe(@Path("id") id: String, @Body fields: com.google.gson.JsonObject): ShoeRepairJobRead
    @GET("v1/work-logs") suspend fun workLogs(@Query("repair_job_id") jobId: String): List<WorkLogRead>
    @POST("v1/work-logs") suspend fun createWorkLog(@Body body: WorkLogCreate): WorkLogRead
    @GET("v1/shop-mobile-bookings") suspend fun bookingRequests(@Query("offset") offset: Int = 0, @Query("limit") limit: Int = 100): BookingPage
    @GET("v1/shop-mobile-bookings/operators") suspend fun bookingOperators(): List<BookingOperator>
    @POST("v1/shop-mobile-bookings") suspend fun createBookingRequest(@Body fields: com.google.gson.JsonObject): BookingRequest
    @POST("v1/shop-mobile-bookings/{id}/{action}") suspend fun bookingAction(@Path("id") id: String, @Path("action") action: String, @Body fields: com.google.gson.JsonObject): BookingRequest
    @GET("v1/prospect-leads") suspend fun prospectLeads(): List<ProspectLead>
    @POST("v1/prospect-leads") suspend fun saveProspect(@Body body: ProspectSave): ProspectLead
    @retrofit2.http.PATCH("v1/prospect-leads/{id}") suspend fun updateProspect(@Path("id") id: String, @Body body: com.google.gson.JsonObject): ProspectLead
    @POST("v1/prospect-leads/{id}/advance") suspend fun advanceProspect(@Path("id") id: String, @Body body: com.google.gson.JsonObject): ProspectLead
    @retrofit2.http.DELETE("v1/prospect-leads/{id}") suspend fun deleteProspect(@Path("id") id: String): okhttp3.ResponseBody
    @GET("v1/prospects/contact-details") suspend fun prospectContactDetails(@Query("place_id") placeId: String): ProspectContact
    @GET("v1/prospects/collector-status") suspend fun prospectCollectorStatus(): ProspectCollectorStatus
    @GET("v1/prospects/categories") suspend fun prospectCategories(): ProspectCategories
    @GET("v1/prospects/search") suspend fun prospectSearch(@Query("category") category: String, @Query("state") state: String, @Query("suburbs") suburbs: String? = null, @Query("live") live: Boolean = false): ProspectResults
    @GET("v1/toolkit/catalog") suspend fun toolkitCatalog(): ToolkitCatalog
    @GET("v1/toolkit/my-selection") suspend fun toolkitSelection(): ToolSelection
    @retrofit2.http.PUT("v1/toolkit/my-selection") suspend fun saveToolkit(@Body body: ToolSelection): ToolSelection
    @POST("v1/toolkit/recommend") suspend fun toolkitRecommend(@Body body: ToolRecommend): ToolReadiness
    @GET("v1/auto-key-jobs/page") suspend fun mobileJobPage(@Query("q") query: String? = null,
        @Query("directory") directory: String = "active", @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0, @Query("focus") focus: String? = null,
        @Query("date_field") dateField: String? = null, @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null): MobileJobPage
    @retrofit2.http.PATCH("v1/auto-key-jobs/{id}") suspend fun updateMobileJob(@Path("id") id: String,
        @Body fields: com.google.gson.JsonObject, @retrofit2.http.Header("X-Expected-Updated-At") updatedAt: String?): AutoKeyJobRead
    @GET("v1/auto-key-jobs/{id}/quotes") suspend fun mobileQuotes(@Path("id") id: String): List<MobileQuote>
    @retrofit2.http.Streaming @GET("v1/auto-key-jobs/quotes/{id}/signature") suspend fun quoteSignature(@Path("id") id: String): ResponseBody
    @POST("v1/auto-key-jobs/{id}/quotes") suspend fun createMobileQuote(@Path("id") id: String, @Body body: MobileQuoteCreate): MobileQuote
    @POST("v1/auto-key-jobs/quotes/{id}/send") suspend fun sendMobileQuote(@Path("id") id: String): MobileQuoteSend
    @GET("v1/auto-key-jobs/{id}/invoices") suspend fun mobileInvoices(@Path("id") id: String): List<MobileInvoice>
    @POST("v1/auto-key-jobs/{jobId}/invoices/from-quote/{quoteId}") suspend fun createMobileInvoice(@Path("jobId") jobId: String, @Path("quoteId") quoteId: String): MobileInvoice
    @POST("v1/auto-key-jobs/invoices/{id}/send") suspend fun sendMobileInvoice(@Path("id") id: String, @Query("channel") channel: String = "both"): MobileInvoiceSend
    @retrofit2.http.PATCH("v1/auto-key-jobs/invoices/{id}") suspend fun editMobileInvoiceAmounts(@Path("id") id: String, @Body body: MobileInvoiceAmounts): MobileInvoice
    @retrofit2.http.PATCH("v1/auto-key-jobs/invoices/{id}") suspend fun updateMobileInvoice(@Path("id") id: String, @Body body: MobileInvoiceUpdate): MobileInvoice
    @GET("v1/{resource}/{id}/messages") suspend fun messages(@Path("resource") resource: String, @Path("id") id: String): List<JobThreadMessage>
    @POST("v1/{resource}/{id}/messages") suspend fun sendMessage(@Path("resource") resource: String, @Path("id") id: String, @Body body: MessageCreate): JobThreadMessage
    @POST("v1/auto-key-jobs") suspend fun createMobileJob(@Body body: MobileJobCreate): AutoKeyJobRead
    @GET("v1/shoe-catalogue/items") suspend fun shoeCatalogue(): List<ShoeCatalogueItem>
    @POST("v1/shoe-repair-jobs/shoes") suspend fun createShoe(@Body body: ShoeCreate): ShoeRead
    @POST("v1/shoe-repair-jobs") suspend fun createShoeJob(@Body body: ShoeJobCreate): ShoeRepairJobRead
    @POST("v1/shoe-repair-jobs/{id}/shoes") suspend fun linkShoe(@Path("id") id: String, @Body body: ShoeLink): ShoeRepairJobRead
    @POST("v1/shoe-repair-jobs/{id}/items") suspend fun appendShoeItems(@Path("id") id: String, @Body body: ShoeItemsAppend): ShoeRepairJobRead
    @retrofit2.http.DELETE("v1/shoe-repair-jobs/{id}/items/{itemId}") suspend fun removeShoeItem(@Path("id") id: String, @Path("itemId") itemId: String): ShoeRepairJobRead
    @retrofit2.http.DELETE("v1/shoe-repair-jobs/{id}/shoes/{entryId}") suspend fun removeShoeFromJob(@Path("id") id: String, @Path("entryId") entryId: String): ShoeRepairJobRead
    @POST("v1/shoe-repair-jobs/{id}/send-quote") suspend fun sendShoeQuote(@Path("id") id: String): ShoeRepairJobRead
    @retrofit2.http.Multipart @POST("v1/attachments") suspend fun uploadShoePhoto(
        @Query("shoe_repair_job_id") id: String, @retrofit2.http.Part file: okhttp3.MultipartBody.Part,
        @Query("label") label: String = "intake"): AttachmentRead
    @POST("v1/quotes")
    suspend fun createQuote(@Body body: QuoteCreate): QuoteRead
    @POST("v1/invoices/from-quote/{quoteId}")
    suspend fun invoiceFromQuote(@Path("quoteId") quoteId: String): InvoiceFromQuoteResponse
    @GET("v1/customer-accounts")
    suspend fun listCustomerAccounts(): List<CustomerAccountRead>
    @POST("v1/customer-accounts") suspend fun createBusinessAccount(@Body fields: com.google.gson.JsonObject): CustomerAccountRead
    @retrofit2.http.PATCH("v1/customer-accounts/{id}") suspend fun updateBusinessAccount(@Path("id") id: String, @Body fields: com.google.gson.JsonObject): CustomerAccountRead
    @GET("v1/customer-accounts/{id}") suspend fun customerAccount(@Path("id") id: String): CustomerAccountRead
    @GET("v1/customer-accounts/{id}/statement") suspend fun accountStatement(@Path("id") id: String,
        @Query("period_year") year: Int, @Query("period_month") month: Int): AccountStatement
    @GET("v1/customer-accounts/{id}/invoices") suspend fun accountInvoices(@Path("id") id: String): List<AccountInvoice>
    @POST("v1/customer-accounts/{id}/invoices/monthly") suspend fun createAccountInvoice(@Path("id") id: String, @Body body: AccountInvoiceCreate): AccountInvoice
    @POST("v1/customer-accounts/{id}/customers") suspend fun addAccountMember(@Path("id") id: String, @Body body: AccountMemberAdd): CustomerAccountRead
    @retrofit2.http.DELETE("v1/customer-accounts/{id}/customers/{customerId}") suspend fun removeAccountMember(@Path("id") id: String, @Path("customerId") customerId: String): Response<Unit>
    @GET("v1/watch-catalogue/items")
    suspend fun watchCatalogue(): List<WatchCatalogueItem>
    @GET("v1/custom-services") suspend fun customWatchServices(@Query("service_type") type: String = "watch"): List<WatchCatalogueItem>
    @GET("v1/custom-services") suspend fun customShoeServices(@Query("service_type") type: String = "shoe"): List<ShoeCatalogueItem>
    @GET("v1/watch-catalogue/repairs-config")
    suspend fun watchRepairsConfig(): WatchRepairsConfig
    @POST("v1/customers")
    suspend fun createCustomer(@Body body: CustomerCreate): CustomerRead
    @retrofit2.http.PATCH("v1/customers/{id}")
    suspend fun updateCustomer(@Path("id") id: String, @Body body: CustomerCreate): CustomerRead
    @retrofit2.http.PATCH("v1/customers/{id}")
    suspend fun updateCustomerFields(@Path("id") id: String, @Body body: com.google.gson.JsonObject): CustomerRead

    @POST("v1/watches")
    suspend fun createWatch(@Body body: WatchCreate): WatchRead
    @GET("v1/watches/{id}") suspend fun getWatch(@Path("id") id: String): WatchRead
    @retrofit2.http.PATCH("v1/watches/{id}") suspend fun updateWatch(@Path("id") id: String, @Body body: com.google.gson.JsonObject): WatchRead

    @retrofit2.http.Multipart
    @POST("v1/attachments")
    suspend fun uploadPhoto(
        @Query("repair_job_id") jobId: String,
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part,
        @Query("label") label: String? = null,
    ): AttachmentRead
    @POST("v1/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("v1/auth/session")
    suspend fun session(): SessionResponse

    @GET("v1/reports/summary")
    suspend fun getReportsSummary(): ReportsSummaryResponse

    @GET("v1/reports/widgets")
    suspend fun getReportsWidgets(): DashboardWidgetsResponse

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

    @GET("v1/watches")
    suspend fun listWatches(
        @Query("customer_id") customerId: String,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "created_at",
        @Query("sort_dir") sortDir: String = "desc",
    ): List<WatchRead>

    @GET("v1/repair-jobs")
    suspend fun listRepairJobs(
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "created_at",
        @Query("sort_dir") sortDir: String = "desc",
        @Query("q") q: String? = null,
        @Query("customer_id") customerId: String? = null,
        @Query("status") status: String? = null,
        @Query("assigned_user_id") assignedUserId: String? = null,
    ): List<RepairJobRead>

    @GET("v1/repair-jobs/{jobId}")
    suspend fun getRepairJob(@Path("jobId") jobId: String): RepairJobRead

    @POST("v1/repair-jobs")
    suspend fun postRepairJob(@Body body: RepairJobCreate): RepairJobRead

    @GET("v1/repair-jobs/{jobId}/status-history")
    suspend fun getRepairJobStatusHistory(@Path("jobId") jobId: String): List<JobStatusHistoryRead>

    @GET("v1/repair-jobs/{jobId}/sms-log")
    suspend fun getRepairJobSmsLog(@Path("jobId") jobId: String): List<SmsLogRead>

    @POST("v1/repair-jobs/{jobId}/resend-notification")
    suspend fun postRepairJobResendNotification(
        @Path("jobId") jobId: String,
        @Body body: ResendNotificationRequest,
    ): ResendNotificationResponse

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
        @Query("repair_job_id") repairJobId: String? = null,
        @Query("shoe_repair_job_id") shoeRepairJobId: String? = null,
        @Query("auto_key_job_id") autoKeyJobId: String? = null,
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
        @Query("repair_job_id") repairJobId: String? = null,
    ): List<QuoteRead>

    @GET("v1/quotes/{quoteId}/line-items")
    suspend fun getQuoteLineItems(@Path("quoteId") quoteId: String): List<QuoteLineItemRead>

    @POST("v1/quotes/{quoteId}/resend")
    suspend fun postQuoteResend(@Path("quoteId") quoteId: String): QuoteSendResponse

    @POST("v1/quotes/{quoteId}/send")
    suspend fun postQuoteSend(@Path("quoteId") quoteId: String): QuoteSendResponse

    @GET("v1/invoices")
    suspend fun listInvoices(@Query("limit") limit: Int = 100, @Query("offset") offset: Int = 0): InvoicePage

    @POST("v1/invoices/{id}/send")
    suspend fun sendInvoice(@Path("id") id: String): InvoiceSendResponse

    @GET("v1/invoices/{invoiceId}")
    suspend fun getInvoice(@Path("invoiceId") invoiceId: String): InvoiceWithPayments

    @GET("v1/invoices/{invoiceId}/line-items")
    suspend fun getInvoiceLineItems(@Path("invoiceId") invoiceId: String): List<QuoteLineItemRead>

    @POST("v1/invoices/{invoiceId}/payments")
    suspend fun postInvoicePayment(
        @Path("invoiceId") invoiceId: String,
        @Body body: PaymentCreate,
    ): PaymentRead

    @GET("v1/inbox")
    suspend fun listInbox(
        @Query("limit") limit: Int = 80,
        @Query("offset") offset: Int = 0,
    ): List<TenantEventLogRead>

    @GET("v1/shoe-repair-jobs")
    suspend fun listShoeRepairJobs(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 200,
        @Query("status") status: String? = null,
        @Query("customer_id") customerId: String? = null,
    ): List<ShoeRepairJobRead>

    @GET("v1/shoe-repair-jobs/{jobId}")
    suspend fun getShoeRepairJob(@Path("jobId") jobId: String): ShoeRepairJobRead

    @GET("v1/shoe-repair-jobs/{jobId}/status-history")
    suspend fun getShoeRepairJobStatusHistory(@Path("jobId") jobId: String): List<ShoeJobStatusHistoryRead>

    @POST("v1/shoe-repair-jobs/{jobId}/status")
    suspend fun postShoeRepairJobStatus(
        @Path("jobId") jobId: String,
        @Body body: ShoeStatusUpdate,
    ): ShoeRepairJobRead

    @POST("v1/shoe-repair-jobs/{jobId}/note")
    suspend fun postShoeRepairJobNote(
        @Path("jobId") jobId: String,
        @Body body: JobNotePayload,
    ): Response<ResponseBody>

    @POST("v1/shoe-repair-jobs/{jobId}/claim")
    suspend fun postShoeRepairJobClaim(@Path("jobId") jobId: String): ShoeRepairJobRead

    @POST("v1/shoe-repair-jobs/{jobId}/release")
    suspend fun postShoeRepairJobRelease(@Path("jobId") jobId: String): ShoeRepairJobRead

    @GET("v1/auto-key-jobs")
    suspend fun listAutoKeyJobs(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 200,
        @Query("customer_id") customerId: String? = null,
    ): List<AutoKeyJobRead>

    @POST("v1/auto-key-jobs/quick-intake")
    suspend fun postAutoKeyQuickIntake(@Body body: AutoKeyQuickIntakeCreate): AutoKeyJobRead

    @GET("v1/auto-key-jobs/{jobId}")
    suspend fun getAutoKeyJob(@Path("jobId") jobId: String): AutoKeyJobRead

    @POST("v1/auto-key-jobs/{jobId}/status")
    suspend fun postAutoKeyJobStatus(
        @Path("jobId") jobId: String,
        @Body body: RepairJobStatusUpdate,
        @retrofit2.http.Header("X-Expected-Updated-At") updatedAt: String? = null,
    ): AutoKeyJobRead

    @GET("v1/customer-orders")
    suspend fun listCustomerOrders(@Query("status") status: String? = null): List<CustomerOrderRead>

    @POST("v1/customer-orders")
    suspend fun createCustomerOrder(@Body body: CustomerOrderCreate): CustomerOrderRead

    @retrofit2.http.PATCH("v1/customer-orders/{id}")
    suspend fun updateCustomerOrder(@Path("id") id: String, @Body body: CustomerOrderUpdate): CustomerOrderRead
}
