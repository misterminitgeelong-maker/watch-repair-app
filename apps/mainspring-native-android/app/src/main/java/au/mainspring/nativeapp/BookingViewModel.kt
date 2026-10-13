package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class BookingState(val rows: List<BookingRequest> = emptyList(), val total: Int = 0, val operators: List<BookingOperator> = emptyList(),
 val fields: Map<String,String> = emptyMap(), val loading: Boolean = false, val busy: Boolean = false, val error: String? = null, val info: String? = null,
 val uncertain: Boolean = false, val historyChecked: Boolean = false)
class BookingViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val draftKey = "booking-request"
 private fun restored(): Map<String,String> = try { Gson().fromJson(drafts.loadMessageDraft(draftKey).ifBlank { "{}" }, object: TypeToken<Map<String,String>>(){}.type) ?: emptyMap() } catch(_: Exception) { emptyMap() }
 private val mutable = MutableStateFlow(BookingState(fields = restored(), uncertain = drafts.pendingOperation(draftKey))); val state = mutable.asStateFlow()
 init { refresh() }
 fun set(key: String, value: String) { mutable.update { it.copy(fields = it.fields + (key to value)) }; drafts.saveMessageDraft(draftKey, Gson().toJson(mutable.value.fields)) }
 fun discard() { if(mutable.value.busy) return; drafts.saveMessageDraft(draftKey, ""); mutable.update { it.copy(fields = emptyMap()) } }
 fun refresh() { if(mutable.value.busy || mutable.value.loading) return; fetch(false) }
 fun loadMore() { if(mutable.value.busy || mutable.value.loading || mutable.value.rows.size >= mutable.value.total) return; fetch(true) }
 private fun fetch(append: Boolean) { mutable.update { it.copy(loading = true, error = null) }; viewModelScope.launch { try {
  val page = api.bookingRequests(if(append) mutable.value.rows.size else 0)
  val operators = try { api.bookingOperators() } catch(_: Exception) { emptyList() }
  mutable.update { it.copy(loading = false, rows = if(append) (it.rows + page.items).distinctBy { row -> row.id } else page.items, total = page.total, operators = operators, historyChecked = true) }
 } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not refresh booking requests. ${e.userMessage()}") } } } }
 fun checkedHistory() { if(!mutable.value.historyChecked) return; drafts.setPendingOperation(draftKey, false); mutable.update { it.copy(uncertain = false) } }
 fun create(onCreated: () -> Unit) {
  if(mutable.value.busy || mutable.value.loading || mutable.value.uncertain) return
  val fields = mutable.value.fields; fun f(key: String) = fields[key].orEmpty().trim()
  try {
   require(listOf("customer_name", "suburb", "state_code", "job_address").all { f(it).isNotBlank() }) { "Enter customer name, suburb, state and job address." }
   require(f("state_code") in listOf("ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA")) { "Choose an Australian state or territory." }
   val body = JsonObject(); fields.filter { (key, value) -> key != "preferred_scheduled_at" && value.isNotBlank() }.forEach { (key, value) -> body.addProperty(key, value.trim()) }
   if(f("preferred_scheduled_at").isNotBlank()) body.addProperty("preferred_scheduled_at", scheduledTimeIso(f("preferred_scheduled_at"), TokenStore.calendarTimezone()))
   if(!body.has("visit_location_type")) body.addProperty("visit_location_type", "customer_site")
   check(drafts.setPendingOperation(draftKey, true)) { "Could not save the booking checkpoint. Check device storage and sign in before continuing." }
   runAction { try {
    val row = api.createBookingRequest(body); drafts.setPendingOperation(draftKey, false); drafts.saveMessageDraft(draftKey, "")
    mutable.update { it.copy(fields = emptyMap(), rows = listOf(row) + it.rows, total = it.total + 1, info = "Booking request sent to ${row.operator}.") }; onCreated()
   } catch(e: Exception) { val unknown = e !is retrofit2.HttpException || e.code() >= 500; drafts.setPendingOperation(draftKey, unknown); mutable.update { it.copy(uncertain = unknown, historyChecked = false) }; throw e } }
  } catch(e: Exception) { mutable.update { it.copy(error = e.message) } }
 }
 fun action(id: String, action: String, reason: String = "") = runAction {
  require(action in listOf("accept", "decline", "cancel")); val body = JsonObject(); if(action == "decline") body.addProperty("decline_reason", reason.trim())
  val row = api.bookingAction(id, action, body); mutable.update { it.copy(rows = it.rows.map { old -> if(old.id == id) row else old }, info = "Request ${row.status}.") }
 }
 private fun runAction(action: suspend () -> Unit) { if(mutable.value.busy || mutable.value.loading) return; mutable.update { it.copy(busy = true, error = null, info = null) }
  viewModelScope.launch { try { action() } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(error = "Could not confirm this action. Refresh booking requests before repeating it. ${e.userMessage()}") } }
   finally { mutable.update { it.copy(busy = false) } } }
 }
}

