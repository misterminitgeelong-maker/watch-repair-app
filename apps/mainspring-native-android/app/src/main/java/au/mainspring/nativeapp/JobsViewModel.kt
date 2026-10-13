package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.RepairJobRead
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
)

class JobsViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private var request: Job? = null
    private val _state = MutableStateFlow(JobsUiState())
    val state: StateFlow<JobsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        request?.cancel()
        request = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = api.listRepairJobs(q = _state.value.query.trim().ifBlank { null }, status = _state.value.statusFilter)
                _state.update { it.copy(loading = false, jobs = list, error = null, canLoadMore = list.size == 100) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, error = e.message ?: "Could not load jobs (check watch feature on plan).")
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
                    q = snapshot.query.trim().ifBlank { null }, status = snapshot.statusFilter)
                _state.update { it.copy(jobs = (it.jobs + page).distinctBy { job -> job.id }, loading = false, canLoadMore = page.size == 100) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(loading = false, error = "Could not load more repairs. Try again.") } }
        }
    }
    fun filterStatus(value: String?) { _state.update { it.copy(statusFilter = value) }; refresh() }
}
