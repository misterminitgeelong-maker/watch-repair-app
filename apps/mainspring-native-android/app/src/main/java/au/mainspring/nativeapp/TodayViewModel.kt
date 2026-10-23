package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.*

data class TodayState(val loading: Boolean = true, val error: String? = null, val offlineSnapshot: Boolean = false, val jobs: List<AutoKeyJobRead> = emptyList(),
    val unscheduled: List<AutoKeyJobRead> = emptyList(), val todayCount: Int? = null, val unscheduledCount: Int? = null,
    val unpaidCount: Int? = null, val tab: String = "active", val truncated: Boolean = false)

/** Run-sheet extras that are not part of the offline snapshot: jobs in the field, late jobs, needs-action counts and the one-tap status write. */
data class RunSheetState(val field: List<AutoKeyJobRead> = emptyList(), val lateIds: Set<String> = emptySet(), val counts: Map<String, Int> = emptyMap(),
    val movingId: String? = null, val info: String? = null, val error: String? = null)

fun bookingInstant(value: String?): Instant? = value?.let {
    try { OffsetDateTime.parse(it).toInstant() } catch(_: Exception) {
        try { LocalDateTime.parse(it).toInstant(ZoneOffset.UTC) } catch(_: Exception) { null }
    }
}

class TodayViewModel : ViewModel() {
    private val api = ApiClient.api
    private val drafts=TokenStore.bindDrafts()
    private val snapshots=FieldSnapshots(drafts)
    private val mutable = MutableStateFlow(snapshots.today("active") ?: TodayState())
    val state=mutable.asStateFlow()
    private val runMutable = MutableStateFlow(RunSheetState())
    val runSheet = runMutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }
    fun tab(value: String) { if(value !in listOf("active","quote","booked","completed")) return; mutable.value=snapshots.today(value) ?: TodayState(tab=value); refresh() }
    /** Best effort: the run sheet still works from the booked-today list when these extra queues cannot be read. */
    private suspend fun loadRunSheetExtras() {
        val late = try { api.mobileJobPage(directory = "active", focus = "late", limit = 100) } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
        val inField = try { api.mobileJobPage(directory = "active", focus = "in_field", limit = 100) } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
        val unassigned = try { api.mobileJobPage(directory = "active", focus = "unassigned", limit = 1) } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
        val onHold = try { api.mobileJobPage(directory = "active", focus = "on_hold", limit = 1) } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
        val counts = buildMap<String, Int> {
            late?.let { put("late", it.total) }; unassigned?.let { put("unassigned", it.total) }; onHold?.let { put("on_hold", it.total) }
            mutable.value.unscheduledCount?.let { put("unscheduled", it) }
        }
        runMutable.update { it.copy(field = (inField?.items.orEmpty() + late?.items.orEmpty()).distinctBy { j -> j.id }, lateIds = late?.items.orEmpty().map { j -> j.id }.toSet(), counts = counts) }
    }
    /** One-tap Start trip / Arrived / Complete. Uses the same versioned status endpoint as the job screen; a network failure is queued. */
    fun advance(jobId: String, target: String) {
        if(runMutable.value.movingId != null || !TokenStore.canWorkJobs()) return
        val job = (mutable.value.jobs + runMutable.value.field + mutable.value.unscheduled).firstOrNull { it.id == jobId } ?: return
        if(nextMobileStatus(job.status) != target) return
        runMutable.update { it.copy(movingId = jobId, error = null, info = null) }
        viewModelScope.launch {
            try {
                val updated = api.postAutoKeyJobStatus(jobId, RepairJobStatusUpdate(status = target, note = null), job.updatedAt)
                snapshots.saveJob(updated)
                replaceJob(updated)
                runMutable.update { it.copy(movingId = null, info = if(updated.invoiceCreated == true) "Status saved. An invoice was created." else "Status saved.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                if(au.mainspring.nativeapp.offline.OfflineSync.queueStatus(e, au.mainspring.nativeapp.offline.OfflineKinds.MOBILE_STATUS, jobId, target, null, null, "Mobile job", expectedUpdatedAt = job.updatedAt)) {
                    replaceJob(job.copy(status = target))
                    runMutable.update { it.copy(movingId = null, info = au.mainspring.nativeapp.offline.OfflineSync.SAVED_OFFLINE_MESSAGE) }
                } else runMutable.update { it.copy(movingId = null, error = "Could not update this job. ${e.userMessage()}") }
            }
        }
    }
    fun dismissRunSheetMessage() { runMutable.update { it.copy(info = null, error = null) } }
    private fun replaceJob(updated: AutoKeyJobRead) {
        mutable.update { s -> s.copy(jobs = s.jobs.map { if(it.id == updated.id) updated else it }, unscheduled = s.unscheduled.map { if(it.id == updated.id) updated else it }) }
        runMutable.update { s -> s.copy(field = s.field.map { if(it.id == updated.id) updated else it }) }
    }
    fun refresh() {
        request?.cancel()
        val tab = mutable.value.tab
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                coroutineScope {
                    val today = async { api.mobileJobPage(directory = "active", focus = "today", limit = 100) }
                    val unscheduled = async { api.mobileJobPage(directory = "active", focus = "unscheduled", limit = 25) }
                    val unpaid = async { api.mobileJobPage(directory = "completed", focus = "completed_unpaid", limit = 1) }
                    val first = when(tab) {
                        "quote" -> api.mobileJobPage(directory = "active", focus = "needs_quote", limit = 100)
                        "completed" -> api.mobileJobPage(directory = "completed", focus = "completed_unpaid", limit = 100)
                        else -> today.await()
                    }
                    val rows = first.items.toMutableList()
                    while(rows.size < first.total && rows.size < 1000) {
                        val more = api.mobileJobPage(directory = if(tab == "completed") "completed" else "active",
                            focus = when(tab) { "quote" -> "needs_quote"; "completed" -> "completed_unpaid"; else -> "today" }, limit = 100, offset = rows.size)
                        if(more.items.isEmpty()) break
                        rows.addAll(more.items)
                    }
                    val scheduled = rows.distinctBy { it.id }.filter { tab != "booked" || it.status in setOf("booked","booking_confirmed") }
                        .sortedBy { bookingInstant(it.scheduledAt) ?: Instant.MAX }
                    val u = unscheduled.await()
                    // Save the offline copy before announcing the result, so anything that reacts to loading=false can rely on it being stored.
                    val next = mutable.value.copy(loading = false, offlineSnapshot=false,jobs = scheduled, unscheduled = u.items, todayCount = today.await().total,
                        unscheduledCount = u.total, unpaidCount = unpaid.await().total, truncated = rows.size < first.total)
                    snapshots.saveToday(tab,next)
                    mutable.value = next
                    if(tab == "active") loadRunSheetExtras()
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, offlineSnapshot=it.jobs.isNotEmpty() || it.unscheduled.isNotEmpty(),error = "Could not refresh today's jobs. ${e.userMessage()}") } }
        }
    }
}
