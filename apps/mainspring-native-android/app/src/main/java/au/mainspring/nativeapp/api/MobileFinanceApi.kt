package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import okhttp3.ResponseBody
import retrofit2.http.GET
import retrofit2.http.Query

/** Mobile services operations cockpit and finance report (read-only). Obtain via ApiClient.service(MobileFinanceApi::class.java). */
interface MobileFinanceApi {
    @GET("v1/reports/auto-key/cockpit") suspend fun cockpit(@Query("items") items: Int = 5): MobileCockpitResponse
    @GET("v1/reports/auto-key/finance") suspend fun finance(@Query("period") period: String): MobileFinanceResponse
    @retrofit2.http.Streaming @GET("v1/reports/auto-key/finance/export")
    suspend fun financeExport(@Query("period") period: String, @Query("kind") kind: String): ResponseBody
}

data class CockpitJob(
    val id: String = "", @SerializedName("job_number") val jobNumber: String = "", val title: String = "",
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("scheduled_at") val scheduledAt: String? = null,
    @SerializedName("assigned_name") val assignedName: String? = null,
)
data class CockpitQueue(val key: String = "", val label: String = "", val count: Int = 0, val items: List<CockpitJob> = emptyList())
data class CockpitMetric(
    val key: String = "", val label: String = "", val unit: String = "count", val current: Double? = null,
    val previous: Double? = null, val target: Double? = null, val partial: Boolean = false,
)
data class CockpitAgingCents(val current: Long = 0, @SerializedName("d8_30") val d8To30: Long = 0, @SerializedName("d31_plus") val d31Plus: Long = 0)
data class CockpitAgingCounts(val current: Int = 0, @SerializedName("d8_30") val d8To30: Int = 0, @SerializedName("d31_plus") val d31Plus: Int = 0)
data class CockpitOutstanding(
    val current: Long = 0, val count: Int = 0, @SerializedName("overdue_cents") val overdueCents: Long = 0,
    @SerializedName("aging_cents") val agingCents: CockpitAgingCents = CockpitAgingCents(),
    @SerializedName("aging_counts") val agingCounts: CockpitAgingCounts = CockpitAgingCounts(),
)
data class CockpitCapacity(
    val technicians: Int = 0, @SerializedName("capacity_minutes") val capacityMinutes: Int = 0,
    @SerializedName("booked_minutes") val bookedMinutes: Int = 0, @SerializedName("available_minutes") val availableMinutes: Int = 0,
    val conflicts: Int = 0, @SerializedName("unassigned_today") val unassignedToday: Int = 0,
)
data class CockpitFollowUp(val count: Int = 0, @SerializedName("value_cents") val valueCents: Long = 0)
data class CockpitFollowUps(
    val quotes: CockpitFollowUp = CockpitFollowUp(), val confirmations: CockpitFollowUp = CockpitFollowUp(),
    @SerializedName("completed_unpaid") val completedUnpaid: CockpitFollowUp = CockpitFollowUp(),
    @SerializedName("overdue_invoices") val overdueInvoices: CockpitFollowUp = CockpitFollowUp(),
)
data class MobileCockpitResponse(
    val attention: List<CockpitQueue> = emptyList(), val metrics: List<CockpitMetric> = emptyList(),
    val outstanding: CockpitOutstanding = CockpitOutstanding(), val capacity: CockpitCapacity = CockpitCapacity(),
    @SerializedName("follow_ups") val followUps: CockpitFollowUps = CockpitFollowUps(),
    @SerializedName("weekly_target_cents") val weeklyTargetCents: Long? = null,
)

data class FinanceMetric(val key: String = "", val label: String = "", val unit: String = "count", val current: Double? = null, val previous: Double? = null)
data class FinancePeriod(val label: String = "", val start: String = "", val end: String = "", val complete: Boolean = true)
data class FinanceTarget(
    @SerializedName("period_cents") val periodCents: Long = 0, @SerializedName("collected_cents") val collectedCents: Long = 0,
    @SerializedName("attainment_pct") val attainmentPct: Double? = null,
)
data class FinanceConversion(
    val key: String = "", val label: String = "", val numerator: Int = 0, val denominator: Int = 0,
    val pct: Double? = null, @SerializedName("previous_pct") val previousPct: Double? = null,
)
data class FinanceBucket(val key: String = "", val label: String = "", val cents: Long = 0, val count: Int = 0)
data class FinanceAgeing(
    @SerializedName("total_cents") val totalCents: Long = 0, @SerializedName("overdue_cents") val overdueCents: Long = 0,
    val buckets: List<FinanceBucket> = emptyList(),
)
data class FinanceTech(
    val name: String = "", @SerializedName("jobs_completed") val jobsCompleted: Int = 0,
    @SerializedName("invoiced_cents") val invoicedCents: Long = 0, @SerializedName("collected_cents") val collectedCents: Long = 0,
    @SerializedName("utilisation_pct") val utilisationPct: Double? = null,
)
data class FinanceQuality(val message: String = "")
data class MobileFinanceResponse(
    val period: FinancePeriod = FinancePeriod(), val metrics: List<FinanceMetric> = emptyList(), val target: FinanceTarget? = null,
    val conversion: List<FinanceConversion> = emptyList(), @SerializedName("ar_ageing") val arAgeing: FinanceAgeing = FinanceAgeing(),
    val technicians: List<FinanceTech> = emptyList(), @SerializedName("data_quality") val dataQuality: List<FinanceQuality> = emptyList(),
)
