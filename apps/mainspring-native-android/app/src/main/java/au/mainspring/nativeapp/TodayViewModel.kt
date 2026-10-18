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
    private var request: Job? = null
    init { refresh() }
    fun tab(value: String) { if(value !in listOf("active","quote","booked","completed")) return; mutable.value=snapshots.today(value) ?: TodayState(tab=value); refresh() }
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
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, offlineSnapshot=it.jobs.isNotEmpty() || it.unscheduled.isNotEmpty(),error = "Could not refresh today's jobs. ${e.userMessage()}") } }
        }
    }
}
