package au.mainspring.nativeapp.ui

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/** The last few jobs opened on this device, newest first, stored as "service/id". Titles are resolved from the live job list. */
object RecentItems {
    private var preferences: android.content.SharedPreferences? = null
    private val mutable = MutableStateFlow<List<String>>(emptyList())
    val items = mutable.asStateFlow()
    fun init(context: Context) {
        if(preferences != null) return
        preferences = context.applicationContext.getSharedPreferences("mainspring_recent", Context.MODE_PRIVATE)
        mutable.value = preferences?.getString("jobs", "").orEmpty().split(',').filter { it.contains('/') }
    }
    fun record(route: String?) {
        val key = when {
            route == null -> return
            route.startsWith("watchJob/") -> "watch/" + route.removePrefix("watchJob/")
            route.startsWith("shoeJob/") -> "shoe/" + route.removePrefix("shoeJob/")
            route.startsWith("autoKeyJob/") -> "auto_key/" + route.removePrefix("autoKeyJob/")
            else -> return
        }
        val next = (listOf(key) + mutable.value.filter { it != key }).take(8)
        mutable.value = next
        preferences?.edit()?.putString("jobs", next.joinToString(","))?.apply()
    }
}
