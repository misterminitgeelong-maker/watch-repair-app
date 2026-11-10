package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import okhttp3.ResponseBody
import retrofit2.http.*

data class EngravingEvent(val id: String, val name: String, @SerializedName("event_date") val date: String? = null,
    val location: String? = null, @SerializedName("price_cents") val price: Int, @SerializedName("minutes_per_medal") val minutes: Int,
    val status: String, @SerializedName("sms_enabled") val sms: Boolean, @SerializedName("online_payments") val online: Boolean,
    @SerializedName("online_payments_ready") val onlineReady: Boolean = false, @SerializedName("public_url") val publicUrl: String,
    val stats: Map<String, Int> = emptyMap())
data class EngravingOrder(val id: String, @SerializedName("event_id") val eventId: String,
    @SerializedName("order_number") val number: String, @SerializedName("status_token") val token: String,
    @SerializedName("group_id") val group: String? = null, @SerializedName("ticket_number") val ticket: String? = null,
    @SerializedName("athlete_name") val athlete: String, val line2: String? = null, val place: String,
    val qty: Int, @SerializedName("medals_done") val done: Int, val phone: String? = null, val status: String, val paid: Boolean,
    @SerializedName("payment_method") val paymentMethod: String? = null, @SerializedName("amount_cents") val amount: Int,
    val source: String, val notes: String? = null, @SerializedName("ready_sms_status") val smsStatus: String? = null)
data class EngravingQueue(val event: EngravingEvent, val orders: List<EngravingOrder>)
interface EngravingApi {
    @GET("v1/engraving/events") suspend fun events(): List<EngravingEvent>
    @POST("v1/engraving/events") suspend fun createEvent(@Body fields: JsonObject): EngravingEvent
    @PATCH("v1/engraving/events/{id}") suspend fun updateEvent(@Path("id") id: String, @Body fields: JsonObject): EngravingEvent
    @GET("v1/engraving/events/{id}/queue") suspend fun queue(@Path("id") id: String): EngravingQueue
    @POST("v1/engraving/events/{id}/orders") suspend fun walkUp(@Path("id") id: String, @Body fields: JsonObject): EngravingOrder
    @PATCH("v1/engraving/orders/{id}") suspend fun updateOrder(@Path("id") id: String, @Body fields: JsonObject): EngravingOrder
    @POST("v1/engraving/orders/{id}/{action}") suspend fun action(@Path("id") id: String, @Path("action") action: String): EngravingOrder
    @GET("v1/engraving/events/{id}/export") suspend fun export(@Path("id") id: String, @Query("software") software: String, @Query("limit") limit: Int? = null): ResponseBody
}
