package au.mainspring.nativeapp.api

import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName

data class RefreshRequest(
    @SerializedName("refresh_token") val refreshToken: String,
)

data class LoginRequest(
    @SerializedName("tenant_slug") val tenantSlug: String,
    val email: String,
    val password: String,
)
data class MultiSiteLoginRequest(val email: String, val password: String)
data class SiteSwitchRequest(@SerializedName("tenant_id") val tenantId: String)
data class SessionSite(@SerializedName("tenant_id") val tenantId: String,
    @SerializedName("tenant_name") val name: String, @SerializedName("tenant_slug") val slug: String,
    @SerializedName("user_id") val userId: String, val role: String)

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String?,
    @SerializedName("expires_in_seconds") val expiresInSeconds: Int?,
)

data class SessionUser(
    val id: String,
    @SerializedName("full_name") val fullName: String,
    val email: String,
    val role: String,
)

data class SessionResponse(
    @SerializedName("default_currency") val currency: String? = null,
    @SerializedName("tenant_name") val shopName: String? = null,
    @SerializedName("tenant_abn") val shopAbn: String? = null,
    @SerializedName("tenant_shop_phone") val shopPhone: String? = null,
    @SerializedName("tenant_business_address") val shopAddress: String? = null,
    @SerializedName("tenant_id") val tenantId: String,
    val user: SessionUser,
    @SerializedName("tenant_slug") val tenantSlug: String,
    @SerializedName("plan_code") val planCode: String,
    @SerializedName("schedule_calendar_timezone") val calendarTimezone: String = "Australia/Sydney",
    @SerializedName("enabled_features") val enabledFeatures: List<String> = emptyList(),
    @SerializedName("mobile_services_customer_sms_enabled") val mobileSmsEnabled: Boolean = false,
    @SerializedName("active_site_tenant_id") val activeSiteId: String? = null,
    @SerializedName("available_sites") val sites: List<SessionSite> = emptyList(),
    @SerializedName("is_minit_hq_ui") val hqConsole: Boolean = false,
    @SerializedName("is_platform_console") val platformConsole: Boolean = false,
    @SerializedName("signup_payment_pending") val signupPaymentPending: Boolean = false,
    /** Stripe status: trialing, active, past_due, canceled, or null. */
    @SerializedName("subscription_status") val subscriptionStatus: String? = null,
    /** ISO-8601 UTC instant the trial ends, or null. */
    @SerializedName("trial_end") val trialEnd: String? = null,
)
data class ArrivalSmsRequest(@SerializedName("time_window") val timeWindow: String)
data class ArrivalSmsResponse(val ok: Boolean)

data class CustomerRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("full_name") val fullName: String,
    val email: String?,
    val phone: String?,
    val address: String?,
    val notes: String?,
    @SerializedName("created_at") val createdAt: String,
)

data class WatchRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("customer_id") val customerId: String,
    val brand: String? = null,
    val model: String? = null,
    @SerializedName("serial_number") val serialNumber: String? = null,
    @SerializedName("movement_type") val movementType: String? = null,
    @SerializedName("condition_notes") val conditionNotes: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)

data class RepairJobRead(
    val id: String,
    @SerializedName("deposit_cents") val depositCents: Int = 0,
    @SerializedName("pre_quote_cents") val preQuoteCents: Int = 0,
    @SerializedName("cost_cents") val costCents: Int = 0,
    val salesperson: String? = null,
    @SerializedName("collection_date") val collectionDate: String? = null,
    @SerializedName("parts_eta") val partsEta: String? = null,
    @SerializedName("internal_notes") val internalNotes: String? = null,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("watch_id") val watchId: String,
    @SerializedName("job_number") val jobNumber: String,
    val title: String,
    val description: String?,
    val status: String,
    val priority: String,
    @SerializedName("customer_name") val customerName: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("claimed_by_user_id") val claimedByUserId: String? = null,
    @SerializedName("claimed_by_name") val claimedByName: String? = null,
    @SerializedName("customer_account_id") val customerAccountId: String? = null,
    @SerializedName("tracking_sms_skipped_reason") val trackingSmsSkippedReason: String? = null,
    @SerializedName("assigned_user_id") val assignedUserId: String? = null,
    @SerializedName("status_token") val statusToken: String? = null,
    @SerializedName("customer_phone") val customerPhone: String? = null,
    @SerializedName("customer_email") val customerEmail: String? = null,
    @SerializedName("watch_brand") val watchBrand: String? = null,
    @SerializedName("watch_model") val watchModel: String? = null,
    @SerializedName("status_changed_at") val statusChangedAt: String? = null,
    @SerializedName("customer_note") val customerNote: String? = null,
)

