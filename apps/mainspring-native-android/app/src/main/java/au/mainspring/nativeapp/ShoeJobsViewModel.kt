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
)

class ShoeJobsViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val _state = MutableStateFlow(ShoeJobsUiState())
    val state: StateFlow<ShoeJobsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if(_state.value.loading) return
        fetch(false)
    }
    fun loadMore() { if(!_state.value.loading && _state.value.canLoadMore) fetch(true) }
    private fun fetch(append: Boolean) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val list = api.listShoeRepairJobs(skip = if(append) _state.value.jobs.size else 0)
                _state.update { it.copy(loading = false, jobs = if(append) (it.jobs + list).distinctBy { row -> row.id } else list, canLoadMore = list.size == 200) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load shoe jobs") }
            }
        }
    }
}
