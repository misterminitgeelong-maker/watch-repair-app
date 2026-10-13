package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
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
    val status: String, val urgent: Boolean, val dueDate: String?, val assignedToMe: Boolean, val sortKey: String,
) {
    val ready get() = status in READY_STATUSES
    val active get() = status !in DONE_STATUSES
    val needsAttention get() = status in ATTENTION_STATUSES
    companion object {
        val READY_STATUSES = setOf("awaiting_collection", "work_completed", "completed")
        val DONE_STATUSES = setOf("collected", "invoice_paid", "paid", "no_go", "failed_job")
        val ATTENTION_STATUSES = setOf("awaiting_collection", "awaiting_go_ahead", "quote_sent", "awaiting_quote", "awaiting_parts", "work_completed", "job_delayed")
    }
}

data class JobsHubState(
    val loading: Boolean = false, val error: String? = null, val jobs: List<HubJob> = emptyList(),
    val query: String = "", val segment: String = "active", val service: String = "all",
) {
    val visible: List<HubJob> get() {
        val q = query.trim()
        return jobs.filter { j ->
            (service == "all" || j.service == service) &&
            when(segment) { "mine" -> j.assignedToMe && j.active; "ready" -> j.ready; else -> j.active } &&
            (q.isEmpty() || listOf(j.title, j.number, j.customer.orEmpty()).any { it.contains(q, ignoreCase = true) })
        }.sortedBy { it.sortKey }
    }
    val activeCount get() = jobs.count { it.active }
    val mineCount get() = jobs.count { it.assignedToMe && it.active }
    val readyCount get() = jobs.count { it.ready }
}

class JobsHubViewModel(private val services: Set<String> = setOf("watch", "shoe", "auto_key")) : ViewModel() {
    private val api = ApiClient.api
    private val _state = MutableStateFlow(JobsHubState())
    val state: StateFlow<JobsHubState> = _state.asStateFlow()
    init { refresh() }

    fun setQuery(value: String) { _state.update { it.copy(query = value) } }
    fun setSegment(value: String) { _state.update { it.copy(segment = value) } }
    fun setService(value: String) { _state.update { it.copy(service = value) } }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val me = TokenStore.currentUserId()
                val rows = coroutineScope {
                    val watch = async { if("watch" in services) runCatching { api.listRepairJobs(limit = 200) }.getOrNull() else emptyList() }
                    val shoe = async { if("shoe" in services) runCatching { api.listShoeRepairJobs(limit = 200) }.getOrNull() else emptyList() }
                    val mobile = async { if("auto_key" in services) runCatching { api.listAutoKeyJobs(limit = 200) }.getOrNull() else emptyList() }
                    val w = watch.await(); val s = shoe.await(); val m = mobile.await()
                    if(w == null && s == null && m == null) throw java.io.IOException("jobs unavailable")
                    (w.orEmpty().map { HubJob(it.id, "watch", it.jobNumber, it.title, it.customerName, it.status, it.priority in listOf("urgent", "high"), it.collectionDate,
                        me.isNotBlank() && it.claimedByUserId == me, (it.collectionDate ?: "9999") + it.jobNumber) } +
                    s.orEmpty().map { HubJob(it.id, "shoe", it.jobNumber, it.title, null, it.status, it.priority in listOf("urgent", "high"), it.collectionDate,
                        me.isNotBlank() && it.assignedUserId == me, (it.collectionDate ?: "9999") + it.jobNumber) } +
                    m.orEmpty().map { HubJob(it.id, "auto_key", it.jobNumber, it.title, it.customerName, it.status, it.priority in listOf("urgent", "high"), it.scheduledAt?.take(10),
                        me.isNotBlank() && it.assignedUserId == me, (it.scheduledAt?.take(10) ?: "9999") + it.jobNumber) })
                }
                _state.update { it.copy(loading = false, jobs = rows) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