data class AttachmentRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("repair_job_id") val repairJobId: String? = null,
    @SerializedName("watch_id") val watchId: String? = null,
    @SerializedName("shoe_repair_job_id") val shoeRepairJobId: String? = null,
    @SerializedName("auto_key_job_id") val autoKeyJobId: String? = null,
    @SerializedName("storage_key") val storageKey: String,
    @SerializedName("file_name") val fileName: String? = null,
    @SerializedName("content_type") val contentType: String? = null,
    @SerializedName("file_size_bytes") val fileSizeBytes: Int? = null,
    val label: String? = null,
    @SerializedName("created_at") val createdAt: String,
)

data class AttachmentDownloadLinkResponse(
    @SerializedName("download_url") val downloadUrl: String,
    @SerializedName("expires_in_seconds") val expiresInSeconds: Int,
)

data class RepairJobStatusUpdate(
    val status: String,
    val note: String? = null,
    /** Shown to the customer on their status page; backend max length 280. */
    @SerializedName("customer_note") val customerNote: String? = null,
)

data class JobNotePayload(
    val note: String,
)
data class JobThreadMessage(val id: String, val direction: String, val body: String,
    val event: String? = null, val status: String? = null,
    @SerializedName("created_at") val createdAt: String)
data class MessageCreate(val body: String)

data class JobStatusHistoryRead(
    val id: String,
    @SerializedName("repair_job_id") val repairJobId: String? = null,
    @SerializedName("old_status") val oldStatus: String?,
    @SerializedName("new_status") val newStatus: String,
    @SerializedName("change_note") val changeNote: String?,
    @SerializedName("created_at") val createdAt: String,
)

data class QuoteRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String? = null,
    @SerializedName("repair_job_id") val repairJobId: String,
    val status: String,
    @SerializedName("subtotal_cents") val subtotalCents: Int,
    @SerializedName("tax_cents") val taxCents: Int,
    @SerializedName("total_cents") val totalCents: Int,
    val currency: String,
    @SerializedName("approval_token") val approvalToken: String? = null,
    @SerializedName("sent_at") val sentAt: String? = null,
    @SerializedName("created_at") val createdAt: String,
)

data class QuoteLineItemRead(
    val id: String? = null,
    val description: String? = null,
    val quantity: Double = 1.0,
    @SerializedName("unit_price_cents") val unitPriceCents: Int = 0,
    @SerializedName("item_type") val itemType: String? = null,
)

data class QuoteSendResponse(
    val id: String,
    val status: String,
    @SerializedName("sent_at") val sentAt: String,
    @SerializedName("approval_token") val approvalToken: String,
)

data class QuoteCreate(
    @SerializedName("repair_job_id") val repairJobId: String,
    @SerializedName("gst_enabled") val gstEnabled: Boolean,
    @SerializedName("gst_inclusive") val gstInclusive: Boolean,
    @SerializedName("line_items") val lines: List<QuoteLineItemRead>,
)
data class InvoiceFromQuoteResponse(val invoice: InvoiceRead)

data class ShoeCreate(@SerializedName("customer_id") val customerId: String,
    @SerializedName("shoe_type") val shoeType: String?, val brand: String?, val color: String?,
    @SerializedName("description_notes") val notes: String?)
data class ShoeRead(val id: String,
    @SerializedName("customer_id") val customerId: String? = null,
    @SerializedName("shoe_type") val shoeType: String? = null, val brand: String? = null, val color: String? = null,
    @SerializedName("description_notes") val notes: String? = null)
data class ShoeJobShoeEntry(val id: String, @SerializedName("shoe_id") val shoeId: String, val shoe: ShoeRead? = null,
    @SerializedName("sort_order") val sortOrder: Int = 0)
data class ShoeStatusUpdate(val status: String, val note: String? = null,
    @SerializedName("customer_note") val customerNote: String? = null)
data class ShoeCatalogueItem(val key: String, val name: String,
    @SerializedName("group_id") val groupId: String,
    @SerializedName("price_cents") val priceCents: Int?,
    @SerializedName("pricing_type") val pricingType: String)
