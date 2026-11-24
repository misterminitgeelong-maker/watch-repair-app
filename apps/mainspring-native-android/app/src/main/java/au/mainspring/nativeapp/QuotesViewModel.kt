package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.QuoteRead
import au.mainspring.nativeapp.data.QuoteNavCache
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class QuotesUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val quotes: List<QuoteRead> = emptyList(),
    val jobs: Map<String, au.mainspring.nativeapp.api.RepairJobRead> = emptyMap(),
    /** True when the server may hold more quotes than were fetched (a full page came back). */
    val truncated: Boolean = false,
)

/** The most quotes the backend returns per request. */
internal const val QUOTES_PAGE_LIMIT = 500

/** Sort keys: "newest", "oldest", "amount". `olderThanDays` > 0 keeps only quotes sent at least that many days ago (web parity). */
fun visibleQuotes(state: QuotesUiState, status: String?, query: String, sort: String, olderThanDays: Int, now: Long = System.currentTimeMillis()): List<QuoteRead> {
    val term = query.trim().lowercase()
    val cutoff = now - olderThanDays * 86_400_000L
    val rows = state.quotes.filter { q ->
        val job = state.jobs[q.repairJobId]
        (status == null || q.status == status) &&
            (olderThanDays <= 0 || (q.sentAt?.let { s -> (au.mainspring.nativeapp.parseServerInstant(s)?.toEpochMilli()?.let { it <= cutoff } ?: false) } ?: false)) &&
            (term.isEmpty() || listOf(q.jobNumber ?: job?.jobNumber, job?.title, q.customerName ?: job?.customerName).any { (it ?: "").lowercase().contains(term) })
    }
    return when (sort) {
        "oldest" -> rows.sortedBy { it.createdAt }
        "amount" -> rows.sortedByDescending { it.totalCents }
        else -> rows.sortedByDescending { it.createdAt }
    }
}

class QuotesViewModel : ViewModel() {
    private val generation = au.mainspring.nativeapp.TokenStore.sessionGeneration()
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val _state = MutableStateFlow(QuotesUiState())
    val state: StateFlow<QuotesUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = api.listQuotes(limit = QUOTES_PAGE_LIMIT)
                QuoteNavCache.putAll(list,generation)
                _state.update { it.copy(loading = false, quotes = list, truncated = list.size >= QUOTES_PAGE_LIMIT) }
                runCatching { api.listRepairJobs(limit = 200) }.getOrNull()?.let { jobs -> _state.update { it.copy(jobs = jobs.associateBy { job -> job.id }) } }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }
}
