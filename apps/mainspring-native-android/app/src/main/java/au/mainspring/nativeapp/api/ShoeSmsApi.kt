package au.mainspring.nativeapp.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

/** Body for POST /v1/shoe-repair-jobs/{id}/resend-notification; event is `job_live` or `status_<status>`. */
data class ShoeResendRequest(val event: String)

/** SMS log and resend for shoe repair jobs (mirrors the watch calls on [MainspringApi]). */
interface ShoeSmsApi {
    @GET("v1/shoe-repair-jobs/{jobId}/sms-log") suspend fun shoeSmsLog(@Path("jobId") jobId: String): List<SmsLogRead>
    @POST("v1/shoe-repair-jobs/{jobId}/resend-notification")
    suspend fun resendShoeNotification(@Path("jobId") jobId: String, @Body body: ShoeResendRequest): SmsLogRead
}