data class ShoeItemCreate(@SerializedName("catalogue_key") val key: String,
    @SerializedName("catalogue_group") val group: String,
    @SerializedName("item_name") val name: String,
    @SerializedName("pricing_type") val pricingType: String,
    @SerializedName("unit_price_cents") val price: Int?, val quantity: Double = 1.0, val notes: String? = null)
data class ShoeJobCreate(@SerializedName("shoe_id") val shoeId: String, val title: String,
    val description: String?, val priority: String, val status: String,
    val salesperson: String?, @SerializedName("collection_date") val collectionDate: String?,
    @SerializedName("deposit_cents") val deposit: Int, val items: List<ShoeItemCreate>,
    @SerializedName("customer_account_id") val accountId: String? = null)
data class ShoeLink(@SerializedName("shoe_id") val shoeId: String)
data class ShoeItemsAppend(val items: List<ShoeItemCreate>)
data class ShoeJobItemRead(val id: String, @SerializedName("item_name") val name: String,
    @SerializedName("unit_price_cents") val price: Int?, val quantity: Double, val notes: String?)
data class MobileJobCreate(@SerializedName("customer_id") val customerId: String,
    val title: String, val description: String?, val priority: String, val status: String,
    @SerializedName("scheduled_at") val scheduledAt: String?,
    @SerializedName("job_address") val address: String?, @SerializedName("job_type") val jobType: String?,
    @SerializedName("vehicle_make") val make: String?, @SerializedName("vehicle_model") val model: String?,
    @SerializedName("vehicle_year") val year: Int?, @SerializedName("registration_plate") val plate: String?,
    val vin: String?, @SerializedName("key_type") val keyType: String?, @SerializedName("key_quantity") val keyQuantity: Int,
    @SerializedName("tech_notes") val techNotes: String?,
    @SerializedName("deposit_cents") val deposit: Int, @SerializedName("send_booking_sms") val sendBookingSms: Boolean = false,
    @SerializedName("customer_account_id") val customerAccountId: String? = null,
    @SerializedName("assigned_user_id") val assignedUserId: String? = null)

data class ShoeJobStatusHistoryRead(
    val id: String,
    @SerializedName("shoe_repair_job_id") val shoeRepairJobId: String,
    @SerializedName("old_status") val oldStatus: String?,
    @SerializedName("new_status") val newStatus: String,
    @SerializedName("change_note") val changeNote: String?,
    @SerializedName("created_at") val createdAt: String,
)

data class SmsLogRead(
    val id: String,
    @SerializedName("to_phone") val toPhone: String,
    val body: String,
    val event: String,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
)

data class ResendNotificationRequest(
    @SerializedName("event_type") val eventType: String,
)

data class ResendNotificationChannels(
    val sms: Boolean,
    val email: Boolean,
)

data class ResendNotificationResponse(
    val sent: ResendNotificationChannels,
)

data class InvoiceRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("repair_job_id") val repairJobId: String,
    @SerializedName("quote_id") val quoteId: String? = null,
    @SerializedName("invoice_number") val invoiceNumber: String,
    val status: String,
    @SerializedName("subtotal_cents") val subtotalCents: Int,
    @SerializedName("tax_cents") val taxCents: Int,
    @SerializedName("total_cents") val totalCents: Int,
    val currency: String,
    @SerializedName("created_at") val createdAt: String,
)

data class PaymentRead(
    val id: String,
    @SerializedName("invoice_id") val invoiceId: String? = null,
    @SerializedName("amount_cents") val amountCents: Int,
    val currency: String,
    val status: String,
    val provider: String,
    @SerializedName("provider_reference") val providerReference: String? = null,
)

data class PaymentCreate(
    @SerializedName("amount_cents") val amountCents: Int,
    @SerializedName("provider_reference") val providerReference: String? = null,
)

data class InvoiceWithPayments(
    val invoice: InvoiceRead,
    val payments: List<PaymentRead>,
)

data class TenantEventLogRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String? = null,
    @SerializedName("event_type") val eventType: String,
    @SerializedName("event_summary") val eventSummary: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("entity_type") val entityType: String? = null,
    @SerializedName("entity_id") val entityId: String? = null,
)

