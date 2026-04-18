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

data class JobsUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val jobs: List<RepairJobRead> = emptyList(),
)

class JobsViewModel : ViewModel() {
    private val _state = MutableStateFlow(JobsUiState())
    val state: StateFlow<JobsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = ApiClient.api.listRepairJobs()
                _state.update { it.copy(loading = false, jobs = list, error = null) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, error = e.message ?: "Could not load jobs (check watch feature on plan).")
                }
            }
        }
    }
}
