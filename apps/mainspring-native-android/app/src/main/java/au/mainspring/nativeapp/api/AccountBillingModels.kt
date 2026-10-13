package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName

data class AccountStatementLine(
    @SerializedName("source_type") val sourceType: String,
    @SerializedName("source_job_id") val jobId: String,
    @SerializedName("job_number") val jobNumber: String,
    val description: String,
    @SerializedName("amount_cents") val amount: Int,
)
data class AccountStatement(
    @SerializedName("period_year") val year: Int,
    @SerializedName("period_month") val month: Int,
    val lines: List<AccountStatementLine>,
    @SerializedName("subtotal_cents") val subtotal: Int,
)
data class AccountInvoice(
    val id: String,
    @SerializedName("invoice_number") val number: String,
    @SerializedName("period_year") val year: Int,
    @SerializedName("period_month") val month: Int,
    val status: String,
    @SerializedName("subtotal_cents") val subtotal: Int,
    @SerializedName("tax_cents") val tax: Int,
    @SerializedName("total_cents") val total: Int,
    val currency: String,
    val lines: List<AccountStatementLine> = emptyList(),
)
data class AccountInvoiceCreate(
    @SerializedName("period_year") val year: Int,
    @SerializedName("period_month") val month: Int,
    @SerializedName("tax_cents") val tax: Int,
)
data class AccountMemberAdd(@SerializedName("customer_id") val customerId: String)