data class ShoeRepairJobRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("shoe_id") val shoeId: String,
    @SerializedName("assigned_user_id") val assignedUserId: String? = null,
    @SerializedName("customer_account_id") val customerAccountId: String? = null,
    @SerializedName("job_number") val jobNumber: String,
    @SerializedName("status_token") val statusToken: String,
    val title: String,
    val description: String? = null,
    val priority: String,
    val status: String,
    val salesperson: String? = null,
    @SerializedName("collection_date") val collectionDate: String? = null,
    @SerializedName("deposit_cents") val depositCents: Int,
    @SerializedName("cost_cents") val costCents: Int,
    @SerializedName("quote_approval_token") val quoteApprovalToken: String,
    @SerializedName("quote_approval_token_expires_at") val quoteApprovalTokenExpiresAt: String? = null,
    @SerializedName("quote_status") val quoteStatus: String,
    @SerializedName("created_at") val createdAt: String,
    val items: List<ShoeJobItemRead> = emptyList(),
    val shoe: ShoeRead? = null,
    @SerializedName("extra_shoes") val extraShoes: List<ShoeJobShoeEntry>? = null,
    @SerializedName("customer_note") val customerNote: String? = null,
    val complexity: String? = null,
    @SerializedName("estimated_days_min") val estimatedDaysMin: Int? = null,
    @SerializedName("estimated_days_max") val estimatedDaysMax: Int? = null,
    @SerializedName("estimated_ready_by") val estimatedReadyBy: String? = null,
    @SerializedName("claimed_by_user_id") val claimedByUserId: String? = null,
    @SerializedName("claimed_by_name") val claimedByName: String? = null,
    @SerializedName("tracking_sms_skipped_reason") val trackingSmsSkippedReason: String? = null,
)

data class AutoKeyJobRead(
    val id: String,
    @SerializedName("updated_at") val updatedAt: String? = null,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("customer_id") val customerId: String,
    @SerializedName("assigned_user_id") val assignedUserId: String? = null,
    @SerializedName("customer_account_id") val customerAccountId: String? = null,
    @SerializedName("job_number") val jobNumber: String,
    @SerializedName("status_token") val statusToken: String,
    val title: String,
    val description: String? = null,
    @SerializedName("vehicle_make") val vehicleMake: String? = null,
    @SerializedName("vehicle_model") val vehicleModel: String? = null,
    @SerializedName("vehicle_year") val vehicleYear: Int? = null,
    @SerializedName("registration_plate") val registrationPlate: String? = null,
    val vin: String? = null,
    @SerializedName("key_type") val keyType: String? = null,
    @SerializedName("blade_code") val bladeCode: String? = null,
    @SerializedName("chip_type") val chipType: String? = null,
    @SerializedName("tech_notes") val techNotes: String? = null,
    @SerializedName("key_quantity") val keyQuantity: Int,
    @SerializedName("programming_status") val programmingStatus: String,
    val priority: String,
    val status: String,
    val salesperson: String? = null,
    @SerializedName("collection_date") val collectionDate: String? = null,
    @SerializedName("deposit_cents") val depositCents: Int,
    @SerializedName("cost_cents") val costCents: Int,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("scheduled_at") val scheduledAt: String? = null,
    @SerializedName("job_address") val jobAddress: String? = null,
    @SerializedName("job_type") val jobType: String? = null,
    @SerializedName("visit_order") val visitOrder: Int? = null,
    @SerializedName("additional_services_json") val additionalServicesJson: String? = null,
    @SerializedName("commission_lead_source") val commissionLeadSource: String,
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("tracking_sms_skipped_reason") val trackingSmsSkippedReason: String? = null,
    @SerializedName("customer_phone") val customerPhone: String? = null,
    @SerializedName("invoice_created") val invoiceCreated: Boolean? = null,
    @SerializedName("invoice_skip_reason") val invoiceSkipReason: String? = null,
)

data class ReportsCounts(
    val jobs: Int,
    val customers: Int,
    val watches: Int,
    val quotes: Int,
    val invoices: Int,
    @SerializedName("shoe_jobs") val shoeJobs: Int = 0,
)

data class ShoeQuotesSummary(
    @SerializedName("by_status") val byStatus: Map<String, Int> = emptyMap(),
    @SerializedName("approval_rate_percent") val approvalRatePercent: Double = 0.0,
)

data class SalesFunnelSummary(
    @SerializedName("approved_quotes") val approvedQuotes: Int,
    @SerializedName("sent_quotes") val sentQuotes: Int,
    @SerializedName("declined_quotes") val declinedQuotes: Int,
    @SerializedName("approval_rate_percent") val approvalRatePercent: Double,
)

