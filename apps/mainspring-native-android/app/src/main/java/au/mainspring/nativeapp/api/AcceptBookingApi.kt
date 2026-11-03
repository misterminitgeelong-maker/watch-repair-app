package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Path

/** Accepts one shop mobile booking request (web: ShopBookingInbox `acceptMut`). Same endpoint the booking list uses. */
interface AcceptBookingApi {
    @POST("v1/shop-mobile-bookings/{id}/accept") suspend fun accept(@Path("id") id: String, @Body body: JsonObject = JsonObject()): BookingRequest
}
