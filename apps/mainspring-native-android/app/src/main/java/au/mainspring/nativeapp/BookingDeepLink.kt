package au.mainspring.nativeapp

import java.net.URI
import java.net.URLDecoder
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Deep link into the booking-accept flow. The backend's live booking SMS/email links to
 * `{public_base_url}/auto-key?accept_booking=<id>`; the app also accepts `mainspring://booking/accept?id=<id>`
 * and `mainspring://auto-key?accept_booking=<id>`.
 */
data class AcceptBookingLink(val bookingId: String)

object BookingDeepLink {
    /** Web hosts whose links the manifest intent filter claims. Keep in sync with AndroidManifest.xml. */
    val WEB_HOSTS = setOf("mainspring.au", "www.mainspring.au")
    const val SCHEME = "mainspring"
    const val ROUTE_PATTERN = "acceptBooking/{id}"
    fun route(bookingId: String) = "acceptBooking/$bookingId"

    private val SAFE_ID = Regex("^[A-Za-z0-9_-]{1,64}$")

    /** Pure parser for an incoming Uri string (`intent.data?.toString()`). Returns null for anything that is not an accept-booking link. */
    fun parse(uri: String?, webHosts: Set<String> = WEB_HOSTS): AcceptBookingLink? {
        if(uri.isNullOrBlank()) return null
        val u = try { URI(uri.trim()) } catch(_: Exception) { return null }
        val scheme = u.scheme?.lowercase() ?: return null
        val host = u.host?.lowercase() ?: return null
        val path = u.rawPath.orEmpty().trimEnd('/')
        val query = queryParams(u.rawQuery)
        val id = when(scheme) {
            "https" -> {
                if(host !in webHosts.map { it.lowercase() }) return null
                if(path != "/auto-key") return null
                query["accept_booking"]
            }
            SCHEME -> when(host) {
                "booking" -> if(path == "/accept") query["id"] ?: query["accept_booking"] else null
                "auto-key" -> if(path.isEmpty()) query["accept_booking"] else null
                else -> null
            }
            else -> null
        }
        return id?.trim()?.takeIf { SAFE_ID.matches(it) }?.let(::AcceptBookingLink)
    }

    private fun queryParams(raw: String?): Map<String, String> {
        if(raw.isNullOrEmpty()) return emptyMap()
        val out = LinkedHashMap<String, String>()
        for(pair in raw.split('&')) {
            if(pair.isEmpty()) continue
            val i = pair.indexOf('=')
            val k = decode(if(i < 0) pair else pair.substring(0, i)); val v = if(i < 0) "" else decode(pair.substring(i + 1))
            if(k !in out) out[k] = v
        }
        return out
    }
    private fun decode(s: String) = try { URLDecoder.decode(s, "UTF-8") } catch(_: Exception) { s }
}

/**
 * Holds one not-yet-handled deep link between MainActivity (which receives the intent, possibly before sign-in)
 * and the signed-in shell (which navigates and then calls [consume]).
 */
object DeepLinkInbox {
    private val mutable = MutableStateFlow<AcceptBookingLink?>(null)
    val pending: StateFlow<AcceptBookingLink?> = mutable.asStateFlow()
    /** Returns true when [uri] was an accept-booking link and is now pending. */
    fun offer(uri: String?): Boolean { val link = BookingDeepLink.parse(uri) ?: return false; mutable.value = link; return true }
    fun consume(link: AcceptBookingLink) { if(mutable.value == link) mutable.value = null }
    fun clear() { mutable.value = null }
}