data class ReportsFinancials(
    @SerializedName("billed_cents") val billedCents: Int,
    @SerializedName("revenue_cents") val revenueCents: Int,
    @SerializedName("cost_cents") val costCents: Int,
    @SerializedName("outstanding_cents") val outstandingCents: Int,
    @SerializedName("gross_profit_cents") val grossProfitCents: Int,
    @SerializedName("gross_margin_percent") val grossMarginPercent: Double,
)

data class ReportsOperations(
    @SerializedName("work_minutes") val workMinutes: Int,
    @SerializedName("avg_revenue_per_job_cents") val avgRevenuePerJobCents: Int,
    @SerializedName("avg_turnaround_days") val avgTurnaroundDays: Double? = null,
    @SerializedName("quote_to_invoice_pct") val quoteToInvoicePct: Double,
    @SerializedName("avg_quote_response_hours") val avgQuoteResponseHours: Double? = null,
)

data class ReportsSummaryResponse(
    val counts: ReportsCounts,
    @SerializedName("jobs_by_status") val jobsByStatus: Map<String, Int> = emptyMap(),
    @SerializedName("shoe_jobs_by_status") val shoeJobsByStatus: Map<String, Int>? = null,
    @SerializedName("shoe_quotes") val shoeQuotes: ShoeQuotesSummary? = null,
    @SerializedName("quotes_by_status") val quotesByStatus: Map<String, Int> = emptyMap(),
    @SerializedName("sales_funnel") val salesFunnel: SalesFunnelSummary,
    val financials: ReportsFinancials,
    val operations: ReportsOperations,
)

data class DashboardWidgetsResponse(
    @SerializedName("overdue_jobs_count") val overdueJobsCount: Int,
    @SerializedName("quotes_pending_7d_count") val quotesPending7dCount: Int,
    @SerializedName("overdue_invoices_count") val overdueInvoicesCount: Int,
    @SerializedName("overdue_collection_count") val overdueCollectionCount: Int,
)

data class RepairJobCreate(
    @SerializedName("watch_id") val watchId: String,
    @SerializedName("customer_account_id") val customerAccountId: String? = null,
    val title: String,
    val description: String? = null,
    val priority: String = "normal",
    val status: String? = null,
    val salesperson: String? = null,
    @SerializedName("collection_date") val collectionDate: String? = null,
    @SerializedName("deposit_cents") val depositCents: Int = 0,
    @SerializedName("pre_quote_cents") val preQuoteCents: Int = 0,
    @SerializedName("job_number_override") val jobNumberOverride: String? = null,
)

data class CustomerCreate(
    @SerializedName("full_name") val fullName: String,
    val phone: String? = null,
    val email: String? = null,
    val address: String? = null,
    val notes: String? = null,
)

data class WatchCreate(
    @SerializedName("customer_id") val customerId: String,
    val brand: String?,
    val model: String?,
    @SerializedName("serial_number") val serialNumber: String?,
    @SerializedName("condition_notes") val conditionNotes: String?,
    @SerializedName("movement_type") val movementType: String? = null,
)

data class CustomerAccountRead(val id: String, val name: String,
    @SerializedName("customer_ids") val customerIds: List<String> = emptyList(),
    @SerializedName("is_active") val active: Boolean = true,
    @SerializedName("account_code") val code: String? = null,
    @SerializedName("contact_name") val contactName: String? = null,
    @SerializedName("contact_email") val email: String? = null,
    @SerializedName("contact_phone") val phone: String? = null,
    @SerializedName("billing_address") val address: String? = null,
    @SerializedName("payment_terms_days") val terms: Int = 30,
    val notes: String? = null,
    @SerializedName("account_type") val type: String? = null,
    @SerializedName("fleet_size") val fleetSize: Int? = null,
    @SerializedName("billing_cycle") val billingCycle: String? = null,
    @SerializedName("primary_contact_name") val primaryContact: String? = null,
    @SerializedName("primary_contact_phone") val primaryPhone: String? = null,
    @SerializedName("credit_limit") val creditLimit: Int? = null,
    @SerializedName("account_notes") val accountNotes: String? = null)
