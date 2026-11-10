package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.PlacesApi
import au.mainspring.nativeapp.api.PlaceDetails
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.UUID

/**
 * Address autocomplete for the job address. The web uses the Google Places widget in the browser. The phone asks the
 * Mainspring server (which holds the Places key) and falls back to the platform geocoder when the server cannot help.
 */
interface AddressSuggester {
    suspend fun suggest(query: String): List<String>
    /** Upgrades a picked suggestion to its full address (suburb, state, postcode). Unchanged when there is nothing better. */
    suspend fun resolve(picked: String): String = picked
    /** Structured fields when the platform geocoder can resolve a selected address. */
    suspend fun resolvePlace(picked: String): PlaceDetails? = null
}

/** Builds an [AddressSuggester] from a lambda; resolving keeps the picked text as it is. */
fun AddressSuggester(suggest: suspend (String) -> List<String>): AddressSuggester = object : AddressSuggester {
    override suspend fun suggest(query: String): List<String> = suggest(query)
}

/** Bounding box around Australia and New Zealand to bias results the way the web restricts Places to au/nz. */
private const val SOUTH = -47.5; private const val WEST = 112.0; private const val NORTH = -9.0; private const val EAST = 179.0

object DeviceAddressSuggester : AddressSuggester {
    @Suppress("DEPRECATION")
    override suspend fun suggest(query: String): List<String> = withContext(Dispatchers.IO) {
        val context = TokenStore.context() ?: return@withContext emptyList()
        if(!android.location.Geocoder.isPresent()) return@withContext emptyList()
        try {
            android.location.Geocoder(context, java.util.Locale("en", "AU")).getFromLocationName(query.trim(), 5, SOUTH, WEST, NORTH, EAST).orEmpty()
                .mapNotNull { a -> a.getAddressLine(0)?.trim()?.takeIf(String::isNotEmpty) }.distinct()
        } catch(_: Exception) { emptyList() }
    }
    @Suppress("DEPRECATION")
    override suspend fun resolvePlace(picked: String): PlaceDetails? = withContext(Dispatchers.IO) {
        val context = TokenStore.context() ?: return@withContext null
        if(!android.location.Geocoder.isPresent()) return@withContext null
        try {
            android.location.Geocoder(context, java.util.Locale("en", "AU")).getFromLocationName(picked, 1, SOUTH, WEST, NORTH, EAST)?.firstOrNull()?.let { address ->
                PlaceDetails(address.getAddressLine(0) ?: picked, address.locality ?: address.subLocality, australianStateCode(address.adminArea), address.postalCode, address.latitude, address.longitude)
            }
        } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
    }
}

/** Android geocoders may return either a state name or its two/three-letter abbreviation. */
fun australianStateCode(value: String?): String? = when(value?.trim()?.uppercase(java.util.Locale.ROOT)) {
    "ACT", "AUSTRALIAN CAPITAL TERRITORY" -> "ACT"; "NSW", "NEW SOUTH WALES" -> "NSW"; "NT", "NORTHERN TERRITORY" -> "NT"
    "QLD", "QUEENSLAND" -> "QLD"; "SA", "SOUTH AUSTRALIA" -> "SA"; "TAS", "TASMANIA" -> "TAS"
    "VIC", "VICTORIA" -> "VIC"; "WA", "WESTERN AUSTRALIA" -> "WA"; else -> null
}

/**
 * Web-quality suggestions from `GET v1/places/autocomplete`, with the device geocoder as the fallback.
 * An unconfigured server (503) is not asked again for ten minutes, and a failed request falls back for half a minute,
 * so typing never waits on a server that cannot answer.
 */
class ServerAddressSuggester(
    private val places: () -> PlacesApi = { ApiClient.service(PlacesApi::class.java) },
    private val fallback: AddressSuggester = DeviceAddressSuggester,
    private val now: () -> Long = System::currentTimeMillis,
) : AddressSuggester {
    private var session = newSession()
    private val placeIds = HashMap<String, String>()
    private var serverUnavailableUntil = 0L

    private fun newSession() = UUID.randomUUID().toString()

    override suspend fun suggest(query: String): List<String> {
        if(now() < serverUnavailableUntil) return fallback.suggest(query)
        return try {
            val rows = places().autocomplete(query.trim(), session).suggestions
            rows.forEach { placeIds[it.description] = it.placeId }
            rows.map { it.description }.distinct()
        } catch(e: CancellationException) { throw e }
        catch(e: retrofit2.HttpException) {
            serverUnavailableUntil = now() + if(e.code() == 503) TEN_MINUTES else HALF_MINUTE
            fallback.suggest(query)
        } catch(e: Exception) {
            serverUnavailableUntil = now() + HALF_MINUTE
            fallback.suggest(query)
        }
    }

    override suspend fun resolve(picked: String): String {
        val placeId = placeIds[picked] ?: return picked
        return try {
            places().details(placeId, session).formattedAddress.trim().ifEmpty { picked }
        } catch(e: CancellationException) { throw e }
        catch(_: Exception) { picked }
        finally { session = newSession(); placeIds.clear() } // a picked address ends the billing session
    }

    private companion object { const val TEN_MINUTES = 10 * 60_000L; const val HALF_MINUTE = 30_000L }
}
