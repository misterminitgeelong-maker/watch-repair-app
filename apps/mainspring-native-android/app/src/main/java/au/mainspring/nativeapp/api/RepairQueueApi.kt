package au.mainspring.nativeapp.api

import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Path

/** `direction`: "right" moves a watch job one step along the queue lane, "left" one step back. */
data class QueueSwipeBody(val direction: String)

/** Watch repair queue swipe triage (mirrors web `repairJobQueueSwipe`); status-only, no SMS or email. */
interface RepairQueueApi {
    @POST("v1/repair-jobs/{id}/queue-swipe")
    suspend fun queueSwipe(@Path("id") id: String, @Body body: QueueSwipeBody): RepairJobRead
}
