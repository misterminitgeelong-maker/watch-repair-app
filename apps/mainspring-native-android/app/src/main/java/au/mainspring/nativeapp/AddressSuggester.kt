package au.mainspring.nativeapp

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Address autocomplete for the job address. The web uses the Google Places widget in the browser; there is no backend
 * suggestions endpoint, so the phone asks the platform geocoder (no API key, nothing sent to Mainspring servers).
 */
fun interface AddressSuggester {
    suspend fun suggest(query: String): List<String>
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
}
