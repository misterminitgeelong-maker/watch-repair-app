package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AttachmentRead
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.JobStatusHistoryRead
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.RepairJobStatusUpdate
import au.mainspring.nativeapp.api.ResendNotificationRequest
import au.mainspring.nativeapp.api.SmsLogRead
import au.mainspring.nativeapp.api.absolutizeApiUrl
import au.mainspring.nativeapp.api.requireSuccessEmptyBody
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException

data class JobDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val job: RepairJobRead? = null,
    val history: List<JobStatusHistoryRead> = emptyList(),
    val attachments: List<AttachmentRead> = emptyList(),
    val smsLog: List<SmsLogRead> = emptyList(),
    val statusBusy: Boolean = false,
    val noteBusy: Boolean = false,
    val claimBusy: Boolean = false,
    val resendBusy: Boolean = false,
    val resendInfo: String? = null,
    val statusUnknown: Boolean = false, val statusReviewed: Boolean = false, val statusRequest: String = "",
)

class JobDetailViewModel(
    private val jobId: String,
    private val apiBaseUrl: String,
) : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val statusCheckpoint = CounterStatusCheckpoint("watch", jobId)
    private val _state = MutableStateFlow(JobDetailUiState(statusUnknown = statusCheckpoint.pending, statusRequest = statusCheckpoint.description))
    val state: StateFlow<JobDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        if(_state.value.loading || _state.value.statusBusy) return
        _state.update { it.copy(loading = true, error = null, statusReviewed = false) }
        viewModelScope.launch {
            try {
                val job = api.getRepairJob(jobId)
                _state.update { it.copy(job = job) }
                val history = api.getRepairJobStatusHistory(jobId)
                val attachments = try {
                    api.listAttachments(repairJobId = jobId)
                } catch (_: Exception) {
                    emptyList()
                }
                val smsLog = try {
                    api.getRepairJobSmsLog(jobId)
                } catch (_: Exception) {
                    emptyList()
                }
                _state.update {
                    it.copy(loading = false, job = job, history = history, attachments = attachments, smsLog = smsLog, statusReviewed = true)
                }
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
        if(snapshot.loading || snapshot.statusBusy || snapshot.statusUnknown || !TokenStore.canWorkJobs() || newStatus !in WATCH_JOB_STATUS_OPTIONS) return
        val message = note?.trim()?.takeIf { it.isNotEmpty() }
        if(newStatus == current.status && message == null) return
        _state.update { it.copy(statusBusy = true, error = null, resendInfo = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                val latest = api.getRepairJob(jobId)
                if(latest.status != current.status) {
                    _state.update { it.copy(statusBusy = false, job = latest, error = "This status changed. Review the latest job before updating it.") }; return@launch
                }
                statusCheckpoint.start(newStatus, message); submitted = true
                _state.update { it.copy(statusRequest = statusCheckpoint.description) }
                val job = api.postRepairJobStatus(jobId, RepairJobStatusUpdate(newStatus, message))
                statusCheckpoint.clear()
                _state.update { it.copy(statusBusy = false, job = job, statusUnknown = false, statusRequest = "") }
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
            _state.update { it.copy(noteBusy = true, error = null, resendInfo = null) }
            try {
                api.postRepairJobNote(jobId, JobNotePayload(trimmed)).requireSuccessEmptyBody()
                val history = api.getRepairJobStatusHistory(jobId)
                val smsLog = try {
                    api.getRepairJobSmsLog(jobId)
                } catch (_: Exception) {
                    _state.value.smsLog
                }
                _state.update { it.copy(noteBusy = false, history = history, smsLog = smsLog) }
            } catch (e: Exception) {
                _state.update { it.copy(noteBusy = false, error = e.message ?: "Could not add note") }
            }
        }
    }

    fun claimJob() {
        viewModelScope.launch {
            _state.update { it.copy(claimBusy = true, error = null, resendInfo = null) }
            try {
                val job = api.postRepairJobClaim(jobId)
                _state.update { it.copy(claimBusy = false, job = job) }
            } catch (e: Exception) {
                _state.update { it.copy(claimBusy = false, error = e.message ?: "Could not claim job") }
            }
        }
    }

    fun releaseJob() {
        viewModelScope.launch {
            _state.update { it.copy(claimBusy = true, error = null, resendInfo = null) }
            try {
                val job = api.postRepairJobRelease(jobId)
                _state.update { it.copy(claimBusy = false, job = job) }
            } catch (e: Exception) {
                _state.update { it.copy(claimBusy = false, error = e.message ?: "Could not release job") }
            }
        }
    }

    fun resendNotification(eventType: String) {
        viewModelScope.launch {
            _state.update { it.copy(resendBusy = true, error = null, resendInfo = null) }
            try {
                val r = api.postRepairJobResendNotification(jobId, ResendNotificationRequest(eventType))
                val parts = buildList {
                    if (r.sent.sms) add("SMS")
                    if (r.sent.email) add("Email")
                }
                val msg = if (parts.isEmpty()) {
                    "Nothing was sent (check customer phone/email, or quote status for “Quote sent”)."
                } else {
                    "Sent: ${parts.joinToString(" + ")}"
                }
                val smsLog = try {
                    api.getRepairJobSmsLog(jobId)
                } catch (_: Exception) {
                    _state.value.smsLog
                }
                _state.update { it.copy(resendBusy = false, resendInfo = msg, smsLog = smsLog) }
            } catch (e: Exception) {
                _state.update { it.copy(resendBusy = false, error = e.message ?: "Resend failed") }
            }
        }
    }

    companion object {
        fun factory(jobId: String, apiBaseUrl: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return JobDetailViewModel(jobId, apiBaseUrl) as T
            }
        }
    }
}

