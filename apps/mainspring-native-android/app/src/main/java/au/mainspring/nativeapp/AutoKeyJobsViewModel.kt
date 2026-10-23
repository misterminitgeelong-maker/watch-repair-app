package au.mainspring.nativeapp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
data class AutoKeyJobsUiState(val loading: Boolean = false, val error: String? = null, val jobs: List<AutoKeyJobRead> = emptyList(),
 val query: String = "", val directory: String = "active", val focus: String? = null, val total: Int = 0, val day: String? = null,
 val movingId: String? = null, val moveToast: au.mainspring.nativeapp.ui.screens.BoardMoveToast? = null,
 val savedViews: List<SavedJobView> = emptyList(), val selecting: Boolean = false, val selected: Set<String> = emptySet(),
 val bulkBusy: Boolean = false, val bulkMessage: String? = null, val bulkError: String? = null)

/** Saved-view encoding for mobile jobs on the shared [SavedJobView]: statusFilter = focus key, sort = directory, query = search text. */
fun mobileViewOf(directory: String, focus: String?, query: String, name: String = "") =
 SavedJobView(name, statusFilter = focus, sort = directory, query = query.ifBlank { null })
fun mobileViewToSaved(v: SavedJobView): MobileSavedView = sanitizeSavedView(MobileSavedView(v.sort ?: "active", v.statusFilter))
class AutoKeyJobsViewModel(private val persistView: Boolean = false): ViewModel() {
 companion object { fun listFactory() = object: androidx.lifecycle.ViewModelProvider.Factory {
  @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = AutoKeyJobsViewModel(true) as T
 } }
    private val api = au.mainspring.nativeapp.api.ApiClient.api
 private val restored = restoreLastView()
 private val mutable = MutableStateFlow(AutoKeyJobsUiState(directory = restored.directory, focus = restored.focus, savedViews = appSavedViews.load("mobile"))); val state = mutable.asStateFlow(); private var request: Job? = null
 init { refresh() }
 private fun lastViewKey() = TokenStore.offlineScope()?.let { "mobile_jobs_last_view:$it" }
 /** Reopen the list on the directory and focus the user last used, like the web's remembered auto-key view. */
 private fun restoreLastView(): MobileSavedView = if(!persistView) MobileSavedView() else try {
  lastViewKey()?.let { TokenStore.loadScopedString(it) }?.let { sanitizeSavedView(com.google.gson.Gson().fromJson(it, MobileSavedView::class.java)) } ?: MobileSavedView()
 } catch(_: Exception) { MobileSavedView() }
 private fun rememberView() { if(!persistView) return; val s = mutable.value; lastViewKey()?.let { TokenStore.saveScopedString(it, com.google.gson.Gson().toJson(MobileSavedView(s.directory, s.focus))) } }
 fun currentView() = mutable.value.let { mobileViewOf(it.directory, it.focus, it.query) }
 fun saveView(view: SavedJobView) { mutable.update { it.copy(savedViews = appSavedViews.save("mobile", view)) } }
 fun deleteView(name: String) { mutable.update { it.copy(savedViews = appSavedViews.delete("mobile", name)) } }
 fun applyView(v: SavedJobView) {
  val saved = mobileViewToSaved(v)
  mutable.update { it.copy(directory = saved.directory, focus = saved.focus, query = v.query.orEmpty().take(200), day = null, selected = emptySet()) }
  rememberView(); fetch(false)
 }
 fun startSelecting() { mutable.update { it.copy(selecting = true, selected = emptySet(), bulkMessage = null, bulkError = null) } }
 fun stopSelecting() { mutable.update { it.copy(selecting = false, selected = emptySet()) } }
 fun toggleSelected(id: String) { mutable.update { it.copy(selected = toggleBulkSelection(it.selected, id)) } }
 fun toggleSelectAll() { mutable.update { s -> s.copy(selected = toggleSelectAll(s.selected, s.jobs.map { it.id })) } }
 fun dismissBulkMessage() { mutable.update { it.copy(bulkMessage = null, bulkError = null) } }
 /** Sets one status on every selected job (web "Set status"). Setting a status is idempotent, so after any failure a reload shows the truth and the user may repeat it. */
 fun bulkSetStatus(status: String) {
  val s = mutable.value
  if(s.bulkBusy || !TokenStore.canWorkJobs()) return
  bulkProblem(s.selected, status)?.let { msg -> mutable.update { it.copy(bulkError = msg) }; return }
  val ids = s.jobs.map { it.id }.filter { it in s.selected }
  if(ids.isEmpty()) { mutable.update { it.copy(bulkError = "Select at least one job.") }; return }
  mutable.update { it.copy(bulkBusy = true, bulkError = null, bulkMessage = null) }
  viewModelScope.launch {
   try {
    val resp = api.bulkMobileStatus(BulkMobileStatus(ids, status))
    if(!resp.isSuccessful) throw retrofit2.HttpException(resp)
    mutable.update { it.copy(bulkBusy = false, selecting = false, selected = emptySet(), bulkMessage = "Updated ${ids.size} job${if(ids.size == 1) "" else "s"} to ${au.mainspring.nativeapp.ui.statusLabel(status)}.") }
    fetch(false)
   } catch(e: CancellationException) { throw e }
   catch(e: Exception) {
    mutable.update { it.copy(bulkBusy = false, bulkError = if(e is retrofit2.HttpException && e.code() < 500) "Could not update these jobs. ${e.userMessage()}" else "Could not confirm the update. Refresh the list to see which jobs changed, then repeat it if needed. ${e.userMessage()}") }
    fetch(false)
   }
  }
 }
 fun query(text: String) { mutable.update { it.copy(query = text.take(200)) }; fetch(false, true) }
 fun directory(value: String) { require(value in listOf("active", "completed", "all")); mutable.update { it.copy(directory = value, focus = null) }; rememberView(); fetch(false) }
 fun focus(value: String?) { mutable.update { it.copy(focus = value, day = null) }; rememberView(); fetch(false) }
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
   mutable.update { it.copy(loading = false, jobs = ordered, total = page.total, selected = pruneBulkSelection(it.selected, ordered.map { row -> row.id })) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load mobile jobs. ${e.userMessage()}") } } }
 }
}
