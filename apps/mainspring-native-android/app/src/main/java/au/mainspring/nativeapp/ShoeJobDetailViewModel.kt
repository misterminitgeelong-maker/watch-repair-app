package au.mainspring.nativeapp

import au.mainspring.nativeapp.offline.OfflineKinds
import au.mainspring.nativeapp.offline.OfflineSync

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AttachmentRead
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.ShoeCatalogueItem
import au.mainspring.nativeapp.api.ShoeCreate
import au.mainspring.nativeapp.api.ShoeItemCreate
import au.mainspring.nativeapp.api.ShoeItemsAppend
import au.mainspring.nativeapp.api.ShoeLink
import au.mainspring.nativeapp.api.ShoeStatusUpdate
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
    val info: String? = null,
    val job: ShoeRepairJobRead? = null,
    val customer: au.mainspring.nativeapp.api.CustomerRead? = null,
    val history: List<ShoeJobStatusHistoryRead> = emptyList(),
    val attachments: List<AttachmentRead> = emptyList(),
    val statusBusy: Boolean = false,
    val noteBusy: Boolean = false,
    val claimBusy: Boolean = false,
    val quoteBusy: Boolean = false,
    val editBusy: Boolean = false,
    val adminBusy: Boolean = false,
    val deleted: Boolean = false,
    val clonedJobId: String? = null,
    val accounts: List<au.mainspring.nativeapp.api.CustomerAccountRead> = emptyList(),
    val accountsLoading: Boolean = false,
    val accountBusy: Boolean = false,
    val catalogue: List<ShoeCatalogueItem> = emptyList(),
    val customerShoes: List<au.mainspring.nativeapp.api.ShoeRead> = emptyList(),
    val customerShoesLoading: Boolean = false,
    val smsLog: List<au.mainspring.nativeapp.api.SmsLogRead> = emptyList(),
    val resendBusy: Boolean = false,
    val resendInfo: String? = null,
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

    private val sms get() = ApiClient.service(au.mainspring.nativeapp.api.ShoeSmsApi::class.java)

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
                val smsLog = try { sms.shoeSmsLog(jobId) } catch (e: CancellationException) { throw e } catch (_: Exception) { _state.value.smsLog }
                val customerId = j.shoe?.customerId
                val customer = if (customerId == null) null else _state.value.customer?.takeIf { it.id == customerId }
                    ?: try { api.getCustomer(customerId) } catch (e: CancellationException) { throw e } catch (_: Exception) { null }
                _state.update { it.copy(loading = false, job = j, customer = customer, history = history, attachments = attachments, smsLog = smsLog, statusReviewed = true) }
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

    fun setStatus(newStatus: String, note: String? = null, customerNote: String? = null) {
        val snapshot = _state.value
        val current = snapshot.job ?: return
        if(snapshot.loading || snapshot.statusBusy || snapshot.statusUnknown || !TokenStore.canWorkJobs() || newStatus !in SHOE_JOB_STATUS_OPTIONS) return
        val message = note?.trim()?.takeIf { it.isNotEmpty() }
        val visibleNote = customerNote?.trim()?.takeIf { it.isNotEmpty() }?.take(SHOE_CUSTOMER_NOTE_MAX)
        if(newStatus == current.status && message == null && visibleNote == null) return
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
                val j = api.postShoeRepairJobStatus(jobId, ShoeStatusUpdate(newStatus, message, visibleNote))
                statusCheckpoint.clear()
                _state.update { it.copy(statusBusy = false, job = j, statusUnknown = false, statusRequest = "") }
                load()
            } catch(e: CancellationException) { throw e }
            catch (e: Exception) {
                if(OfflineSync.queueStatus(e, OfflineKinds.SHOE_STATUS, jobId, newStatus, message, visibleNote, "Shoe job", baseStatus = current.status)) {
                    statusCheckpoint.clear()
                    _state.update { it.copy(statusBusy = false, statusUnknown = false, statusRequest = "", info = null) }
                    return@launch
                }
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
                if(OfflineSync.queueNote(e, OfflineKinds.SHOE_NOTE, jobId, trimmed, "Shoe job")) {
                    _state.update { it.copy(noteBusy = false, info = OfflineSync.SAVED_OFFLINE_MESSAGE) }; return@launch
                }
                _state.update { it.copy(noteBusy = false, error = e.userMessage()) }
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
                _state.update { it.copy(claimBusy = false, error = e.userMessage()) }
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
                _state.update { it.copy(claimBusy = false, error = e.userMessage()) }
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

    fun loadCatalogue() {
        if(_state.value.catalogue.isNotEmpty()) return
        viewModelScope.launch {
            try {
                val base = api.shoeCatalogue()
                _state.update { it.copy(catalogue = base) }
                val custom = try { api.customShoeServices() } catch(e: CancellationException) { throw e } catch(_: Exception) { emptyList() }
                if(custom.isNotEmpty()) _state.update { it.copy(catalogue = (it.catalogue + custom).distinctBy { row -> row.key }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(error = e.userMessage()) } }
        }
    }

    /** Runs a job edit that returns the refreshed job; one edit at a time. */
    private fun edit(block: suspend () -> au.mainspring.nativeapp.api.ShoeRepairJobRead) {
        if(_state.value.editBusy || !TokenStore.canWorkJobs()) return
        _state.update { it.copy(editBusy = true, error = null) }
        viewModelScope.launch {
            try { val j = block(); _state.update { it.copy(editBusy = false, job = j) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(editBusy = false, error = e.userMessage()) } }
        }
    }
    fun addServices(items: List<ShoeItemCreate>) { if(items.isNotEmpty()) edit { api.appendShoeItems(jobId, ShoeItemsAppend(items)) } }
    fun removeService(itemId: String) = edit { api.removeShoeItem(jobId, itemId) }
    fun removePair(entryId: String) = edit { api.removeShoeFromJob(jobId, entryId) }
    fun addPair(type: String, brand: String, colour: String, notes: String) {
        val customerId = _state.value.job?.shoe?.customerId ?: return
        edit {
            val shoe = api.createShoe(ShoeCreate(customerId, type.trim().ifBlank { null }, brand.trim().ifBlank { null }, colour.trim().ifBlank { null }, notes.trim().ifBlank { null }))
            api.linkShoe(jobId, ShoeLink(shoe.id))
        }
    }

    /** Loads the customer's other shoes on file for "existing pair" in the Add pair dialog. */
    fun loadCustomerShoes() {
        val customerId = _state.value.job?.shoe?.customerId ?: return
        if(_state.value.customerShoesLoading) return
        _state.update { it.copy(customerShoesLoading = true) }
        viewModelScope.launch {
            try { val all = api.listShoes(customerId); _state.update { it.copy(customerShoesLoading = false, customerShoes = all) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(customerShoesLoading = false, error = e.userMessage()) } }
        }
    }
    fun addExistingPair(shoeId: String) { edit { api.linkShoe(jobId, ShoeLink(shoeId)) } }
    /** PATCH the shoe record (type, brand, colour, notes), then reload the job so every pair card reflects it. */
    fun editShoe(shoeId: String, type: String, brand: String, colour: String, notes: String) {
        edit { api.updateShoe(shoeId, shoeUpdateBody(type, brand, colour, notes)); api.getShoeRepairJob(jobId) }
    }

    private val admin get() = ApiClient.service(au.mainspring.nativeapp.api.JobAdminApi::class.java)

    /** Owner/manager only (web hides delete from other roles). Sets [ShoeJobDetailUiState.deleted] on success. */
    fun deleteJob() {
        val snapshot = _state.value
        if(snapshot.job == null || snapshot.adminBusy || snapshot.statusBusy || !TokenStore.canManageInvoices()) return
        _state.update { it.copy(adminBusy = true, error = null) }
        viewModelScope.launch {
            try {
                admin.deleteShoeJob(jobId).let { r -> if(!r.isSuccessful) throw retrofit2.HttpException(r); r.body()?.close() }
                _state.update { it.copy(adminBusy = false, deleted = true) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(adminBusy = false, error = e.userMessage()) } }
        }
    }

    /** Duplicates the job (POST /shoe-repair-jobs/{id}/clone); the new id lands in [ShoeJobDetailUiState.clonedJobId]. */
    fun duplicateJob() {
        val snapshot = _state.value
        if(snapshot.job == null || snapshot.adminBusy || snapshot.statusBusy || !TokenStore.canWorkJobs()) return
        _state.update { it.copy(adminBusy = true, error = null) }
        viewModelScope.launch {
            try {
                val cloned = admin.cloneShoeJob(jobId)
                _state.update { it.copy(adminBusy = false, clonedJobId = cloned.id) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(adminBusy = false, error = e.userMessage()) } }
        }
    }
    /** Re-sends a customer SMS (`job_live` or `status_<status>`) and refreshes the SMS log. */
    fun resendNotification(event: String) {
        if (_state.value.resendBusy) return
        _state.update { it.copy(resendBusy = true, error = null, resendInfo = null) }
        viewModelScope.launch {
            try {
                val r = sms.resendShoeNotification(jobId, au.mainspring.nativeapp.api.ShoeResendRequest(event))
                val log = try { sms.shoeSmsLog(jobId) } catch (e: CancellationException) { throw e } catch (_: Exception) { _state.value.smsLog }
                _state.update { it.copy(resendBusy = false, smsLog = log, resendInfo = "SMS ${r.status} to ${r.toPhone}") }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(resendBusy = false, error = e.userMessage()) } }
        }
    }

    fun consumeClonedJob() { _state.update { it.copy(clonedJobId = null) } }

    fun loadAccounts() {
        if(_state.value.accountsLoading) return
        _state.update { it.copy(accountsLoading = true) }
        viewModelScope.launch {
            try {
                val accounts = api.listCustomerAccounts().filter { it.active }.sortedBy { it.name.lowercase() }
                _state.update { it.copy(accountsLoading = false, accounts = accounts) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(accountsLoading = false, error = e.userMessage()) } }
        }
    }

    /** Sets (or clears when null) the B2B customer account. */
    fun assignAccount(accountId: String?) {
        val snapshot = _state.value
        if(snapshot.job == null || snapshot.accountBusy || snapshot.statusBusy || !TokenStore.canWorkJobs()) return
        _state.update { it.copy(accountBusy = true, error = null) }
        viewModelScope.launch {
            try {
                val fields = com.google.gson.JsonObject()
                if(accountId == null) fields.add("customer_account_id", com.google.gson.JsonNull.INSTANCE) else fields.addProperty("customer_account_id", accountId)
                val j = api.updateCounterShoe(jobId, fields)
                _state.update { it.copy(accountBusy = false, job = j) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { _state.update { it.copy(accountBusy = false, error = e.userMessage()) } }
        }
    }

    companion object {
        const val SHOE_CUSTOMER_NOTE_MAX = 280
        fun factory(jobId: String, apiBaseUrl: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return ShoeJobDetailViewModel(jobId, apiBaseUrl) as T
            }
        }
    }
}

