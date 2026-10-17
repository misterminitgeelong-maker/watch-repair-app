package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName

data class PeriodReport(
    val period: String,
    @SerializedName("reference_date") val referenceDate: String,
    @SerializedName("period_start") val start: String,
    @SerializedName("period_end") val end: String,
    @SerializedName("jobs_opened") val jobs: Long,
    @SerializedName("watch_jobs_opened") val watchJobs: Long,
    @SerializedName("shoe_jobs_opened") val shoeJobs: Long,
    @SerializedName("auto_key_jobs_opened") val mobileJobs: Long,
    @SerializedName("customers_new") val customers: Long,
    val financials: PeriodFinancials,
    @SerializedName("sales_funnel") val funnel: PeriodFunnel,
    val operations: PeriodOperations,
)
data class PeriodFinancials(
    @SerializedName("billed_cents") val billed: Long,
    @SerializedName("revenue_cents") val revenue: Long,
    @SerializedName("cost_cents") val cost: Long,
    @SerializedName("gross_profit_cents") val profit: Long,
    @SerializedName("gross_margin_percent") val margin: Double,
)
data class PeriodFunnel(
    @SerializedName("quotes_sent") val sent: Long,
    @SerializedName("quotes_approved") val approved: Long,
    @SerializedName("quotes_declined") val declined: Long,
    @SerializedName("approval_rate_percent") val approvalRate: Double,
)
data class PeriodOperations(
    @SerializedName("work_minutes") val minutes: Long,
    @SerializedName("avg_revenue_per_job_cents") val averageRevenue: Long,
)
