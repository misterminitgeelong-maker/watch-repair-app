package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AutoKeyJobRead
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AutoKeyJobsUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val jobs: List<AutoKeyJobRead> = emptyList(),
)

class AutoKeyJobsViewModel : ViewModel() {
    private val _state = MutableStateFlow(AutoKeyJobsUiState())
    val state: StateFlow<AutoKeyJobsUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = ApiClient.api.listAutoKeyJobs()
                _state.update { it.copy(loading = false, jobs = list) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load mobile service jobs") }
            }
        }
    }
}
