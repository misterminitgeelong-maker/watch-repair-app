package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** `direction`: "right" moves a watch job one step along the queue lane, "left" one step back. */
data class QueueSwipeBody(val direction: String)

/** Counters saved with a queue day (`GET/PUT /me/repair-queue-day`); the keys match the web app. */
data class QueueDayStatsDto(val advanced: Int = 0, val checkedIn: Int = 0, val skipped: Int = 0)

/** The signed-in user's queue progress for the tenant's current shop day. */
data class RepairQueueDayRead(
    @SerializedName("shop_date") val shopDate: String? = null,
    val mode: String? = null,
    @SerializedName("done_ids") val doneIds: List<String> = emptyList(),
    @SerializedName("queue_order_ids") val queueOrderIds: List<String> = emptyList(),
    val stats: QueueDayStatsDto = QueueDayStatsDto(),
)

data class RepairQueueDayPut(
    val mode: String,
    @SerializedName("done_ids") val doneIds: List<String>,
    @SerializedName("queue_order_ids") val queueOrderIds: List<String>,
    val stats: QueueDayStatsDto,
)

/** Watch repair queue swipe triage (mirrors web `repairJobQueueSwipe`); status-only, no SMS or email. */
interface RepairQueueApi {
    @POST("v1/repair-jobs/{id}/queue-swipe")
    suspend fun queueSwipe(@Path("id") id: String, @Body body: QueueSwipeBody): RepairJobRead

    /** Per-user "done today" ids, queue order and stats for [mode] (`watch` or `shoe`); an empty day when nothing is saved. */
    @GET("v1/me/repair-queue-day")
    suspend fun queueDay(@Query("mode") mode: String): RepairQueueDayRead

    @PUT("v1/me/repair-queue-day")
    suspend fun putQueueDay(@Body body: RepairQueueDayPut): RepairQueueDayRead

    /** Forgets today's saved progress for [mode] (web "Reset today's queue progress"). */
    @DELETE("v1/me/repair-queue-day")
    suspend fun deleteQueueDay(@Query("mode") mode: String): Response<Unit>
}
