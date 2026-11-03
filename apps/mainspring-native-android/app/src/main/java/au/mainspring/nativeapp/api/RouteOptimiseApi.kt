package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.POST

/** Driving-order optimisation (Google Directions, server side). Obtain via ApiClient.service(RouteOptimiseApi::class.java). */
interface RouteOptimiseApi {
    @POST("v1/maps/optimize-driving-route") suspend fun optimise(@Body body: OptimiseRouteBody): OptimiseRouteResult
}

data class LatLngBody(val lat: Double, val lng: Double)
data class OptimiseRouteBody(val stops: List<LatLngBody>)
data class OptimiseRouteResult(@SerializedName("visit_order") val visitOrder: List<Int> = emptyList(), val source: String = "")
