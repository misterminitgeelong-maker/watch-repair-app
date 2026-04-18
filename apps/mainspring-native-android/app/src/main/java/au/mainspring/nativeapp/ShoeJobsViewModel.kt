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
)

class ShoeJobsViewModel : ViewModel() {
    private val _state = MutableStateFlow(ShoeJobsUiState())
    val state: StateFlow<ShoeJobsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = ApiClient.api.listShoeRepairJobs()
                _state.update { it.copy(loading = false, jobs = list) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load shoe jobs") }
            }
        }
    }
}
