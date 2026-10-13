package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import com.google.gson.*

data class WorkLogsState(val rows: List<WorkLogRead> = emptyList(), val note: String = "", val minutes: String = "", val loading: Boolean = false,
 val busy: Boolean = false, val uncertain: Boolean = false, val historyChecked: Boolean = false, val error: String? = null)
class WorkLogsViewModel(private val jobId: String): ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val key = "work-log/$jobId"
 private val draft = try { JsonParser.parseString(drafts.loadMessageDraft(key)).asJsonObject } catch(_: Exception) { null }
 private val mutable = MutableStateFlow(WorkLogsState(note = draft?.get("note")?.asString.orEmpty(), minutes = draft?.get("minutes")?.asString.orEmpty(), uncertain = drafts.pendingOperation(key)))
 val state = mutable.asStateFlow()
 init { refresh() }
 fun note(text: String) { mutable.update { it.copy(note = text) }; persist() }
 fun minutes(text: String) { mutable.update { it.copy(minutes = text) }; persist() }
 private fun persist() { drafts.saveMessageDraft(key, JsonObject().apply { addProperty("note", mutable.value.note); addProperty("minutes", mutable.value.minutes) }.toString()) }
 fun refresh() { if(mutable.value.loading || mutable.value.busy) return; mutable.update { it.copy(loading = true, error = null) }
  viewModelScope.launch { try { val rows = api.workLogs(jobId); mutable.update { it.copy(loading = false, rows = rows.sortedByDescending { row -> row.createdAt }, historyChecked = true) } }
   catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } } }
 }
 fun checkedHistory() { if(!mutable.value.historyChecked) return; drafts.setPendingOperation(key, false); mutable.update { it.copy(uncertain = false) } }
 fun save() {
  if(mutable.value.loading || mutable.value.busy || mutable.value.uncertain) return
  val minutes = mutable.value.minutes.ifBlank { "0" }.toIntOrNull(); val note = mutable.value.note.trim()
  if(minutes == null || minutes !in 0..10080 || (minutes == 0 && note.isBlank())) { mutable.update { it.copy(error = "Enter a work note or a valid number of minutes (up to 10,080).") }; return }
  mutable.update { it.copy(busy = true, error = null) }
  viewModelScope.launch { try {
   check(drafts.setPendingOperation(key, true)) { "Could not save the work-log checkpoint. Check device storage and sign in before continuing." }
   val row = api.createWorkLog(WorkLogCreate(jobId, note.ifBlank { null }, minutes)); drafts.setPendingOperation(key, false); drafts.saveMessageDraft(key, "")
   mutable.update { it.copy(busy = false, rows = listOf(row) + it.rows, note = "", minutes = "") }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { val unknown = e !is retrofit2.HttpException || e.code() >= 500; drafts.setPendingOperation(key, unknown)
   mutable.update { it.copy(busy = false, uncertain = unknown, historyChecked = false, error = "Could not confirm the work log. Refresh and check before saving again. ${e.userMessage()}") } }
  }
 }
 companion object { fun factory(jobId: String) = object: ViewModelProvider.Factory { @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = WorkLogsViewModel(jobId) as T } }
}
