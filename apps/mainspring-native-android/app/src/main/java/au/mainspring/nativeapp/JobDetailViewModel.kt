package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.JobStatusHistoryRead
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.RepairJobStatusUpdate
import au.mainspring.nativeapp.api.requireSuccessEmptyBody
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class JobDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val job: RepairJobRead? = null,
    val history: List<JobStatusHistoryRead> = emptyList(),
    val statusBusy: Boolean = false,
    val noteBusy: Boolean = false,
)

class JobDetailViewModel(
    private val jobId: String,
) : ViewModel() {
    private val _state = MutableStateFlow(JobDetailUiState())
    val state: StateFlow<JobDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val job = ApiClient.api.getRepairJob(jobId)
                val history = ApiClient.api.getRepairJobStatusHistory(jobId)
                _state.update { it.copy(loading = false, job = job, history = history) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load job") }
            }
        }
    }

    fun setStatus(newStatus: String, note: String? = null) {
        viewModelScope.launch {
            _state.update { it.copy(statusBusy = true, error = null) }
            try {
                val job = ApiClient.api.postRepairJobStatus(jobId, RepairJobStatusUpdate(newStatus, note))
                val history = ApiClient.api.getRepairJobStatusHistory(jobId)
                _state.update { it.copy(statusBusy = false, job = job, history = history) }
            } catch (e: Exception) {
                _state.update { it.copy(statusBusy = false, error = e.message ?: "Status update failed") }
            }
        }
    }

    fun addNote(noteText: String) {
        val trimmed = noteText.trim()
        if (trimmed.isEmpty()) return
        viewModelScope.launch {
            _state.update { it.copy(noteBusy = true, error = null) }
            try {
                ApiClient.api.postRepairJobNote(jobId, JobNotePayload(trimmed)).requireSuccessEmptyBody()
                val history = ApiClient.api.getRepairJobStatusHistory(jobId)
                _state.update { it.copy(noteBusy = false, history = history) }
            } catch (e: Exception) {
                _state.update { it.copy(noteBusy = false, error = e.message ?: "Could not add note") }
            }
        }
    }

    companion object {
        fun factory(jobId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return JobDetailViewModel(jobId) as T
            }
        }
    }
}
