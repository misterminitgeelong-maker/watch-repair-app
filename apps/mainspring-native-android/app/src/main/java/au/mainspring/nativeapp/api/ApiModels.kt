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

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String?,
    @SerializedName("expires_in_seconds") val expiresInSeconds: Int?,
)

data class SessionUser(
    @SerializedName("full_name") val fullName: String,
    val email: String,
    val role: String,
)

data class SessionResponse(
    val user: SessionUser,
    @SerializedName("tenant_slug") val tenantSlug: String,
    @SerializedName("plan_code") val planCode: String,
)

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

data class RepairJobRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("watch_id") val watchId: String,
    @SerializedName("job_number") val jobNumber: String,
    val title: String,
    val description: String?,
    val status: String,
    val priority: String,
    @SerializedName("customer_name") val customerName: String?,
    @SerializedName("created_at") val createdAt: String,
)

data class RepairJobStatusUpdate(
    val status: String,
    val note: String? = null,
)

data class JobNotePayload(
    val note: String,
)

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
    val items: JsonElement? = null,
    val shoe: JsonElement? = null,
    @SerializedName("extra_shoes") val extraShoes: JsonElement? = null,
    val complexity: String? = null,
    @SerializedName("estimated_days_min") val estimatedDaysMin: Int? = null,
    @SerializedName("estimated_days_max") val estimatedDaysMax: Int? = null,
    @SerializedName("estimated_ready_by") val estimatedReadyBy: String? = null,
    @SerializedName("claimed_by_user_id") val claimedByUserId: String? = null,
    @SerializedName("claimed_by_name") val claimedByName: String? = null,
)

data class AutoKeyJobRead(
    val id: String,
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
    @SerializedName("customer_phone") val customerPhone: String? = null,
)
