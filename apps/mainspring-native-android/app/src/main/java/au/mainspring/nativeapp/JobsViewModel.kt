package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.TeamUser
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException

data class JobsUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val jobs: List<RepairJobRead> = emptyList(),
    val query: String = "",
    val statusFilter: String? = null,
    val canLoadMore: Boolean = false,
    val sort: JobSort = JobSort.NEWEST,
    /** Only jobs at least this many days in the shop (web "N+ days in shop"). */
    val minDaysInShop: Int? = null,
    /** Server-side filter on `assigned_user_id`. */
    val technicianId: String? = null,
    val users: List<TeamUser> = emptyList(),
    /** Board (kanban) view instead of the list. */
    val board: Boolean = true,
    val movingId: String? = null,
    /** "Moved to X. Undo" message after a board move. */
    val moveToast: au.mainspring.nativeapp.ui.screens.BoardMoveToast? = null,
    val savedViews: List<SavedJobView> = emptyList(),
    /** Completed tab (web "Completed") instead of Active. */
    val showCompleted: Boolean = false,
) {
    /** Jobs after the client-side Active/Completed split, age filter and sort. */
    val visibleJobs: List<RepairJobRead> get() = sortJobs(
        jobs.filter { isWatchCompleted(it.status) == showCompleted && (minDaysInShop == null || daysInShop(it.createdAt) >= minDaysInShop) }, sort)
    val activeCount: Int get() = jobs.count { !isWatchCompleted(it.status) }
    val completedCount: Int get() = jobs.count { isWatchCompleted(it.status) }
    /** Number of non-default Filters-sheet choices, for the "Filters" button badge. */
    val activeFilterCount: Int get() = listOf(statusFilter != null, sort != JobSort.NEWEST, minDaysInShop != null, technicianId != null).count { it }
}

/** Statuses that belong on the Completed tab; everything else is Active. */
val WATCH_COMPLETED_STATUSES: Set<String> = setOf("collected", "invoice_paid", "failed_job", "no_go")
fun isWatchCompleted(status: String): Boolean = status in WATCH_COMPLETED_STATUSES

enum class JobSort(val label: String) {
    NEWEST("Newest"), OLDEST("Oldest"), DUE("Due date"), CUSTOMER("Customer"),
}

internal fun daysInShop(createdAt: String?, now: java.time.Instant = java.time.Instant.now()): Int {
    val created = try { java.time.OffsetDateTime.parse(createdAt).toInstant() } catch (_: Exception) { return 0 }
    return java.time.Duration.between(created, now).toDays().toInt().coerceAtLeast(0)
}

internal fun sortJobs(jobs: List<RepairJobRead>, sort: JobSort): List<RepairJobRead> = when(sort) {
    JobSort.NEWEST -> jobs.sortedByDescending { it.createdAt }
    JobSort.OLDEST -> jobs.sortedBy { it.createdAt }
    // Jobs without a collection date go last.
    JobSort.DUE -> jobs.sortedWith(compareBy<RepairJobRead> { it.collectionDate == null }.thenBy { it.collectionDate.orEmpty() }.thenBy { it.jobNumber })
    JobSort.CUSTOMER -> jobs.sortedWith(compareBy<RepairJobRead> { it.customerName.isNullOrBlank() }.thenBy { it.customerName.orEmpty().lowercase() }.thenBy { it.jobNumber })
}

class JobsViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private var request: Job? = null
    private val _state = MutableStateFlow(JobsUiState())
    val state: StateFlow<JobsUiState> = _state.asStateFlow()

    init {
        _state.update { it.copy(savedViews = appSavedViews.load("watch")) }
        refresh()
        loadUsers()
    }

    fun currentView() = _state.value.let { SavedJobView("", it.statusFilter, it.sort.name, it.minDaysInShop, it.technicianId, it.board, showCompleted = it.showCompleted, query = it.query.ifBlank { null }) }
    fun saveView(view: SavedJobView) { _state.update { it.copy(savedViews = appSavedViews.save("watch", view)) } }
    fun deleteView(name: String) { _state.update { it.copy(savedViews = appSavedViews.delete("watch", name)) } }
    fun applyView(v: SavedJobView) {
        _state.update { it.copy(statusFilter = v.statusFilter, sort = JobSort.values().firstOrNull { s -> s.name == v.sort } ?: JobSort.NEWEST,
            minDaysInShop = v.minDaysInShop, technicianId = v.technicianId, board = v.board, showCompleted = v.showCompleted, query = v.query.orEmpty()) }
        refresh()
    }

    private fun loadUsers() {
        viewModelScope.launch {
            try {
                val users = api.teamUsers().filter { it.active }.sortedBy { it.name.lowercase() }
                _state.update { it.copy(users = users) }
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) { /* technician filter is optional; the list still works without it */ }
        }
    }

    fun refresh() {
        request?.cancel()
        request = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = api.listRepairJobs(q = _state.value.query.trim().ifBlank { null }, status = _state.value.statusFilter, assignedUserId = _state.value.technicianId)
                _state.update { it.copy(loading = false, jobs = list, error = null, canLoadMore = list.size == 100) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, error = e.userMessage())
                }
            }
        }
    }

    fun setQuery(value: String) { _state.update { it.copy(query = value) } }
    fun loadMore() {
        if (_state.value.loading || !_state.value.canLoadMore) return
        val snapshot = _state.value
        _state.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                val page = api.listRepairJobs(offset = snapshot.jobs.size,
                    q = snapshot.query.trim().ifBlank { null }, status = snapshot.statusFilter, assignedUserId = snapshot.technicianId)
                _state.update { it.copy(jobs = (it.jobs + page).distinctBy { job -> job.id }, loading = false, canLoadMore = page.size == 100) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(loading = false, error = "Could not load more repairs. Try again.") } }
        }
    }
    fun setBoard(value: Boolean) { _state.update { it.copy(board = value) } }

    /** List-card delete (owner/manager only, as on the web); drops the job from the loaded list on success. */
    fun deleteJob(id: String) {
        if (!TokenStore.canManageInvoices()) return
        viewModelScope.launch {
            try {
                au.mainspring.nativeapp.api.ApiClient.service(au.mainspring.nativeapp.api.JobAdminApi::class.java).deleteRepairJob(id)
                    .let { r -> if (!r.isSuccessful) throw retrofit2.HttpException(r); r.body()?.close() }
                _state.update { s -> s.copy(jobs = s.jobs.filter { it.id != id }) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(error = e.userMessage()) } }
        }
    }

    /** Board "Move to": changes one job's status and swaps the returned job into the list. */
    fun moveJob(id: String, status: String) = moveJob(id, status, null, true)
    /** Moves a ticket to [status] (with [reason] as the status note). A network failure queues the change like any other offline write. */
    fun moveJob(id: String, status: String, reason: String?, showToast: Boolean = true) {
        if (_state.value.movingId != null) return
        val from = _state.value.jobs.firstOrNull { it.id == id }?.status ?: return
        if (from == status) return
        val note = reason?.trim()?.takeIf { it.isNotEmpty() }
        _state.update { it.copy(movingId = id, error = null, moveToast = null) }
        viewModelScope.launch {
            try {
                val updated = api.postRepairJobStatus(id, au.mainspring.nativeapp.api.RepairJobStatusUpdate(status = status, note = note))
                _state.update { s -> s.copy(movingId = null, jobs = s.jobs.map { if (it.id == id) updated else it },
                    moveToast = if(showToast) toast(id, from, status, false) else null) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                if(au.mainspring.nativeapp.offline.OfflineSync.queueStatus(e, au.mainspring.nativeapp.offline.OfflineKinds.WATCH_STATUS, id, status, note, null, "Watch job", baseStatus = from)) {
                    _state.update { s -> s.copy(movingId = null, jobs = s.jobs.map { if (it.id == id) it.copy(status = status) else it },
                        moveToast = if(showToast) toast(id, from, status, true) else null) }
                } else _state.update { it.copy(movingId = null, error = e.userMessage()) }
            }
        }
    }
    private fun toast(id: String, from: String, to: String, queued: Boolean) =
        au.mainspring.nativeapp.ui.screens.BoardMoveToast(id, from, to, watchStatusLabel(to), queued)
    fun clearMoveToast() { _state.update { it.copy(moveToast = null) } }
    fun undoMove(t: au.mainspring.nativeapp.ui.screens.BoardMoveToast) { _state.update { it.copy(moveToast = null) }; moveJob(t.id, t.from, null, false) }
    fun filterStatus(value: String?) { _state.update { it.copy(statusFilter = value, showCompleted = value?.let(::isWatchCompleted) ?: it.showCompleted) }; refresh() }
    fun setShowCompleted(value: Boolean) { _state.update { it.copy(showCompleted = value) } }
    fun setSort(value: JobSort) { _state.update { it.copy(sort = value) } }
    fun filterMinDays(value: Int?) { _state.update { it.copy(minDaysInShop = value) } }
    fun filterTechnician(userId: String?) { _state.update { it.copy(technicianId = userId) }; refresh() }
}
