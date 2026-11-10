package au.mainspring.nativeapp

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Where a tapped notification goes. The server sends the web-style path of the related record
 * (backend/app/push.py push_path); this maps it to an in-app route, or null for anything unknown.
 */
object PushRoutes {
    private val ID = Regex("^[A-Za-z0-9-]{1,64}$")

    fun toRoute(path: String?): String? {
        if(path.isNullOrBlank()) return null
        val clean = path.trim().substringBefore('?').trimEnd('/')
        val wantsMessages = path.substringAfter('?', "").split('&').any { it == "tab=messages" }
        val parts = clean.split('/').filter { it.isNotEmpty() }
        if(clean == "/messages") {
            val query = path.substringAfter('?', "").split('&').mapNotNull { part ->
                val key = part.substringBefore('='); val value = part.substringAfter('=', "")
                val nativeKey = when(key) { "c" -> "conversation"; "network" -> "network"; "hub" -> "hub"; "tab" -> "tab"; else -> return@mapNotNull null }
                if(!ID.matches(value)) null else "$nativeKey=$value"
            }
            return "networkMessages" + if(query.isEmpty()) "" else "?" + query.joinToString("&")
        }
        return when {
            parts.size == 1 && parts[0] == "inbox" -> "inbox"
            parts.size == 1 && parts[0] == "invoices" -> "invoices"
            parts.size == 2 && ID.matches(parts[1]) -> when(parts[0]) {
                "jobs" -> "watchJob/${parts[1]}" + if(wantsMessages) "?tab=messages" else ""
                "shoe-repairs" -> "shoeJob/${parts[1]}" + if(wantsMessages) "?tab=messages" else ""
                "auto-key" -> if(wantsMessages) "messages/auto-key-jobs/${parts[1]}" else "autoKeyJob/${parts[1]}"
                else -> null
            }
            else -> null
        }
    }
}

/** A tapped notification waits here until the signed-in app shell has opened it. */
object PushRouteInbox {
    private val mutable = MutableStateFlow<String?>(null)
    val pending: StateFlow<String?> = mutable.asStateFlow()
    /** Returns true when the path maps to a screen and is now pending. */
    fun offer(path: String?): Boolean { val route = PushRoutes.toRoute(path) ?: return false; mutable.value = route; return true }
    fun consume(route: String) { if(mutable.value == route) mutable.value = null }
    fun clear() { mutable.value = null }
}
