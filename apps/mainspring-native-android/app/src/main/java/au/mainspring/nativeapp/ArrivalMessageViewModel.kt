package au.mainspring.nativeapp

import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class ArrivalDraft(val window: String = "", val accepted: Boolean = false)
data class ArrivalState(val draft: ArrivalDraft = ArrivalDraft(), val customer: CustomerRead? = null, val loading: Boolean = false,
    val busy: Boolean = false, val uncertain: Boolean = false, val error: String? = null, val info: String? = null)

class ArrivalMessageViewModel(private val id: String) : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val key = "arrival/$id"
    private val restored = try { Gson().fromJson(drafts.loadMessageDraft(key), ArrivalDraft::class.java) ?: ArrivalDraft() } catch(_: Exception) { ArrivalDraft() }
    private val mutable = MutableStateFlow(ArrivalState(draft = restored, uncertain = drafts.pendingOperation(key)))
    val state = mutable.asStateFlow()
    init { refresh() }
    private fun persist(value: ArrivalDraft) { drafts.saveMessageDraft(key,Gson().toJson(value)); mutable.update { it.copy(draft = value) } }
    fun window(value: String) { if(!mutable.value.busy && !mutable.value.uncertain && !mutable.value.draft.accepted) persist(mutable.value.draft.copy(window = value)) }
    fun startUpdatedWindow() { if(!mutable.value.busy && !mutable.value.uncertain) persist(mutable.value.draft.copy(accepted = false)) }
    fun refresh() {
        if(mutable.value.loading || mutable.value.busy) return
        mutable.update { it.copy(loading = true, customer = null, error = null) }
        viewModelScope.launch {
            try { val job = api.getAutoKeyJob(id); val customer = api.getCustomer(job.customerId); mutable.update { it.copy(customer = customer, loading = false) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun checkedCustomer() {
        if(mutable.value.loading || mutable.value.busy || mutable.value.customer == null) return
        drafts.setPendingOperation(key,false); mutable.update { it.copy(uncertain = false, info = "Customer check acknowledged. Review the window before sending again.") }
    }
    fun send() {
        val snapshot = mutable.value
        if(snapshot.loading || snapshot.busy || snapshot.uncertain || snapshot.draft.accepted || !TokenStore.canWorkJobs()) return
        val window = snapshot.draft.window.trim()
        if(window.isBlank() || window.length > 200) { mutable.update { it.copy(error = "Enter an arrival window within 200 characters.") }; return }
        if(snapshot.customer?.phone.isNullOrBlank()) { mutable.update { it.copy(error = "Add the customer's phone number before sending an arrival SMS.") }; return }
        mutable.update { it.copy(busy = true, error = null, info = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                require(api.session().mobileSmsEnabled) { "Customer SMS is disabled for this shop. Call the customer to confirm your arrival window." }
                check(drafts.setPendingOperation(key,true)) { "Could not save the message checkpoint. Check device storage and sign in before continuing." }
                submitted = true
                require(api.arrivalSms(id,ArrivalSmsRequest(window)).ok) { "The server did not acknowledge this arrival request." }
                persist(ArrivalDraft(window,accepted = true)); drafts.setPendingOperation(key,false)
                mutable.update { it.copy(info = "Arrival SMS request accepted. The server does not report delivery status for this message.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val unknown = submitted && (e !is HttpException || e.code() >= 500)
                drafts.setPendingOperation(key,unknown)
                mutable.update { it.copy(uncertain = unknown, error = if(unknown) "The message result is unknown. Check with the customer before sending it again. ${e.userMessage()}" else e.userMessage()) }
            } finally { mutable.update { it.copy(busy = false) } }
        }
    }
    companion object { fun factory(id: String) = object: ViewModelProvider.Factory { @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = ArrivalMessageViewModel(id) as T } }
}
