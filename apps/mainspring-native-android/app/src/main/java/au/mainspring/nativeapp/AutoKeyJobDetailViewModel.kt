package au.mainspring.nativeapp

import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import com.google.gson.Gson

data class AutoKeyJobDetailUiState(val loading: Boolean = false, val error: String? = null, val offlineSnapshot: Boolean = false,
    val job: AutoKeyJobRead? = null, val vehicleContext: com.google.gson.JsonObject? = null, val technicians: List<TeamUser> = emptyList(), val attachments: List<AttachmentRead> = emptyList(),
    val statusBusy: Boolean = false, val statusReviewRequired: Boolean = false, val historyChecked: Boolean = false,
    val statusInfo: String? = null, val requestedStatus: String? = null, val requestedNote: String? = null)

class AutoKeyJobDetailViewModel(private val jobId: String, private val apiBaseUrl: String) : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val operation = "mobile-status/$jobId"
    private val snapshots=FieldSnapshots(drafts)
    private val cachedJob=snapshots.job(jobId)
    private val previousRequest = try { Gson().fromJson(drafts.loadMessageDraft("$operation/request"),RepairJobStatusUpdate::class.java) } catch(_: Exception) { null }
    private val mutable = MutableStateFlow(AutoKeyJobDetailUiState(job=cachedJob,offlineSnapshot=cachedJob!=null,statusReviewRequired = drafts.pendingOperation(operation), requestedStatus = previousRequest?.status, requestedNote = previousRequest?.note))
    val state = mutable.asStateFlow()
    init { load() }
    fun load() {
        if(mutable.value.loading || mutable.value.statusBusy) return
        mutable.update { it.copy(loading = true, error = null, historyChecked = false, statusInfo = null) }
        viewModelScope.launch {
            try {
                val job = api.getAutoKeyJob(jobId)
                val files = try { api.listAttachments(autoKeyJobId = jobId) }
                    catch(e: CancellationException) { throw e } catch(_: Exception) { mutable.value.attachments }
                val context = if(!job.vehicleMake.isNullOrBlank() || !job.vehicleModel.isNullOrBlank()) try {api.vehicleJobContext(job.vehicleMake,job.vehicleModel,job.vehicleYear,job.jobType,job.bladeCode)} catch(e: CancellationException) {throw e} catch(_: Exception) {null} else null
                val users = try {api.teamUsers()} catch(e: CancellationException) {throw e} catch(_: Exception) {emptyList()}
                snapshots.saveJob(job)
                mutable.update { it.copy(offlineSnapshot=false,job = job, vehicleContext = context, technicians = users, attachments = files, loading = false, historyChecked = true) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, offlineSnapshot=it.job!=null, error = "Could not refresh this job. ${e.userMessage()}") } }
        }
    }
    suspend fun resolveDownloadUrl(storageKey: String): String = absolutizeApiUrl(apiBaseUrl,api.getAttachmentDownloadLink(storageKey).downloadUrl)
    fun reviewedStatus() {
        if(mutable.value.loading || mutable.value.statusBusy || !mutable.value.historyChecked) return
        drafts.saveMessageDraft("$operation/request",""); drafts.setPendingOperation(operation,false); mutable.update { it.copy(statusReviewRequired = false, requestedStatus = null, requestedNote = null) }
    }
    fun setStatus(newStatus: String, note: String? = null) {
        val snapshot = mutable.value
        if(snapshot.loading || snapshot.statusBusy || snapshot.statusReviewRequired || snapshot.offlineSnapshot || !TokenStore.canWorkJobs()) return
        val current = snapshot.job ?: return
        if(newStatus !in AUTO_KEY_JOB_STATUS_OPTIONS) { mutable.update { it.copy(error = "Choose a valid mobile job status.") }; return }
        if(newStatus == current.status && note.isNullOrBlank()) return
        val body = RepairJobStatusUpdate(newStatus,note?.trim()?.ifBlank { null })
        drafts.saveMessageDraft("$operation/request",Gson().toJson(body))
        if(!drafts.setPendingOperation(operation,true)) { mutable.update { it.copy(error = "Could not save the status checkpoint. Check device storage and sign in before continuing.") }; return }
        mutable.update { it.copy(statusBusy = true, error = null, statusInfo = null, historyChecked = false, requestedStatus = body.status, requestedNote = body.note) }
        viewModelScope.launch {
            try {
                val job = api.postAutoKeyJobStatus(jobId,body,current.updatedAt)
                drafts.saveMessageDraft("$operation/request","")
                drafts.setPendingOperation(operation,false)
                val message = when { job.invoiceCreated == true -> "Status saved. An invoice was created; review it in Quotes and invoices."
                    job.invoiceSkipReason == "already_invoiced" -> "Status saved. This job already has an invoice."
                    else -> "Status saved." }
                snapshots.saveJob(job)
                mutable.update { it.copy(job = job, offlineSnapshot=false,statusInfo = message) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val unknown = e !is HttpException || e.code() >= 500
                val conflict = e is HttpException && e.code() == 409
                drafts.setPendingOperation(operation,unknown)
                mutable.update { it.copy(statusReviewRequired = unknown || conflict, error = "Could not confirm this status change. Refresh and review the job before trying again. ${e.userMessage()}") }
            } finally { mutable.update { it.copy(statusBusy = false) } }
        }
    }
    companion object { fun factory(id: String, url: String) = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = AutoKeyJobDetailViewModel(id,url) as T
    } }
}
