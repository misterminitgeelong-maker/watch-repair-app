package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ShoeJobsUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val jobs: List<ShoeRepairJobRead> = emptyList(),
    val canLoadMore: Boolean = false,
    val query: String = "",
    val statusFilter: String = "all",
    val showCompleted: Boolean = false,
    val customerNames: Map<String, String> = emptyMap(),
    val board: Boolean = false,
    val movingId: String? = null,
    val savedViews: List<SavedJobView> = emptyList(),
) {
    /** Search-filtered jobs across every status, for the board. */
    val boardJobs: List<ShoeRepairJobRead> get() {
        val q = query.trim().lowercase()
        return jobs.filter { j -> q.isEmpty() || j.jobNumber.lowercase().contains(q) || j.title.lowercase().contains(q) ||
            (customerName(j) ?: "").lowercase().contains(q) }
    }
    fun customerName(j: ShoeRepairJobRead): String? = j.shoe?.customerId?.let { customerNames[it] }
    val activeCount: Int get() = jobs.count { it.status in SHOE_ACTIVE_STATUSES }
    val completedCount: Int get() = jobs.count { it.status in SHOE_CLOSED_STATUSES }
    val visible: List<ShoeRepairJobRead> get() {
        val q = query.trim().lowercase()
        return jobs.filter { j ->
            (if(showCompleted) j.status in SHOE_CLOSED_STATUSES else j.status in SHOE_ACTIVE_STATUSES) &&
                (statusFilter == "all" || j.status == statusFilter) &&
                (q.isEmpty() || j.jobNumber.lowercase().contains(q) || j.title.lowercase().contains(q) ||
                    (j.description ?: "").lowercase().contains(q) || j.items.any { it.name.lowercase().contains(q) } ||
                    (customerName(j) ?: "").lowercase().contains(q))
        }
    }
}

val SHOE_ACTIVE_STATUSES: List<String> = listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on")
val SHOE_CLOSED_STATUSES: List<String> = listOf("completed", "awaiting_collection", "collected", "no_go")

class ShoeJobsViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val _state = MutableStateFlow(ShoeJobsUiState())
    val state: StateFlow<ShoeJobsUiState> = _state.asStateFlow()

    init {
        _state.update { it.copy(savedViews = appSavedViews.load("shoe")) }
        refresh()
        loadCustomerNames()
    }

    fun refresh() {
        if(_state.value.loading) return
        fetch(false)
    }
    fun currentView() = _state.value.let { SavedJobView("", it.statusFilter.takeIf { f -> f != "all" }, board = it.board, showCompleted = it.showCompleted, query = it.query.ifBlank { null }) }
    fun saveView(view: SavedJobView) { _state.update { it.copy(savedViews = appSavedViews.save("shoe", view)) } }
    fun deleteView(name: String) { _state.update { it.copy(savedViews = appSavedViews.delete("shoe", name)) } }
    fun applyView(v: SavedJobView) {
        _state.update { it.copy(statusFilter = v.statusFilter ?: "all", showCompleted = v.showCompleted, board = v.board, query = v.query.orEmpty()) }
    }
    fun setBoard(value: Boolean) { _state.update { it.copy(board = value) } }

    /** Board "Move to": changes one job's status and swaps the returned job into the list. */
    fun moveJob(id: String, status: String) {
        if(_state.value.movingId != null) return
        _state.update { it.copy(movingId = id, error = null) }
        viewModelScope.launch {
            try {
                val updated = api.postShoeRepairJobStatus(id, au.mainspring.nativeapp.api.ShoeStatusUpdate(status))
                _state.update { s -> s.copy(movingId = null, jobs = s.jobs.map { if(it.id == id) updated else it }) }
            } catch(e: kotlinx.coroutines.CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(movingId = null, error = e.userMessage()) } }
        }
    }
    fun setQuery(value: String) { _state.update { it.copy(query = value) } }
    fun setStatusFilter(value: String) { _state.update { it.copy(statusFilter = value) } }
    fun setShowCompleted(value: Boolean) { _state.update { it.copy(showCompleted = value, statusFilter = "all") } }
    private fun loadCustomerNames() {
        viewModelScope.launch {
            try {
                val names = mutableMapOf<String, String>()
                var offset = 0
                while(offset < 2000) {
                    val page = api.listCustomers(limit = 200, offset = offset)
                    page.forEach { names[it.id] = it.fullName }
                    if(page.size < 200) break
                    offset += 200
                }
                _state.update { it.copy(customerNames = names) }
            } catch(e: kotlinx.coroutines.CancellationException) { throw e }
            catch(_: Exception) { /* names are decoration; rows still work without them */ }
        }
    }
    fun loadMore() { if(!_state.value.loading && _state.value.canLoadMore) fetch(true) }
    private fun fetch(append: Boolean) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val list = api.listShoeRepairJobs(skip = if(append) _state.value.jobs.size else 0)
                _state.update { it.copy(loading = false, jobs = if(append) (it.jobs + list).distinctBy { row -> row.id } else list, canLoadMore = list.size == 200) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }
}
