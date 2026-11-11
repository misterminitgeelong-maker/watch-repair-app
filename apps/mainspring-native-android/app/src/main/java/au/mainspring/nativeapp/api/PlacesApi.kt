package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Query

data class PlaceSuggestion(
    @SerializedName("place_id") val placeId: String,
    val description: String,
    @SerializedName("primary_text") val primaryText: String? = null,
    @SerializedName("secondary_text") val secondaryText: String? = null,
)
data class PlaceSuggestionList(val suggestions: List<PlaceSuggestion> = emptyList())
data class PlaceDetails(
    @SerializedName("formatted_address") val formattedAddress: String,
    val suburb: String? = null,
    @SerializedName("state_code") val stateCode: String? = null,
    val postcode: String? = null,
    val lat: Double? = null, val lng: Double? = null,
)

/** Server-side Google Places proxy (`backend/app/routes/places.py`): the phone never holds a Places key. */
interface PlacesApi {
    @GET("v1/places/autocomplete") suspend fun autocomplete(@Query("q") query: String, @Query("session") session: String): PlaceSuggestionList
    @GET("v1/places/details") suspend fun details(@Query("place_id") placeId: String, @Query("session") session: String): PlaceDetails
}
