package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.math.BigDecimal
import au.mainspring.nativeapp.ui.formatShopDate

data class CounterEditorState(val fields: Map<String,String> = emptyMap(), val loading: Boolean = true, val busy: Boolean = false,
 val saved: Boolean = false, val conflict: Boolean = false, val error: String? = null)
private data class CounterEditorDraft(val fields: Map<String,String>, val original: Map<String,String>)
class CounterEditorViewModel(private val resource: String, private val id: String): ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 init { require(resource in listOf("repair-jobs", "shoe-repair-jobs")) }
 private val mutable = MutableStateFlow(CounterEditorState()); val state = mutable.asStateFlow()
 private var original: Map<String,String> = emptyMap(); private var serverFields: Map<String,String> = emptyMap()
 private val key = "counter-edit/$resource/$id"
 private fun amount(cents: Int) = BigDecimal(cents).movePointLeft(2).toPlainString()
 private suspend fun readFields(): Map<String,String> = if(resource == "repair-jobs") {
  val job = api.getRepairJob(id)
  mapOf("job_number" to job.jobNumber, "title" to job.title, "description" to job.description.orEmpty(), "priority" to job.priority,
   "salesperson" to job.salesperson.orEmpty(), "collection_date" to job.collectionDate?.let { formatShopDate(it) }.orEmpty(),
   "deposit_cents" to amount(job.depositCents), "cost_cents" to amount(job.costCents), "pre_quote_cents" to amount(job.preQuoteCents),
   "internal_notes" to job.internalNotes.orEmpty(), "parts_eta" to job.partsEta?.let { formatShopDate(it) }.orEmpty())
 } else {
  val job = api.getShoeRepairJob(id)
  mapOf("title" to job.title, "description" to job.description.orEmpty(), "priority" to job.priority, "salesperson" to job.salesperson.orEmpty(),
   "collection_date" to job.collectionDate?.let { formatShopDate(it) }.orEmpty(), "deposit_cents" to amount(job.depositCents), "cost_cents" to amount(job.costCents))
 }
 init { load() }
 private fun load() { viewModelScope.launch { try {
  serverFields = readFields()
  val draft = try { Gson().fromJson(drafts.loadMessageDraft(key), CounterEditorDraft::class.java) } catch(_: Exception) { null }
  original = draft?.original ?: serverFields
  mutable.value = CounterEditorState(fields = draft?.fields ?: serverFields, loading = false, conflict = original != serverFields,
   error = if(original != serverFields) "This job changed since your draft. Review the current job and discard the draft before replacing newer changes." else null)
 } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } } } }
 fun set(key: String, value: String) { if(mutable.value.busy) return; mutable.update { it.copy(fields = it.fields + (key to value), saved = false) }
  drafts.saveMessageDraft(this.key, Gson().toJson(CounterEditorDraft(mutable.value.fields, original))) }
 fun discard() { if(mutable.value.busy) return; original = serverFields; drafts.saveMessageDraft(key, ""); mutable.update { it.copy(fields = serverFields, saved = false, conflict = false, error = null) } }
 fun save() {
  if(mutable.value.busy || mutable.value.loading || mutable.value.conflict || original.isEmpty()) return
  if(resource == "repair-jobs" && !TokenStore.canWorkJobs()) { mutable.update { it.copy(error = "A technician or manager must edit watch repair details.") }; return }
  val fields = mutable.value.fields
  try {
   require(fields["title"].orEmpty().isNotBlank()) { "A job title is required." }
   val changed = fields.filter { (key, value) -> original[key] != value }
   val body = JsonObject()
   changed.forEach { (key, value) -> when {
    key.endsWith("_cents") -> body.addProperty(key, dollarsToCentsChecked(value))
    key == "collection_date" || key == "parts_eta" -> {
     if(resource == "repair-jobs" && key == "collection_date" && value.isBlank() && !original[key].isNullOrBlank()) error("This API supports changing the collection date but cannot clear it. Set another date.")
     val iso = collectionDateIso(value); if(iso == null) body.add(key, JsonNull.INSTANCE) else body.addProperty(key, iso)
    }
    else -> body.addProperty(key, value.trim())
   } }
   if(body.size() == 0) { mutable.update { it.copy(saved = true) }; return }
   mutable.update { it.copy(busy = true, error = null) }
   viewModelScope.launch { try {
    val fresh = readFields()
    if(fresh != original) { serverFields = fresh; mutable.update { it.copy(busy = false, conflict = true, error = "This job changed while you were editing. Your draft is retained. Review the job and discard edits before replacing the newer details.") }; return@launch }
    if(resource == "repair-jobs") api.updateCounterWatch(id, body) else api.updateCounterShoe(id, body)
    val saved = readFields(); serverFields = saved; original = saved; drafts.saveMessageDraft(key, "")
    mutable.update { it.copy(busy = false, saved = true, fields = saved) }
   } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false, error = "Could not confirm changes. Reopen and review the job before saving again. ${e.userMessage()}") } } }
  } catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
 }
 companion object { fun factory(resource: String, id: String) = object: ViewModelProvider.Factory { @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = CounterEditorViewModel(resource, id) as T } }
}
