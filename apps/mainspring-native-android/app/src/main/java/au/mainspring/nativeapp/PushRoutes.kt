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
        val parts = clean.split('/').filter { it.isNotEmpty() }
        return when {
            parts.size == 1 && parts[0] == "inbox" -> "inbox"
            parts.size == 1 && parts[0] == "invoices" -> "invoices"
            parts.size == 2 && ID.matches(parts[1]) -> when(parts[0]) {
                "jobs" -> "watchJob/${parts[1]}"
                "shoe-repairs" -> "shoeJob/${parts[1]}"
                "auto-key" -> "autoKeyJob/${parts[1]}"
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
