package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException
import java.time.*
import java.time.format.DateTimeFormatter

data class MobileEditorState(val fields: Map<String, String> = emptyMap(), val loading: Boolean = false, val busy: Boolean = false, val error: String? = null, val saved: Boolean = false,
 val users: List<TeamUser> = emptyList(), val teamError: String? = null,
 val accounts: List<CustomerAccountRead> = emptyList(), val accountError: String? = null)
class MobileEditorViewModel(private val id: String): ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val mutable = MutableStateFlow(MobileEditorState(loading = true)); val state = mutable.asStateFlow()
 private var original: Map<String, String> = emptyMap(); private var updatedAt: String? = null
 private var serverFields: Map<String, String> = emptyMap(); private var serverUpdatedAt: String? = null
 private var customerId: String = ""
 private val draftKey = "mobile-edit/$id"
 init { viewModelScope.launch { try {
  val job = api.getAutoKeyJob(id); updatedAt = job.updatedAt
  customerId = job.customerId
  var accountError: String? = null
  val accounts = try { api.listCustomerAccounts() } catch(e: CancellationException) { throw e } catch(e: Exception) {
   if(e !is retrofit2.HttpException || e.code() != 403) accountError = "Billing accounts unavailable. ${e.userMessage()}"
   emptyList()
  }
  val users = try { api.teamUsers() } catch(e: CancellationException) { throw e } catch(_: Exception) { emptyList() }
  val schedule = job.scheduledAt?.let { try { au.mainspring.nativeapp.ui.scheduleInputDate(it, TokenStore.calendarTimezone()) } catch(_: Exception) { it } }.orEmpty()
  original = mapOf("title" to job.title, "description" to job.description.orEmpty(), "job_address" to job.jobAddress.orEmpty(),
   "scheduled_at" to schedule, "vehicle_make" to job.vehicleMake.orEmpty(), "vehicle_model" to job.vehicleModel.orEmpty(),
   "vehicle_year" to job.vehicleYear?.toString().orEmpty(), "registration_plate" to job.registrationPlate.orEmpty(), "vin" to job.vin.orEmpty(),
   "key_type" to job.keyType.orEmpty(), "blade_code" to job.bladeCode.orEmpty(), "chip_type" to job.chipType.orEmpty(),
   "key_quantity" to job.keyQuantity.toString(), "tech_notes" to job.techNotes.orEmpty(), "programming_status" to job.programmingStatus,
   "assigned_user_id" to job.assignedUserId.orEmpty(), "customer_account_id" to job.customerAccountId.orEmpty())
  serverFields = original; serverUpdatedAt = updatedAt
  val draft = drafts.loadMessageDraft(draftKey)
  val restored = try { if(draft.isBlank()) null else Gson().fromJson(draft, EditorDraft::class.java) } catch(_: Exception) { null }
  if(restored != null) {
   original = original + restored.original; updatedAt = restored.updatedAt
   mutable.value = MobileEditorState(fields = original + restored.fields, users = users, accounts = accounts.filter { customerId in it.customerIds }, accountError = accountError, error = if(updatedAt != serverUpdatedAt) "This job changed since your draft. Review the latest job or discard this draft before replacing those changes." else null,
    teamError = if(users.isEmpty()) "No team members could be loaded. Reopen this job to refresh the team." else null)
  } else mutable.value = MobileEditorState(fields = original, users = users, accounts = accounts.filter { customerId in it.customerIds }, accountError = accountError, teamError = if(users.isEmpty()) "No team members could be loaded. Reopen this job to refresh the team." else null)
 } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.value = MobileEditorState(error = "Could not load this job. ${e.userMessage()}") } } }
 fun set(key: String, value: String) { if(mutable.value.loading || mutable.value.busy) return; mutable.update { it.copy(fields = it.fields + (key to value), saved = false) }; persist() }
 private fun persist() { drafts.saveMessageDraft(draftKey, Gson().toJson(EditorDraft(mutable.value.fields, original, updatedAt))) }
 fun discardDraft() { original = serverFields; updatedAt = serverUpdatedAt; drafts.saveMessageDraft(draftKey, ""); mutable.update { it.copy(fields = serverFields, error = null, saved = false) } }
 fun save() {
  if(mutable.value.busy || mutable.value.loading || original.isEmpty() || !TokenStore.canWorkJobs()) return
  val fields = mutable.value.fields
  try {
   require(fields["title"].orEmpty().isNotBlank()) { "A job title is required." }
   val quantity = fields["key_quantity"]?.toIntOrNull(); require(quantity != null && quantity in 1..10000) { "Enter a valid key quantity." }
   if(!fields["vehicle_year"].isNullOrBlank()) require(fields["vehicle_year"]?.toIntOrNull() != null) { "Enter a valid vehicle year." }
   val assigned = fields["assigned_user_id"].orEmpty()
   val account = fields["customer_account_id"].orEmpty()
   if(account != original["customer_account_id"] && account.isNotBlank()) require(mutable.value.accounts.any { it.id == account && it.active }) { "Choose an active billing account linked to this customer." }
   if(assigned != original["assigned_user_id"] && assigned.isNotBlank()) require(mutable.value.users.any { it.id == assigned && it.active }) { "Choose an active team member." }
   val body = JsonObject()
   fields.filter { (key, value) -> original[key] != value }.forEach { (key, value) ->
    when(key) {
     "scheduled_at" -> if(value.isBlank()) body.add(key, JsonNull.INSTANCE) else body.addProperty(key, scheduledTimeIso(value, TokenStore.calendarTimezone()))
     "vehicle_year", "key_quantity" -> if(value.isBlank()) body.add(key, JsonNull.INSTANCE) else body.addProperty(key, value.toInt())
     "assigned_user_id", "customer_account_id" -> if(value.isBlank()) body.add(key, JsonNull.INSTANCE) else body.addProperty(key, value)
     else -> body.addProperty(key, value.trim())
    }
   }
   if(body.size() == 0) { mutable.update { it.copy(saved = true) }; return }
   mutable.update { it.copy(busy = true, error = null) }
   viewModelScope.launch { try {
    val job = api.updateMobileJob(id, body, updatedAt); updatedAt = job.updatedAt; original = fields; serverFields = fields; serverUpdatedAt = updatedAt
    drafts.saveMessageDraft(draftKey, "")
    mutable.update { it.copy(busy = false, saved = true) }
   } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false, error = if(e is retrofit2.HttpException && e.code() == 409) "This job changed while you were editing. Reopen it and review the latest details before saving." else "Could not confirm changes. Review the job before saving again. ${e.userMessage()}") } } }
  } catch(e: Exception) { mutable.update { it.copy(error = e.message) } }
 }
 companion object { fun factory(id: String) = object: ViewModelProvider.Factory { @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = MobileEditorViewModel(id) as T } }
}
private data class EditorDraft(val fields: Map<String, String>, val original: Map<String, String>, val updatedAt: String?)

