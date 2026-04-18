package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AttachmentRead
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.api.RepairJobStatusUpdate
import au.mainspring.nativeapp.api.absolutizeApiUrl
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AutoKeyJobDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val job: AutoKeyJobRead? = null,
    val attachments: List<AttachmentRead> = emptyList(),
    val statusBusy: Boolean = false,
)

class AutoKeyJobDetailViewModel(
    private val jobId: String,
    private val apiBaseUrl: String,
) : ViewModel() {
    private val _state = MutableStateFlow(AutoKeyJobDetailUiState())
    val state: StateFlow<AutoKeyJobDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val j = ApiClient.api.getAutoKeyJob(jobId)
                val attachments = try {
                    ApiClient.api.listAttachments(autoKeyJobId = jobId)
                } catch (_: Exception) {
                    emptyList()
                }
                _state.update { it.copy(loading = false, job = j, attachments = attachments) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load job") }
            }
        }
    }

    suspend fun resolveDownloadUrl(storageKey: String): String {
        val link = ApiClient.api.getAttachmentDownloadLink(storageKey)
        return absolutizeApiUrl(apiBaseUrl, link.downloadUrl)
    }

    fun setStatus(newStatus: String, note: String? = null) {
        viewModelScope.launch {
            _state.update { it.copy(statusBusy = true, error = null) }
            try {
                val j = ApiClient.api.postAutoKeyJobStatus(jobId, RepairJobStatusUpdate(newStatus, note?.trim()?.takeIf { it.isNotEmpty() }))
                val attachments = try {
                    ApiClient.api.listAttachments(autoKeyJobId = jobId)
                } catch (_: Exception) {
                    _state.value.attachments
                }
                _state.update { it.copy(statusBusy = false, job = j, attachments = attachments) }
            } catch (e: Exception) {
                _state.update { it.copy(statusBusy = false, error = e.message ?: "Status update failed") }
            }
        }
    }

    companion object {
        fun factory(jobId: String, apiBaseUrl: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return AutoKeyJobDetailViewModel(jobId, apiBaseUrl) as T
            }
        }
    }
}
