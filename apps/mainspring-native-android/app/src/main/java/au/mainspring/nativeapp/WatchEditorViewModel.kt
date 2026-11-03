package au.mainspring.nativeapp

import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

private data class WatchEditorDraft(val fields: Map<String,String>, val original: Map<String,String>, val createdId: String? = null)
data class WatchEditorState(val fields: Map<String,String> = emptyMap(), val loading: Boolean = false, val busy: Boolean = false,
    val saved: Boolean = false, val createdId: String? = null, val conflict: Boolean = false, val uncertain: Boolean = false,
    val reviewed: Boolean = false, val matches: List<WatchRead> = emptyList(), val error: String? = null)

class WatchEditorViewModel(private val customerId: String, private val id: String) : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val key = "watch-edit/$customerId/${id.ifBlank { "new" }}"
    private val restored = runCatching { Gson().fromJson(drafts.loadMessageDraft(key), WatchEditorDraft::class.java) }.getOrNull()
    private var original = restored?.original ?: emptyMap()
    private val mutable = MutableStateFlow(WatchEditorState(fields = restored?.fields ?: emptyMap(), createdId = restored?.createdId,
        saved = restored?.createdId != null, uncertain = drafts.pendingOperation(key)))
    val state = mutable.asStateFlow()
    init { if(id.isNotBlank()) load() }
    private fun fields(watch: WatchRead) = mapOf("brand" to watch.brand.orEmpty(), "model" to watch.model.orEmpty(), "serial_number" to watch.serialNumber.orEmpty(),
        "movement_type" to watch.movementType.orEmpty(), "condition_notes" to watch.conditionNotes.orEmpty())
    private fun persist() { drafts.saveMessageDraft(key, Gson().toJson(WatchEditorDraft(state.value.fields, original, state.value.createdId))) }
    fun set(field: String, value: String) {
        if(state.value.loading || state.value.busy || state.value.uncertain || state.value.createdId != null) return
        mutable.update { it.copy(fields = it.fields + (field to value), saved = false) }; persist()
    }
    fun load(discard: Boolean = false) {
        if(id.isBlank() || state.value.loading || state.value.busy) return
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val watch = api.getWatch(id)
                require(watch.customerId == customerId) { "This watch belongs to a different customer. Reopen its current customer profile." }
                val latest = fields(watch)
                val replace = discard || original.isEmpty()
                if(replace) original = latest
                mutable.update { it.copy(loading = false, fields = if(replace) latest else it.fields, saved = false, conflict = !replace && original != latest,
                    error = if(!replace && original != latest) "This watch changed since your draft. Discard edits and review its current details." else null) }
                persist()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun save() {
        val s = state.value
        if(s.loading || s.busy || s.uncertain || s.conflict || s.createdId != null || (id.isNotBlank() && original.isEmpty())) return
        val values = s.fields.mapValues { it.value.trim() }
        if(values.values.none { it.isNotBlank() }) { mutable.update { it.copy(error = "Enter identifying watch details or condition notes.") }; return }
        mutable.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                if(id.isNotBlank()) {
                    val current = api.getWatch(id)
                    if(current.customerId != customerId || fields(current) != original) {
                        mutable.update { it.copy(busy = false, conflict = true, error = "This watch changed while you were editing. Discard edits and review the latest watch.") }; return@launch
                    }
                }
                val body = JsonObject()
                values.filter { (field,value) -> id.isBlank() || original[field] != value }.forEach { (field,value) ->
                    if(value.isBlank()) body.add(field, JsonNull.INSTANCE) else body.addProperty(field,value)
                }
                if(id.isNotBlank() && body.size() == 0) { mutable.update { it.copy(busy = false, saved = true) }; return@launch }
                if(id.isBlank()) check(drafts.setPendingOperation(key, true)) { "Could not retain the watch checkpoint. Check storage and sign in again." }
                submitted = true
                val watch = if(id.isBlank()) api.createWatch(WatchCreate(customerId, values["brand"]?.ifBlank { null }, values["model"]?.ifBlank { null },
                    values["serial_number"]?.ifBlank { null }, values["condition_notes"]?.ifBlank { null }, values["movement_type"]?.ifBlank { null })) else api.updateWatch(id, body)
                original = fields(watch)
                mutable.update { it.copy(busy = false, saved = true, fields = original, createdId = if(id.isBlank()) watch.id else null) }
                persist(); if(id.isBlank()) drafts.setPendingOperation(key, false)
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val uncertain = id.isBlank() && submitted && (e !is retrofit2.HttpException || e.code() >= 500)
                if(id.isBlank()) drafts.setPendingOperation(key, uncertain)
                mutable.update { it.copy(busy = false, uncertain = uncertain, reviewed = false, error = e.userMessage()) }
            }
        }
    }
    fun review() {
        if(id.isNotBlank() || state.value.busy || state.value.loading) return
        mutable.update { it.copy(loading = true, reviewed = false, error = null) }
        viewModelScope.launch {
            try {
                var offset = 0; val rows = mutableListOf<WatchRead>()
                do { val page = api.listWatches(customerId = customerId, limit = 200, offset = offset); rows.addAll(page); offset += page.size } while(page.size == 200)
                mutable.update { it.copy(loading = false, reviewed = true, matches = rows.distinctBy { watch -> watch.id }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun useExisting(watchId: String) {
        if(!state.value.reviewed || state.value.loading || state.value.busy) return
        val watch = state.value.matches.find { it.id == watchId && it.customerId == customerId } ?: return
        original = fields(watch); mutable.update { it.copy(fields = original, createdId = watch.id, uncertain = false, saved = true) }
        persist(); drafts.setPendingOperation(key, false)
    }
    fun reviewedNotCreated() {
        if(!state.value.reviewed || state.value.loading || state.value.busy) return
        drafts.setPendingOperation(key, false); mutable.update { it.copy(uncertain = false) }
    }
    fun another() {
        if(id.isNotBlank() || state.value.busy || state.value.loading || state.value.uncertain) return
        original = emptyMap(); mutable.value = WatchEditorState(); persist()
    }
    companion object { fun factory(customerId: String, id: String) = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>) = WatchEditorViewModel(customerId, id) as T
    } }
}
