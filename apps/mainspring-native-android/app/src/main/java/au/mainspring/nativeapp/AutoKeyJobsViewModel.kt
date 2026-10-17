package au.mainspring.nativeapp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
data class AutoKeyJobsUiState(val loading: Boolean = false, val error: String? = null, val jobs: List<AutoKeyJobRead> = emptyList(),
 val query: String = "", val directory: String = "active", val focus: String? = null, val total: Int = 0, val day: String? = null,
 val movingId: String? = null, val moveToast: au.mainspring.nativeapp.ui.screens.BoardMoveToast? = null)
class AutoKeyJobsViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
 private val mutable = MutableStateFlow(AutoKeyJobsUiState()); val state = mutable.asStateFlow(); private var request: Job? = null
 init { refresh() }
 fun query(text: String) { mutable.update { it.copy(query = text.take(200)) }; fetch(false, true) }
 fun directory(value: String) { require(value in listOf("active", "completed", "all")); mutable.update { it.copy(directory = value, focus = null) }; fetch(false) }
 fun focus(value: String?) { mutable.update { it.copy(focus = value, day = null) }; fetch(false) }
 fun day(value: String?) {
  if(value != null) try { java.time.LocalDate.parse(value) } catch(_: Exception) { mutable.update { it.copy(error = "Choose a valid schedule date.") }; return }
  mutable.update { it.copy(day = value, focus = null, directory = if(value != null) "all" else it.directory) }; fetch(false)
 }
 fun shiftDay(days: Long) { mutable.value.day?.let { day(java.time.LocalDate.parse(it).plusDays(days).toString()) } }
 fun refresh() { fetch(false) }
 /** Board "Move to": same status endpoint as the job screen (with the version the user saw); a network failure queues it. */
 fun moveJob(id: String, status: String, label: String, reason: String? = null, showToast: Boolean = true) {
  if(mutable.value.movingId != null) return
  val job = mutable.value.jobs.firstOrNull { it.id == id } ?: return
  if(job.status == status) return
  val note = reason?.trim()?.takeIf { it.isNotEmpty() }
  mutable.update { it.copy(movingId = id, error = null, moveToast = null) }
  viewModelScope.launch {
   try {
    val updated = api.postAutoKeyJobStatus(id, RepairJobStatusUpdate(status = status, note = note), job.updatedAt)
    val extra = if(updated.invoiceCreated == true) "An invoice was created" else null
    mutable.update { s -> s.copy(movingId = null, jobs = s.jobs.map { if(it.id == id) updated else it },
     moveToast = if(showToast) au.mainspring.nativeapp.ui.screens.BoardMoveToast(id, job.status, status, label, false, extra) else null) }
   } catch(e: CancellationException) { throw e }
   catch(e: Exception) {
    if(au.mainspring.nativeapp.offline.OfflineSync.queueStatus(e, au.mainspring.nativeapp.offline.OfflineKinds.MOBILE_STATUS, id, status, note, null, "Mobile job", expectedUpdatedAt = job.updatedAt)) {
     mutable.update { s -> s.copy(movingId = null, jobs = s.jobs.map { if(it.id == id) it.copy(status = status) else it },
      moveToast = if(showToast) au.mainspring.nativeapp.ui.screens.BoardMoveToast(id, job.status, status, label, true) else null) }
    } else mutable.update { it.copy(movingId = null, error = "Could not move this job. ${e.userMessage()}") }
   }
  }
 }
 fun clearMoveToast() { mutable.update { it.copy(moveToast = null) } }
 fun loadMore() { if(mutable.value.loading || mutable.value.jobs.size >= mutable.value.total) return; fetch(true) }
 private fun fetch(append: Boolean, debounce: Boolean = false) {
  request?.cancel(); val snapshot = mutable.value; mutable.update { it.copy(loading = true, error = null) }
  request = viewModelScope.launch { try {
   if(debounce) delay(300)
   val page = api.mobileJobPage(snapshot.query.trim().ifBlank { null }, snapshot.directory, offset = if(append) snapshot.jobs.size else 0, focus = snapshot.focus,
    dateField = "scheduled".takeIf { snapshot.day != null }, dateFrom = snapshot.day, dateTo = snapshot.day)
   val rows = if(append) (snapshot.jobs + page.items).distinctBy { row -> row.id } else page.items
   val ordered = if(snapshot.day == null) rows else rows.sortedBy { job ->
    try { java.time.OffsetDateTime.parse(job.scheduledAt).toInstant().epochSecond }
    catch(_: Exception) { try { java.time.LocalDateTime.parse(job.scheduledAt).toEpochSecond(java.time.ZoneOffset.UTC) } catch(_: Exception) { Long.MAX_VALUE } }
   }
   mutable.update { it.copy(loading = false, jobs = ordered, total = page.total) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load mobile jobs. ${e.userMessage()}") } } }
 }
}
