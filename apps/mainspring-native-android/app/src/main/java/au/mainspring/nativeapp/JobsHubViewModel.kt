package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.canonicalMobileStatus
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** One row of the unified Jobs list: a watch, shoe or mobile-services job. */
data class HubJob(
    val id: String, val service: String, val number: String, val title: String, val customer: String?,
    val status: String, val urgent: Boolean, val dueDate: String?, val assignedToMe: Boolean, val sortKey: String, val createdAt: String = "",
) {
    val ready get() = status in READY_STATUSES
    val active get() = when(service) { "watch" -> !isWatchCompleted(status); "shoe" -> status !in SHOE_CLOSED_STATUSES; else -> canonicalMobileStatus(status) !in DONE_STATUSES }
    val needsAttention get() = status in ATTENTION_STATUSES
    companion object {
        val READY_STATUSES = setOf("awaiting_collection", "work_completed", "completed")
        /** Canonical closed mobile statuses (backend AUTO_KEY_FINAL_STATUSES after alias folding); callers pass `canonicalMobileStatus(status)`. */
        val DONE_STATUSES = setOf("work_completed", "invoice_paid", "no_go", "failed_job")
        val ATTENTION_STATUSES = setOf("awaiting_collection", "awaiting_go_ahead", "quote_sent", "awaiting_quote", "awaiting_parts", "work_completed", "job_delayed")
    }
}

data class JobsHubState(
    val loading: Boolean = false, val error: String? = null, val jobs: List<HubJob> = emptyList(),
    val query: String = "", val segment: String = "active", val service: String = "all", val sort: String = "default",
) {
    val visible: List<HubJob> get() {
        val q = query.trim()
        return jobs.filter { j ->
            (service == "all" || j.service == service) &&
            when(segment) { "mine" -> j.assignedToMe && j.active; "ready" -> j.ready; else -> j.active } &&
            (q.isEmpty() || listOf(j.title, j.number, j.customer.orEmpty()).any { it.contains(q, ignoreCase = true) })
        }.let { sortHubJobs(it, sort) }
    }
    val activeCount get() = jobs.count { it.active }
    val mineCount get() = jobs.count { it.assignedToMe && it.active }
    val readyCount get() = jobs.count { it.ready }
}

const val HUB_PAGE_SIZE = 200
const val HUB_MAX_PAGES = 5

/** Fetches consecutive pages until one comes back short, up to [maxPages]; any page failure fails the whole lane. */
suspend fun <T> fetchAllPages(pageSize: Int, maxPages: Int, fetch: suspend (offset: Int) -> List<T>): List<T> {
    val all = ArrayList<T>()
    for(page in 0 until maxPages) {
        val chunk = fetch(page * pageSize)
        all += chunk
        if(chunk.size < pageSize) break
    }
    return all
}

/** Names the lanes that failed, or null when every lane loaded, for the existing hub error banner. */
fun hubPartialError(failedLanes: List<String>): String? =
    if(failedLanes.isEmpty()) null else "Couldn't load ${failedLanes.joinToString(" or ")} jobs, so counts and lists may be incomplete. Pull to refresh to retry."

class JobsHubViewModel(private val services: Set<String> = setOf("watch", "shoe", "auto_key")) : ViewModel() {
    private val api = ApiClient.api
    private val _state = MutableStateFlow(JobsHubState())
    val state: StateFlow<JobsHubState> = _state.asStateFlow()
    init { refresh() }

    fun setQuery(value: String) { _state.update { it.copy(query = value) } }
    fun setSegment(value: String) { _state.update { it.copy(segment = value) } }
    fun setService(value: String) { _state.update { it.copy(service = value) } }
    fun setSort(value: String) { _state.update { it.copy(sort = value) } }

    /** One service lane: null when it failed (cancellation still propagates) so the others can still render. */
    private suspend fun <T> lane(block: suspend () -> List<T>): List<T>? =
        try { block() } catch(e: CancellationException) { throw e } catch(e: Exception) { null }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val me = TokenStore.currentUserId()
                var partial: String? = null
                val rows = coroutineScope {
                    val watch = async { if("watch" in services) lane { fetchAllPages(HUB_PAGE_SIZE, HUB_MAX_PAGES) { o -> api.listRepairJobs(limit = HUB_PAGE_SIZE, offset = o) } } else emptyList() }
                    val shoe = async { if("shoe" in services) lane { fetchAllPages(HUB_PAGE_SIZE, HUB_MAX_PAGES) { o -> api.listShoeRepairJobs(skip = o, limit = HUB_PAGE_SIZE) } } else emptyList() }
                    val mobile = async { if("auto_key" in services) lane { fetchAllPages(HUB_PAGE_SIZE, HUB_MAX_PAGES) { o -> api.listAutoKeyJobs(skip = o, limit = HUB_PAGE_SIZE) } } else emptyList() }
                    val w = watch.await(); val s = shoe.await(); val m = mobile.await()
                    if(w == null && s == null && m == null) throw java.io.IOException("jobs unavailable")
                    partial = hubPartialError(listOfNotNull(if(w == null) "watch" else null, if(s == null) "shoe" else null, if(m == null) "mobile" else null))
                    (w.orEmpty().map { HubJob(it.id, "watch", it.jobNumber, it.title, it.customerName, it.status, it.priority in listOf("urgent", "high"), it.collectionDate,
                        me.isNotBlank() && (it.claimedByUserId == me || it.assignedUserId == me), (it.collectionDate ?: "9999") + it.jobNumber, it.createdAt) } +
                    s.orEmpty().map { HubJob(it.id, "shoe", it.jobNumber, it.title, null, it.status, it.priority in listOf("urgent", "high"), it.collectionDate,
                        me.isNotBlank() && it.assignedUserId == me, (it.collectionDate ?: "9999") + it.jobNumber, it.createdAt) } +
                    m.orEmpty().map { HubJob(it.id, "auto_key", it.jobNumber, it.title, it.customerName, it.status, it.priority in listOf("urgent", "high"), serverShopDate(it.scheduledAt)?.toString(),
                        me.isNotBlank() && it.assignedUserId == me, (serverShopDate(it.scheduledAt)?.toString() ?: "9999") + it.jobNumber, it.createdAt) })
                }
                _state.update { it.copy(loading = false, jobs = rows, error = partial) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