data class WatchCatalogueItem(val key: String, val name: String,
    @SerializedName("price_cents") val priceCents: Int?,
    @SerializedName("pricing_type") val pricingType: String,
    @SerializedName("group_label") val groupLabel: String?)
data class WatchRepairsCombo(val keys: List<String>? = null,
    @SerializedName("total_cents") val totalCents: Int? = null,
    @SerializedName("battery_key") val batteryKey: String? = null,
    @SerializedName("band_keys") val bandKeys: List<String>? = null,
    @SerializedName("band_discount_percent") val bandDiscountPercent: Double? = null)
data class WatchRepairsConfig(val combos: List<WatchRepairsCombo> = emptyList(), val currency: String = "AUD")

data class AutoKeyQuickIntakeCreate(
    @SerializedName("full_name") val fullName: String,
    val phone: String,
)

data class InvoicePage(val items: List<InvoiceRead> = emptyList(), val total: Int = 0, val limit: Int = 100, val offset: Int = 0)
data class InvoiceSendResponse(
    @SerializedName("invoice_id") val invoiceId: String,
    @SerializedName("email_sent") val emailSent: Boolean,
    @SerializedName("email_skipped_reason") val skippedReason: String?,
    @SerializedName("email_error_detail") val errorDetail: String?,
)

data class MobileQuoteCreate(@SerializedName("line_items") val lines: List<MobileQuoteLine>, @SerializedName("gst_enabled") val gst: Boolean, @SerializedName("gst_inclusive") val inclusive: Boolean)
data class MobileQuoteLine(val description: String, val quantity: Double = 1.0, @SerializedName("unit_price_cents") val unitCents: Int)
data class MobileQuote(val id: String, val status: String, @SerializedName("subtotal_cents") val subtotal: Int,
    @SerializedName("tax_cents") val tax: Int, @SerializedName("total_cents") val total: Int, val currency: String,
    @SerializedName("line_items") val lines: List<MobileQuoteLine> = emptyList(), @SerializedName("signer_name") val signer: String? = null,
    @SerializedName("signed_at") val signedAt: String? = null, @SerializedName("has_signature") val hasSignature: Boolean = false)
data class MobileInvoice(val id: String, @SerializedName("invoice_number") val number: String, val status: String,
    @SerializedName("auto_key_quote_id") val quoteId: String?, @SerializedName("total_cents") val total: Int,
    val currency: String, @SerializedName("payment_method") val paymentMethod: String? = null,
    @SerializedName("subtotal_cents") val subtotal: Int? = null, @SerializedName("tax_cents") val tax: Int? = null,
    @SerializedName("created_at") val createdAt: String? = null, @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("job_number") val jobNumber: String? = null)
/** Amount edit for an unpaid mobile invoice (web `updateAutoKeyInvoice` with subtotal/tax/total). */
data class MobileInvoiceAmounts(@SerializedName("subtotal_cents") val subtotal: Int, @SerializedName("tax_cents") val tax: Int, @SerializedName("total_cents") val total: Int)
data class MobileInvoiceUpdate(val status: String, @SerializedName("payment_method") val paymentMethod: String)
data class MobileQuoteSend(val quote: MobileQuote, @SerializedName("email_sent") val sent: Boolean,
    @SerializedName("email_skipped_reason") val reason: String?)
data class MobileInvoiceSend(val invoice: MobileInvoice, @SerializedName("email_sent") val emailSent: Boolean,
    @SerializedName("sms_sent") val smsSent: Boolean, @SerializedName("email_skipped_reason") val reason: String?,
    @SerializedName("sms_skipped_reason") val smsReason: String? = null, @SerializedName("email_error_detail") val emailError: String? = null)

data class MobileJobPage(val items: List<AutoKeyJobRead> = emptyList(), val total: Int = 0)

data class ToolkitCatalog(val title: String, val groups: List<ToolGroup>, val scenarios: List<ToolScenario>)
data class ToolGroup(val id: String, val label: String, val tools: List<ToolItem>)
data class ToolItem(val key: String, val name: String, val notes: String? = null)
data class ToolScenario(val id: String, val label: String, val tips: String? = null)
data class ToolSelection(@SerializedName("tool_keys") val keys: List<String>)
data class ToolRecommend(@SerializedName("scenario_id") val scenario: String, @SerializedName("tool_keys") val keys: List<String>)
data class ToolReadiness(val label: String, val tips: String?, @SerializedName("ready_for_required") val ready: Boolean,
    @SerializedName("missing_required") val missing: List<ToolItem>, @SerializedName("missing_nice_to_have") val nice: List<ToolItem>)

