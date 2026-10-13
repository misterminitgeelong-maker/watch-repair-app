package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AttachmentRead
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.RepairJobStatusUpdate
import au.mainspring.nativeapp.api.ShoeJobStatusHistoryRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.api.absolutizeApiUrl
import au.mainspring.nativeapp.api.requireSuccessEmptyBody
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException

data class ShoeJobDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val job: ShoeRepairJobRead? = null,
    val history: List<ShoeJobStatusHistoryRead> = emptyList(),
    val attachments: List<AttachmentRead> = emptyList(),
    val statusBusy: Boolean = false,
    val noteBusy: Boolean = false,
    val claimBusy: Boolean = false,
    val quoteBusy: Boolean = false,
    val statusUnknown: Boolean = false, val statusReviewed: Boolean = false, val statusRequest: String = "",
)

class ShoeJobDetailViewModel(
    private val jobId: String,
    private val apiBaseUrl: String,
) : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val statusCheckpoint = CounterStatusCheckpoint("shoe", jobId)
    private val _state = MutableStateFlow(ShoeJobDetailUiState(statusUnknown = statusCheckpoint.pending, statusRequest = statusCheckpoint.description))
    val state: StateFlow<ShoeJobDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        if(_state.value.loading || _state.value.statusBusy) return
        _state.update { it.copy(loading = true, error = null, statusReviewed = false) }
        viewModelScope.launch {
            try {
                val j = api.getShoeRepairJob(jobId)
                _state.update { it.copy(job = j) }
                val history = api.getShoeRepairJobStatusHistory(jobId)
                val attachments = try {
                    api.listAttachments(shoeRepairJobId = jobId)
                } catch (_: Exception) {
                    emptyList()
                }
                _state.update { it.copy(loading = false, job = j, history = history, attachments = attachments, statusReviewed = true) }
            } catch(e: CancellationException) { throw e }
            catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }

    suspend fun resolveDownloadUrl(storageKey: String): String {
        val link = api.getAttachmentDownloadLink(storageKey)
        return absolutizeApiUrl(apiBaseUrl, link.downloadUrl)
    }

    fun setStatus(newStatus: String, note: String? = null) {
        val snapshot = _state.value
        val current = snapshot.job ?: return
        if(snapshot.loading || snapshot.statusBusy || snapshot.statusUnknown || !TokenStore.canWorkJobs() || newStatus !in SHOE_JOB_STATUS_OPTIONS) return
        val message = note?.trim()?.takeIf { it.isNotEmpty() }
        if(newStatus == current.status && message == null) return
        _state.update { it.copy(statusBusy = true, error = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                val latest = api.getShoeRepairJob(jobId)
                if(latest.status != current.status) {
                    _state.update { it.copy(statusBusy = false, job = latest, error = "This status changed. Review the latest job before updating it.") }; return@launch
                }
                statusCheckpoint.start(newStatus, message); submitted = true
                _state.update { it.copy(statusRequest = statusCheckpoint.description) }
                val j = api.postShoeRepairJobStatus(jobId, RepairJobStatusUpdate(newStatus, message))
                statusCheckpoint.clear()
                _state.update { it.copy(statusBusy = false, job = j, statusUnknown = false, statusRequest = "") }
                load()
            } catch(e: CancellationException) { throw e }
            catch (e: Exception) {
                val unknown = submitted && (e !is retrofit2.HttpException || e.code() >= 500)
                if(!unknown) statusCheckpoint.clear()
                _state.update { it.copy(statusBusy = false, statusUnknown = unknown, statusReviewed = false, error = e.userMessage()) }
            }
        }
    }
    fun reviewedStatus() {
        if(!_state.value.statusReviewed || _state.value.loading || _state.value.statusBusy) return
        statusCheckpoint.clear(); _state.update { it.copy(statusUnknown = false, statusRequest = "") }
    }

    fun addNote(noteText: String) {
        val trimmed = noteText.trim()
        if (trimmed.isEmpty()) return
        viewModelScope.launch {
            _state.update { it.copy(noteBusy = true, error = null) }
            try {
                api.postShoeRepairJobNote(jobId, JobNotePayload(trimmed)).requireSuccessEmptyBody()
                val j = api.getShoeRepairJob(jobId)
                val history = api.getShoeRepairJobStatusHistory(jobId)
                _state.update { it.copy(noteBusy = false, job = j, history = history) }
            } catch (e: Exception) {
                _state.update { it.copy(noteBusy = false, error = e.message ?: "Could not add note") }
            }
        }
    }

    fun claimJob() {
        viewModelScope.launch {
            _state.update { it.copy(claimBusy = true, error = null) }
            try {
                val j = api.postShoeRepairJobClaim(jobId)
                _state.update { it.copy(claimBusy = false, job = j) }
            } catch (e: Exception) {
                _state.update { it.copy(claimBusy = false, error = e.message ?: "Could not claim job") }
            }
        }
    }

    fun releaseJob() {
        viewModelScope.launch {
            _state.update { it.copy(claimBusy = true, error = null) }
            try {
                val j = api.postShoeRepairJobRelease(jobId)
                _state.update { it.copy(claimBusy = false, job = j) }
            } catch (e: Exception) {
                _state.update { it.copy(claimBusy = false, error = e.message ?: "Could not release job") }
            }
        }
    }
    fun sendQuote() {
        if(_state.value.quoteBusy) return
        _state.update { it.copy(quoteBusy = true, error = null) }
        viewModelScope.launch {
            try { val job = api.sendShoeQuote(jobId); _state.update { it.copy(quoteBusy = false, job = job) } }
            catch(e: Exception) { _state.update { it.copy(quoteBusy = false, error = "Could not confirm quote delivery. Refresh the job before sending again. ${e.message.orEmpty()}") } }
        }
    }

    companion object {
        fun factory(jobId: String, apiBaseUrl: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return ShoeJobDetailViewModel(jobId, apiBaseUrl) as T
            }
        }
    }
}

