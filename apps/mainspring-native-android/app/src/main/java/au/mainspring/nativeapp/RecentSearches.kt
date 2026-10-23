package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.SearchHit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** The last results a person opened from search, newest first, in memory for the app session (web `lib/recentSearch.ts`, MAX 8). */
object RecentSearches {
    const val MAX = 8
    private val mutable = MutableStateFlow<List<SearchHit>>(emptyList())
    val hits: StateFlow<List<SearchHit>> = mutable.asStateFlow()

    fun push(hit: SearchHit) { mutable.value = pushRecent(mutable.value, hit) }
    fun clear() { mutable.value = emptyList() }
}

/** Puts [hit] first, drops an older copy of the same kind and id, and caps the list. */
fun pushRecent(existing: List<SearchHit>, hit: SearchHit, max: Int = RecentSearches.MAX): List<SearchHit> =
    (listOf(hit) + existing.filterNot { it.kind == hit.kind && it.id == hit.id }).take(max)