data class ProspectBusiness(val name: String, val address: String, val phone: String?, val website: String?, val category: String,
    @SerializedName("place_id") val placeId: String, val rating: Double?, @SerializedName("review_count") val reviews: Int?)
data class ProspectResults(val results: List<ProspectBusiness>, val total: Int, val source: String)
data class ProspectCategory(val key: String, val label: String)
data class ProspectCategories(val categories: List<ProspectCategory>)
data class ProspectLead(val id: String, val name: String, val address: String?, val phone: String?, val website: String?, val status: String,
    @SerializedName("place_id") val placeId: String?, @SerializedName("contact_name") val contactName: String?,
    @SerializedName("contact_email") val contactEmail: String?, val notes: String?, @SerializedName("visit_scheduled_at") val visit: String?,
    @SerializedName("customer_account_id") val accountId: String?)
data class ProspectSave(val name: String, val address: String, val phone: String?, val website: String?, val category: String,
    @SerializedName("place_id") val placeId: String, val rating: Double?, @SerializedName("review_count") val reviews: Int?, @SerializedName("state_code") val state: String)

data class BookingPage(val items: List<BookingRequest>, val total: Int)
data class BookingOperator(@SerializedName("tenant_id") val id: String, @SerializedName("tenant_name") val name: String)
data class BookingRequest(val id: String, val status: String, @SerializedName("customer_name") val customer: String,
    @SerializedName("requesting_tenant_id") val requestingTenant: String, @SerializedName("target_operator_tenant_id") val targetTenant: String,
    @SerializedName("requesting_shop_name") val shop: String, @SerializedName("target_operator_name") val operator: String,
    @SerializedName("job_address") val address: String, @SerializedName("preferred_scheduled_at") val schedule: String?, val notes: String?,
    @SerializedName("decline_reason") val declineReason: String?, @SerializedName("schedule_conflict_warning") val conflict: String?,
    @SerializedName("resulting_auto_key_job_id") val jobId: String?)

data class WorkLogCreate(@SerializedName("repair_job_id") val jobId: String, val note: String?, @SerializedName("minutes_spent") val minutes: Int)
data class WorkLogRead(val id: String, val note: String?, @SerializedName("minutes_spent") val minutes: Int, @SerializedName("created_at") val createdAt: String)

data class PricingMeta(@SerializedName("enabled_categories") val categories: List<String>)
data class PricingRow(val id: String, val make: String? = null, @SerializedName("model_variant") val model: String? = null,
    @SerializedName("job_type") val jobType: String? = null, @SerializedName("service_name") val service: String? = null,
    val description: String? = null, val notes: String? = null, @SerializedName("key_type") val keyType: String? = null,
    @SerializedName("tool_required") val tool: String? = null, @SerializedName("service_location") val location: String? = null,
    @SerializedName("retail_price") val price: java.math.BigDecimal? = null, @SerializedName("callout_inclusive") val callout: Boolean = false) {
    fun label(): String = service ?: listOfNotNull(make, model, jobType, keyType).filter { it.isNotBlank() }.joinToString(" · ")
}

data class CustomerOrderRead(
    val id: String,
    @SerializedName("customer_id") val customerId: String? = null,
    @SerializedName("customer_name") val customerName: String? = null,
    val title: String,
    val description: String? = null,
    val supplier: String? = null,
    val status: String,
    val priority: String = "normal",
    @SerializedName("estimated_cost_cents") val estimatedCostCents: Int = 0,
    val notes: String? = null,
)
data class CustomerOrderCreate(
    val title: String,
    val description: String? = null,
    val supplier: String? = null,
    @SerializedName("customer_id") val customerId: String? = null,
    val priority: String = "normal",
    @SerializedName("estimated_cost_cents") val estimatedCostCents: Int = 0,
    val notes: String? = null,
)
data class CustomerOrderUpdate(
    val status: String? = null,
    val title: String? = null,
    val supplier: String? = null,
    val priority: String? = null,
    @SerializedName("estimated_cost_cents") val estimatedCostCents: Int? = null,
    val notes: String? = null,
)

/** Body of POST v1/me/devices; platform is android for this app (the server also accepts ios). */
data class DeviceRegisterBody(val token: String, val platform: String = "android")
