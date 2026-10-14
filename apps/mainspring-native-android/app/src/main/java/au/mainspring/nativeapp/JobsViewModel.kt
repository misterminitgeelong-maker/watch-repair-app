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
) {
    /** Jobs after the client-side age filter and sort. */
    val visibleJobs: List<RepairJobRead> get() = sortJobs(
        jobs.filter { minDaysInShop == null || daysInShop(it.createdAt) >= minDaysInShop }, sort)
}

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
        refresh()
        loadUsers()
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
    fun filterStatus(value: String?) { _state.update { it.copy(statusFilter = value) }; refresh() }
    fun setSort(value: JobSort) { _state.update { it.copy(sort = value) } }
    fun filterMinDays(value: Int?) { _state.update { it.copy(minDaysInShop = value) } }
    fun filterTechnician(userId: String?) { _state.update { it.copy(technicianId = userId) }; refresh() }
}
