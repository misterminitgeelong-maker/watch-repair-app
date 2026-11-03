package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.SearchApi
import au.mainspring.nativeapp.api.SearchHit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SearchUiState(
    val query: String = "",
    val loading: Boolean = false,
    val error: String? = null,
    /** True once a request for the current query has completed (so "no results" is only shown after a search). */
    val searched: Boolean = false,
    val hits: List<SearchHit> = emptyList(),
) {
    val jobs get() = hits.filter { it.kind == "repair_job" || it.kind == "shoe_repair_job" || it.kind == "auto_key_job" }
    val customers get() = hits.filter { it.kind == "customer" }
    val invoices get() = hits.filter { it.kind == "invoice" }
}

/** Native route for a hit, or null for kinds the app cannot open. */
fun searchRoute(hit: SearchHit): String? = when (hit.kind) {
    "repair_job" -> "watchJob/${hit.id}"
    "shoe_repair_job" -> "shoeJob/${hit.id}"
    "auto_key_job" -> "autoKeyJob/${hit.id}"
    "customer" -> "customer/${hit.id}"
    "invoice" -> "invoice/${hit.id}"
    else -> null
}.takeIf { hit.id.isNotBlank() }

class SearchViewModel : ViewModel() {
    companion object { const val DEBOUNCE_MS = 300L; const val MIN_CHARS = 2 }

    private val mutable = MutableStateFlow(SearchUiState())
    val state = mutable.asStateFlow()
    private var request: Job? = null

    fun setQuery(value: String) {
        request?.cancel()
        val trimmed = value.trim()
        if (trimmed.length < MIN_CHARS) {
            mutable.value = SearchUiState(query = value)
            return
        }
        mutable.update { it.copy(query = value, loading = true, error = null, searched = false) }
        request = viewModelScope.launch {
            try {
                delay(DEBOUNCE_MS)
                val res = ApiClient.service(SearchApi::class.java).search(trimmed)
                val hits = res.hits.orEmpty().filter { searchRoute(it) != null }
                mutable.update { it.copy(loading = false, hits = hits, searched = true) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                mutable.update { it.copy(loading = false, hits = emptyList(), searched = false, error = e.userMessage()) }
            }
        }
    }
}
