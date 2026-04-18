package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ShoeJobDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val job: ShoeRepairJobRead? = null,
)

class ShoeJobDetailViewModel(
    private val jobId: String,
) : ViewModel() {
    private val _state = MutableStateFlow(ShoeJobDetailUiState())
    val state: StateFlow<ShoeJobDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val j = ApiClient.api.getShoeRepairJob(jobId)
                _state.update { it.copy(loading = false, job = j) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load shoe job") }
            }
        }
    }

    companion object {
        fun factory(jobId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return ShoeJobDetailViewModel(jobId) as T
            }
        }
    }
}
