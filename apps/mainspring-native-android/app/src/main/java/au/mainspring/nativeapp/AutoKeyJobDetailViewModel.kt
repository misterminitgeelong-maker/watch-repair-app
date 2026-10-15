package au.mainspring.nativeapp

import au.mainspring.nativeapp.offline.OfflineKinds
import au.mainspring.nativeapp.offline.OfflineSync

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
    val statusInfo: String? = null, val requestedStatus: String? = null, val requestedNote: String? = null,
    val activity: List<JobActivityEvent> = emptyList(), val activityLoading: Boolean = false, val activityError: String? = null, val activityLoaded: Boolean = false,
    val adminBusy: Boolean = false, val adminError: String? = null, val duplicated: AutoKeyJobRead? = null, val deleted: Boolean = false,
    val keySearchLoading: Boolean = false, val keyMatches: List<KeySpecMatch> = emptyList(), val keySearched: Boolean = false, val keySearchError: String? = null,
    val keyApplyBusy: Boolean = false, val keyApplied: Boolean = false)

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
        if(newStatus !in AUTO_KEY_JOB_STATUS_OPTIONS && MOBILE_STATUS_PICKER.none { it.first == newStatus }) { mutable.update { it.copy(error = "Choose a valid mobile job status.") }; return }
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
                if(OfflineSync.queueStatus(e, OfflineKinds.MOBILE_STATUS, jobId, body.status, body.note, null, "Mobile job", expectedUpdatedAt = current.updatedAt)) {
                    drafts.saveMessageDraft("$operation/request",""); drafts.setPendingOperation(operation,false)
                    mutable.update { it.copy(statusReviewRequired = false, requestedStatus = null, requestedNote = null, statusInfo = null) }
                    return@launch
                }
                val unknown = e !is HttpException || e.code() >= 500
                val conflict = e is HttpException && e.code() == 409
                drafts.setPendingOperation(operation,unknown)
                mutable.update { it.copy(statusReviewRequired = unknown || conflict, error = "Could not confirm this status change. Refresh and review the job before trying again. ${e.userMessage()}") }
            } finally { mutable.update { it.copy(statusBusy = false) } }
        }
    }
    private val admin get() = ApiClient.service(MobileJobAdminApi::class.java)
    fun loadActivity() {
        if(mutable.value.activityLoading || mutable.value.offlineSnapshot) return
        mutable.update { it.copy(activityLoading = true, activityError = null) }
        viewModelScope.launch {
            try { val events = admin.activity(jobId).sortedByDescending { it.createdAt }; mutable.update { it.copy(activity = events, activityLoaded = true) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(activityError = "Could not load the activity log. ${e.userMessage()}") } }
            finally { mutable.update { it.copy(activityLoading = false) } }
        }
    }
    fun dismissAdminMessage() { mutable.update { it.copy(adminError = null, duplicated = null) } }
    /** Duplicating is not idempotent, so an unconfirmed failure asks the operator to check the job list before retrying. */
    fun duplicate() {
        if(mutable.value.adminBusy || mutable.value.offlineSnapshot || !TokenStore.canWorkJobs()) return
        mutable.update { it.copy(adminBusy = true, adminError = null, duplicated = null) }
        viewModelScope.launch {
            try { val copy = admin.cloneJob(jobId); mutable.update { it.copy(duplicated = copy) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(adminError = if(e is HttpException && e.code() < 500) "Could not duplicate this job. ${e.userMessage()}" else "Could not confirm the duplicate. Check the job list before trying again. ${e.userMessage()}") } }
            finally { mutable.update { it.copy(adminBusy = false) } }
        }
    }
    fun deleteJob() {
        if(mutable.value.adminBusy || mutable.value.offlineSnapshot || !TokenStore.canManageInvoices()) return
        mutable.update { it.copy(adminBusy = true, adminError = null) }
        viewModelScope.launch {
            try {
                val response = admin.deleteJob(jobId)
                if(response.isSuccessful || response.code() == 404) { drafts.saveMessageDraft("mobile-job-cache/$jobId",""); mutable.update { it.copy(deleted = true) } }
                else mutable.update { it.copy(adminError = "Could not delete this job (${response.code()}).") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(adminError = "Could not confirm the delete. Refresh before trying again. ${e.userMessage()}") } }
            finally { mutable.update { it.copy(adminBusy = false) } }
        }
    }
    fun searchKeys(make: String, model: String, year: String) {
        if(mutable.value.keySearchLoading) return
        if(make.trim().length < 2 && model.trim().length < 2) { mutable.update { it.copy(keySearchError = "Enter at least two letters of the make or model.", keyMatches = emptyList(), keySearched = false) }; return }
        val y = year.trim().takeIf { it.isNotEmpty() }?.let { it.toIntOrNull() ?: run { mutable.update { s -> s.copy(keySearchError = "Enter a valid year.") }; return } }
        mutable.update { it.copy(keySearchLoading = true, keySearchError = null, keyApplied = false) }
        viewModelScope.launch {
            try { val r = admin.searchKeySpecs(make.trim().ifEmpty { null }, model.trim().ifEmpty { null }, y); mutable.update { it.copy(keyMatches = r.matches, keySearched = true) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(keyMatches = emptyList(), keySearched = false, keySearchError = "Could not search the vehicle database. ${e.userMessage()}") } }
            finally { mutable.update { it.copy(keySearchLoading = false) } }
        }
    }
    fun clearKeySearch() { mutable.update { it.copy(keyMatches = emptyList(), keySearched = false, keySearchError = null, keyApplied = false) } }
    /** Applies the chosen match like the web: vehicle, key type, chip, blade and notes. Existing technician notes are kept. */
    fun applyKeyMatch(match: KeySpecMatch, typedYear: String) {
        val current = mutable.value.job ?: return
        val snapshot = mutable.value
        if(snapshot.keyApplyBusy || snapshot.offlineSnapshot || snapshot.loading || snapshot.statusBusy || !TokenStore.canWorkJobs()) return
        val body = com.google.gson.JsonObject()
        body.addProperty("vehicle_make", match.vehicleMake); body.addProperty("vehicle_model", match.vehicleModel)
        (typedYear.trim().toIntOrNull() ?: match.yearFrom)?.let { body.addProperty("vehicle_year", it) }
        match.keyType?.takeIf { it.isNotBlank() }?.let { body.addProperty("key_type", it) }
        match.chipType?.takeIf { it.isNotBlank() }?.let { body.addProperty("chip_type", it) }
        match.suggestedBladeCode?.takeIf { it.isNotBlank() }?.let { body.addProperty("blade_code", it) }
        match.techNotes?.takeIf { it.isNotBlank() }?.let { note ->
            val existing = current.techNotes.orEmpty().trim()
            if(!existing.contains(note.trim())) body.addProperty("tech_notes", if(existing.isEmpty()) note.trim() else existing + "\n\n" + note.trim())
        }
        mutable.update { it.copy(keyApplyBusy = true, keySearchError = null) }
        viewModelScope.launch {
            try {
                val job = api.updateMobileJob(jobId, body, current.updatedAt)
                snapshots.saveJob(job)
                mutable.update { it.copy(job = job, keyApplied = true, statusInfo = "Key details applied from the vehicle database.", activityLoaded = false) }
                val context = try { api.vehicleJobContext(job.vehicleMake, job.vehicleModel, job.vehicleYear, job.jobType, job.bladeCode) } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
                if(context != null) mutable.update { it.copy(vehicleContext = context) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(keySearchError = if(e is HttpException && e.code() == 409) "This job changed. Refresh it, then apply the match again." else "Could not apply these details. ${e.userMessage()}") } }
            finally { mutable.update { it.copy(keyApplyBusy = false) } }
        }
    }
    companion object { fun factory(id: String, url: String) = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = AutoKeyJobDetailViewModel(id,url) as T
    } }
}
