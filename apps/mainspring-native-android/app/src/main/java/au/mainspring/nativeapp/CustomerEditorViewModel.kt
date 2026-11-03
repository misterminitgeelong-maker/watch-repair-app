package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class CustomerEditorState(val customer: CustomerRead? = null, val loading: Boolean = false,
    val saving: Boolean = false, val saved: Boolean = false, val error: String? = null,
    val unknown: Boolean = false, val reviewed: Boolean = false, val matches: List<CustomerRead> = emptyList(),
    val conflict: Boolean = false, val revision: Int = 0)
class CustomerEditorViewModel(private val customerId: String) : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    private val originalKey = "customer-original/$customerId"
    private var original = runCatching { Gson().fromJson(drafts.loadMessageDraft(originalKey), CustomerRead::class.java) }.getOrNull()
    private val created = if(customerId.isBlank()) runCatching { Gson().fromJson(drafts.loadMessageDraft("new-customer-result"), CustomerRead::class.java) }.getOrNull() else null
    private val mutable = MutableStateFlow(CustomerEditorState(customer = created, saved = created != null, unknown = created == null && customerId.isBlank() && drafts.pendingOperation("new-customer")))
    val state = mutable.asStateFlow()
    fun changed() { if(customerId.isNotBlank()) mutable.update { it.copy(saved = false) } }
    init { if(customerId.isNotBlank()) load() }
    private fun fields(customer: CustomerRead) = mapOf("full_name" to customer.fullName, "email" to customer.email.orEmpty(), "phone" to customer.phone.orEmpty(), "address" to customer.address.orEmpty(), "notes" to customer.notes.orEmpty())
    private fun baseline(customer: CustomerRead) { original = customer; drafts.saveMessageDraft(originalKey, Gson().toJson(customer)) }
    fun load(discard: Boolean = false) { if(customerId.isBlank() || mutable.value.loading || mutable.value.saving) return
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
        try { val customer = api.getCustomer(customerId)
            val legacy = original == null && drafts.loadMessageDraft("customer-editor/$customerId").isNotBlank()
            val conflict = !discard && (legacy || original?.let { fields(it) != fields(customer) } == true)
            if(discard || (original == null && !legacy)) baseline(customer)
            mutable.update { it.copy(loading = false, customer = customer, saved = if(discard) false else it.saved, conflict = conflict, revision = it.revision + if(discard) 1 else 0,
                error = if(conflict) "This customer changed, or the draft has no original checkpoint. Discard edits and review the latest customer." else null) }
        }
        catch(e: CancellationException) { throw e }
        catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
    } }
    fun save(name: String, email: String, phone: String, address: String, notes: String) {
        if(mutable.value.loading || mutable.value.saving || mutable.value.unknown || mutable.value.conflict || (customerId.isBlank() && mutable.value.saved) || (customerId.isNotBlank() && original == null)) return
        if(name.isBlank()) { mutable.update { it.copy(error = "Customer name is required.") }; return }
        mutable.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            try {
                val body = CustomerCreate(name.trim(), phone.trim(), email.trim(), address.trim(), notes.trim())
                if(customerId.isBlank()) check(drafts.setPendingOperation("new-customer", true)) { "Could not save the customer checkpoint. Check device storage and sign in before continuing." }
                val c = if(customerId.isBlank()) api.createCustomer(body) else {
                    val current = api.getCustomer(customerId)
                    if(fields(current) != fields(original!!)) {
                        mutable.update { it.copy(saving = false, customer = current, conflict = true, error = "This customer changed while you were editing. Discard edits and review the latest customer.") }; return@launch
                    }
                    val values = mapOf("full_name" to name.trim(), "email" to email.trim(), "phone" to phone.trim(), "address" to address.trim(), "notes" to notes.trim())
                    val patch = JsonObject()
                    values.filter { (field,value) -> fields(original!!)[field] != value }.forEach { (field,value) ->
                        if(value.isBlank() && field != "full_name") patch.add(field, JsonNull.INSTANCE) else patch.addProperty(field,value)
                    }
                    if(patch.size() == 0) current else api.updateCustomerFields(customerId, patch)
                }
                if(customerId.isBlank()) { drafts.saveMessageDraft("new-customer-result", Gson().toJson(c)); drafts.setPendingOperation("new-customer", false) }
                else baseline(c)
                mutable.update { it.copy(saving = false, saved = true, customer = c) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { val unknown = customerId.isBlank() && (e !is retrofit2.HttpException || e.code() >= 500)
                if(customerId.isBlank()) drafts.setPendingOperation("new-customer", unknown)
                mutable.update { it.copy(saving = false, unknown = unknown, reviewed = false, error = "Could not confirm changes. Review customer records before retrying. ${e.userMessage()}") } }
        }
    }
    fun reviewRecords(name: String) { if(mutable.value.saving || mutable.value.loading) return; mutable.update { it.copy(loading = true) }
        viewModelScope.launch { try { val matches = api.listCustomers(q = name.trim().ifBlank { null }, limit = 200); mutable.update { it.copy(loading = false, reviewed = true, matches = matches) } }
        catch(e: CancellationException) { throw e }
        catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } } }
    }
    fun confirmNotSaved() { if(!mutable.value.reviewed) return; drafts.setPendingOperation("new-customer", false); mutable.update { it.copy(unknown = false) } }
    fun useExisting(id: String) {
        if(!mutable.value.reviewed || mutable.value.saving || mutable.value.loading || customerId.isNotBlank()) return
        val customer = mutable.value.matches.find { it.id == id } ?: return
        drafts.saveMessageDraft("new-customer-result", Gson().toJson(customer)); drafts.setPendingOperation("new-customer", false)
        mutable.update { it.copy(customer = customer, saved = true, unknown = false, revision = it.revision + 1) }
    }
    fun startAnother() {
        if(customerId.isNotBlank() || mutable.value.loading || mutable.value.saving || mutable.value.unknown) return
        drafts.saveMessageDraft("new-customer-result", ""); drafts.saveMessageDraft("customer-editor/new", "")
        mutable.value = CustomerEditorState(revision = mutable.value.revision + 1)
    }
    companion object { fun factory(id: String) = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = CustomerEditorViewModel(id) as T
    } }
}
