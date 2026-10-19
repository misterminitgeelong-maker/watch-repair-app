package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.api.TeamUser
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate

/** Sentinel technician filter key for jobs with no assignee. */
const val ROUTE_UNASSIGNED = "__unassigned__"

/** Map/route filters (web: MobileServicesMap + dispatch tech filter). Null means "all". */
fun filterRouteJobs(jobs: List<AutoKeyJobRead>, technicianId: String?, status: String?): List<AutoKeyJobRead> = jobs.filter { job ->
    (technicianId == null || (if(technicianId == ROUTE_UNASSIGNED) job.assignedUserId.isNullOrBlank() else job.assignedUserId == technicianId)) &&
        (status == null || job.status == status)
}

/** Move the element at [from] to [to]; out-of-range requests return the list unchanged. */
fun <T> moveItem(items: List<T>, from: Int, to: Int): List<T> {
    if(from !in items.indices || to !in items.indices || from == to) return items
    return items.toMutableList().also { it.add(to, it.removeAt(from)) }
}

data class RouteDayState(val day: LocalDate, val jobs: List<AutoKeyJobRead> = emptyList(), val technicians: List<TeamUser> = emptyList(),
    val loading: Boolean = false, val error: String? = null)

/** Jobs scheduled on a chosen day, for the route/map day filter. Today itself is served by TodayViewModel (offline snapshot). */
class RouteDayViewModel : ViewModel() {
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(RouteDayState(LocalDate.now()))
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { loadTechnicians() }
    private fun loadTechnicians() { viewModelScope.launch {
        try { val users = api.teamUsers().filter { it.active }; mutable.update { it.copy(technicians = users) } }
        catch(e: CancellationException) { throw e } catch(_: Exception) { /* technician filter simply stays hidden */ }
    } }
    fun setDay(day: LocalDate) { mutable.update { it.copy(day = day, jobs = emptyList()) }; refresh() }
    fun refresh() {
        request?.cancel()
        val day = mutable.value.day
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                val first = api.mobileJobPage(directory = "active", limit = 100, dateField = "scheduled", dateFrom = day.toString(), dateTo = day.toString())
                val rows = first.items.toMutableList()
                while(rows.size < first.total && rows.size < 1000) {
                    val more = api.mobileJobPage(directory = "active", limit = 100, offset = rows.size, dateField = "scheduled", dateFrom = day.toString(), dateTo = day.toString())
                    if(more.items.isEmpty()) break
                    rows.addAll(more.items)
                }
                mutable.update { it.copy(loading = false, jobs = rows.distinctBy { j -> j.id }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load jobs for that day. ${e.userMessage()}") } }
        }
    }
}
