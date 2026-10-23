package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import okhttp3.ResponseBody
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Streaming

/** One technician row from GET /v1/reports/tech-breakdown (all-time logged work). */
data class TechBreakdownRow(
    @SerializedName("user_id") val userId: String = "",
    @SerializedName("user_name") val userName: String = "",
    @SerializedName("total_minutes") val totalMinutes: Int = 0,
    @SerializedName("jobs_count") val jobsCount: Int = 0,
)

data class TrendMonth(
    val month: String = "",
    @SerializedName("jobs_opened") val jobsOpened: Int = 0,
    @SerializedName("revenue_cents") val revenueCents: Long = 0,
)

data class TrendsResponse(val months: List<TrendMonth> = emptyList())

/**
 * Report endpoints that accept either a calendar [period] + [referenceDate] or a custom
 * [dateFrom]/[dateTo] range (the server ignores the range when period is set). Manager+ except tech-breakdown/trends.
 */
interface ReportBreakdownApi {
    @GET("v1/reports/category-summary")
    suspend fun categorySummary(
        @Query("period") period: String?, @Query("reference_date") referenceDate: String?,
        @Query("date_from") dateFrom: String?, @Query("date_to") dateTo: String?,
    ): CategorySummary

    @Streaming @GET("v1/reports/export/sales")
    suspend fun exportSales(
        @Query("category") category: String,
        @Query("period") period: String?, @Query("reference_date") referenceDate: String?,
        @Query("date_from") dateFrom: String?, @Query("date_to") dateTo: String?,
    ): ResponseBody

    @GET("v1/reports/gst-summary")
    suspend fun gstSummary(
        @Query("period") period: String?, @Query("reference_date") referenceDate: String?,
        @Query("date_from") dateFrom: String?, @Query("date_to") dateTo: String?,
    ): GstSummaryResponse

    @GET("v1/reports/tech-breakdown") suspend fun techBreakdown(): List<TechBreakdownRow>
    @GET("v1/reports/trends") suspend fun trends(@Query("months") months: Int): TrendsResponse
}
