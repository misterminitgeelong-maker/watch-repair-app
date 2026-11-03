package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.POST

/** Dispatch extras: day-before reminders and the pool base location. Obtain via ApiClient.service(DispatchExtrasApi::class.java). */
interface DispatchExtrasApi {
    @POST("v1/auto-key-jobs/day-before-reminders") suspend fun sendDayBeforeReminders(): ReminderResult
    @POST("v1/settings/dispatch-base-location") suspend fun setBaseLocation(@Body body: JsonObject): BaseLocation
}

data class ReminderResult(val sent: Int = 0)
data class BaseLocation(
    @SerializedName("base_lat") val lat: Double = 0.0, @SerializedName("base_lng") val lng: Double = 0.0,
    @SerializedName("ring_radius_km") val ringRadiusKm: Int = 10,
)
