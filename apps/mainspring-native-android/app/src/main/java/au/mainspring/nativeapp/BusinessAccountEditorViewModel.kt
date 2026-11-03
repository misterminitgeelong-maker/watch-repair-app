package au.mainspring.nativeapp

import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class AccountEditorDraft(val fields: Map<String,String>, val original: Map<String,String>, val createdId: String? = null)
data class AccountEditorState(val fields: Map<String,String> = emptyMap(), val loading: Boolean = false, val busy: Boolean = false,
    val error: String? = null, val saved: Boolean = false, val createdId: String? = null, val uncertain: Boolean = false,
    val accounts: List<CustomerAccountRead> = emptyList(), val historyChecked: Boolean = false, val conflict: Boolean = false)

class BusinessAccountEditorViewModel(private val id: String) : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val key = "account-edit/${id.ifBlank { "new" }}"
    private val restored = try { Gson().fromJson(drafts.loadMessageDraft(key), AccountEditorDraft::class.java) } catch(_: Exception) { null }
    private var original = restored?.original ?: emptyMap()
    private val mutable = MutableStateFlow(AccountEditorState(fields = restored?.fields ?: mapOf("payment_terms_days" to "30", "is_active" to "true"),
        createdId = restored?.createdId, uncertain = drafts.pendingOperation(key)))
    val state = mutable.asStateFlow()
    init { if(id.isNotBlank() || mutable.value.uncertain) refresh() }
    private fun fields(account: CustomerAccountRead) = mapOf(
        "name" to account.name, "account_code" to account.code.orEmpty(), "contact_name" to account.contactName.orEmpty(),
        "contact_email" to account.email.orEmpty(), "contact_phone" to account.phone.orEmpty(), "billing_address" to account.address.orEmpty(),
        "payment_terms_days" to account.terms.toString(), "notes" to account.notes.orEmpty(), "account_type" to account.type.orEmpty(),
        "fleet_size" to account.fleetSize?.toString().orEmpty(), "primary_contact_name" to account.primaryContact.orEmpty(),
        "primary_contact_phone" to account.primaryPhone.orEmpty(), "billing_cycle" to account.billingCycle.orEmpty(),
        "credit_limit" to account.creditLimit?.toString().orEmpty(), "account_notes" to account.accountNotes.orEmpty(), "is_active" to account.active.toString())
    private fun persist() { drafts.saveMessageDraft(key, Gson().toJson(AccountEditorDraft(mutable.value.fields, original, mutable.value.createdId))) }
    fun set(key: String, value: String) {
        if(mutable.value.busy || mutable.value.loading || mutable.value.createdId != null || mutable.value.uncertain) return
        mutable.update { it.copy(fields = it.fields + (key to value), saved = false) }; persist()
    }
    fun refresh(discard: Boolean = false) {
        if(mutable.value.loading || mutable.value.busy) return
        mutable.update { it.copy(loading = true, error = null, historyChecked = false) }
        viewModelScope.launch {
            try {
                if(id.isNotBlank()) {
                    val current = fields(api.customerAccount(id))
                    val useServer = discard || original.isEmpty()
                    if(useServer) original = current
                    mutable.update { it.copy(fields = if(useServer) current else it.fields,
                        loading = false, conflict = !useServer && original != current, error = if(!useServer && original != current) "This account changed since your draft. Discard edits to use the current account." else null) }
                    if(discard) persist()
                } else {
                    val accounts = api.listCustomerAccounts(); mutable.update { it.copy(accounts = accounts, loading = false, historyChecked = true) }
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun checkedAccounts() { if(mutable.value.historyChecked && !mutable.value.busy) { drafts.setPendingOperation(key, false); mutable.update { it.copy(uncertain = false) } } }
    fun useExisting(accountId: String) {
        if(!mutable.value.historyChecked || mutable.value.busy) return
        val account = mutable.value.accounts.firstOrNull { it.id == accountId } ?: return
        original = fields(account); mutable.update { it.copy(fields = original, createdId = account.id, uncertain = false, saved = true) }
        persist(); drafts.setPendingOperation(key,false)
    }
    fun startAnother() { if(mutable.value.busy || mutable.value.uncertain) return
        original = emptyMap(); mutable.value = AccountEditorState(fields = mapOf("payment_terms_days" to "30", "is_active" to "true")); persist() }
    fun save() {
        val snapshot = mutable.value
        if(snapshot.loading || snapshot.busy || snapshot.uncertain || snapshot.createdId != null || snapshot.conflict || !TokenStore.canManageInvoices()) return
        try {
            val values = snapshot.fields.mapValues { it.value.trim() }
            require(values["name"].orEmpty().isNotBlank()) { "An account name is required." }
            mapOf("name" to 128, "account_code" to 32, "contact_name" to 64, "contact_email" to 64, "contact_phone" to 32,
                "billing_address" to 256, "notes" to 256, "primary_contact_name" to 64, "primary_contact_phone" to 32, "account_notes" to 256)
                .forEach { (field,max) -> require(values[field].orEmpty().length <= max) { "${field.replace('_',' ')} must be within $max characters." } }
            val body = JsonObject()
            values.filter { (field,value) -> (id.isBlank() && field != "is_active") || (id.isNotBlank() && original[field].orEmpty() != value) }.forEach { (field,value) ->
                when(field) {
                    "payment_terms_days", "fleet_size", "credit_limit" -> {
                        val number = value.toIntOrNull()
                        if(value.isBlank() && field != "payment_terms_days") body.add(field, JsonNull.INSTANCE)
                        else { require(number != null && number >= 0) { "Enter a non-negative whole number for ${field.replace('_',' ')}." }; body.addProperty(field,number) }
                    }
                    "is_active" -> body.addProperty(field, value == "true")
                    "account_type" -> { require(value.isBlank() || value in accountTypes) { "Choose a valid account type." }; if(value.isBlank()) body.add(field,JsonNull.INSTANCE) else body.addProperty(field,value) }
                    "billing_cycle" -> { require(value.isBlank() || value in billingCycles) { "Choose a valid billing cycle." }; if(value.isBlank()) body.add(field,JsonNull.INSTANCE) else body.addProperty(field,value) }
                    else -> if(value.isBlank() && field != "name") body.add(field,JsonNull.INSTANCE) else body.addProperty(field,value)
                }
            }
            if(body.size() == 0) { mutable.update { it.copy(saved = true) }; return }
            mutable.update { it.copy(busy = true, error = null) }
            viewModelScope.launch {
                var submitted = false
                try {
                    if(id.isNotBlank() && fields(api.customerAccount(id)) != original) {
                        mutable.update { it.copy(conflict = true) }; error("This account changed while you were editing. Discard edits and review the current account.")
                    }
                    if(id.isBlank()) check(drafts.setPendingOperation(key,true)) { "Could not save the account checkpoint. Check device storage and sign in before continuing." }
                    submitted = true
                    val account = if(id.isBlank()) api.createBusinessAccount(body) else api.updateBusinessAccount(id,body)
                    original = fields(account)
                    mutable.update { it.copy(fields = original, saved = true, createdId = account.id.takeIf { id.isBlank() }) }
                    persist(); drafts.setPendingOperation(key,false)
                } catch(e: CancellationException) { throw e }
                catch(e: Exception) {
                    val unknown = id.isBlank() && submitted && (e !is HttpException || e.code() >= 500)
                    drafts.setPendingOperation(key,unknown)
                    mutable.update { it.copy(uncertain = unknown, historyChecked = false, error = if(unknown) "The account creation result is unknown. Refresh and check accounts before saving again. ${e.userMessage()}" else e.userMessage()) }
                } finally { mutable.update { it.copy(busy = false) } }
            }
        } catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
    }
    companion object {
        val accountTypes = listOf("Dealership", "Rental Fleet", "Government Fleet", "Corporate Fleet", "Car Auctions", "Other")
        val billingCycles = listOf("Monthly", "Fortnightly", "Weekly")
        fun factory(id: String) = object: ViewModelProvider.Factory { @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = BusinessAccountEditorViewModel(id) as T }
    }
}
