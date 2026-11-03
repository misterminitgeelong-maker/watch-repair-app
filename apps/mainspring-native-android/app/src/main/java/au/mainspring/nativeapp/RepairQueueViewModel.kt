package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.MainspringApi
import au.mainspring.nativeapp.api.QueueSwipeBody
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.RepairQueueApi
import au.mainspring.nativeapp.api.WorkLogCreate
import au.mainspring.nativeapp.api.WorkLogRead
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import retrofit2.HttpException
import retrofit2.Response

typealias RepairQueueUiState = QueueUiState<RepairJobRead>

/** Work log history shown on the top card. */
data class QueueWorkLogs(val jobId: String? = null, val loading: Boolean = false, val logs: List<WorkLogRead> = emptyList())

/** Watch lane calls: status-only queue swipes plus notes, claim and work logs on the normal job endpoints. */
internal class WatchQueueOps(
    private val swipeApi: () -> RepairQueueApi,
    private val pageJobs: suspend (offset: Int) -> List<RepairJobRead>,
    private val api: () -> MainspringApi,
) : QueueOps<RepairJobRead> {
    override val mode = "watch"
    override fun row(job: RepairJobRead) = job.toQueueRow()
    override fun nextStatus(status: String) = previewQueueSwipe(status, "right")
    override fun prevStatus(status: String) = previewQueueSwipe(status, "left")
    override fun claimedByUserId(job: RepairJobRead) = job.claimedByUserId
    override suspend fun listJobs(): List<RepairJobRead> {
        val all = mutableListOf<RepairJobRead>()
        for (page in 0 until RepairQueueViewModel.MAX_PAGES) {
            val batch = pageJobs(page * RepairQueueViewModel.PAGE)
            all += batch
            if (batch.size < RepairQueueViewModel.PAGE) break
        }
        return queueEligibleJobs(all.distinctBy { it.id })
    }
    override suspend fun step(job: RepairJobRead, forward: Boolean): RepairJobRead =
        swipeApi().queueSwipe(job.id, QueueSwipeBody(if (forward) "right" else "left"))
    override suspend fun addNote(job: RepairJobRead, note: String) { api().postRepairJobNote(job.id, JobNotePayload(note)).requireOk() }
    override suspend fun setClaim(job: RepairJobRead, claim: Boolean): RepairJobRead =
        if (claim) api().postRepairJobClaim(job.id) else api().postRepairJobRelease(job.id)
}

/** Retrofit does not throw for HTTP errors when a call returns [Response]; surface them like every other call. */
internal fun Response<*>.requireOk() { if (!isSuccessful) throw HttpException(this) }

/**
 * Watch lane of the repair queue (web RepairQueueModal). Swipe triage with undo, notes, log work, claim, filters
 * and "no update", with today's progress saved to `me/repair-queue-day` so it survives reopening and syncs with the web.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class RepairQueueViewModel(
    private val swipeApi: () -> RepairQueueApi = { ApiClient.service(RepairQueueApi::class.java) },
    private val listJobs: suspend (offset: Int) -> List<RepairJobRead> = { ApiClient.api.listRepairJobs(limit = PAGE, offset = it) },
    private val isOnline: () -> Boolean = { ConnectivityMonitor.online.value },
    private val api: () -> MainspringApi = { ApiClient.api },
    dayStore: QueueDayStore = ApiQueueDayStore(),
    private val myUserId: () -> String = { runCatching { TokenStore.currentUserId() }.getOrDefault("") },
) : ViewModel() {
    private val engine = QueueEngine(viewModelScope, WatchQueueOps(swipeApi, listJobs, api), dayStore, isOnline, OFFLINE)
    val state: StateFlow<RepairQueueUiState> = engine.state

    private val _logs = MutableStateFlow(QueueWorkLogs())
    /** Work log history for the card on top. */
    val workLogs: StateFlow<QueueWorkLogs> = _logs.asStateFlow()

    /** The signed-in user's id, to tell a job they claimed from one claimed by someone else. */
    val userId: String get() = myUserId()

    init {
        engine.refresh()
        viewModelScope.launch {
            engine.state.map { it.current?.id }.distinctUntilChanged().collectLatest { id -> loadLogs(id) }
        }
    }

    private suspend fun loadLogs(id: String?) {
        if (id == null) { _logs.value = QueueWorkLogs(); return }
        _logs.value = QueueWorkLogs(id, loading = true)
        try {
            val logs = api().workLogs(id)
            _logs.value = QueueWorkLogs(id, logs = logs)
        } catch (e: CancellationException) { throw e }
        catch (_: Exception) { _logs.value = QueueWorkLogs(id) }
    }

    fun refresh() = engine.refresh()
    fun dismissError() = engine.dismissError()
    fun dismissNotice() = engine.dismissNotice()
    /** Swipe right; an optional [note] is saved on the job after the move. */
    fun advance(note: String? = null) = engine.advance(note)
    fun backOrSkip() = engine.backOrSkip()
    fun skip() = engine.skip()
    fun undo() = engine.undo()
    fun noUpdate(note: String? = null) = engine.noUpdate(note)
    fun saveNote(note: String) = engine.saveNote(note)
    fun setFilters(filters: QueueFilters) = engine.setFilters(filters)
    fun resetDay() = engine.resetDay()

    /** Claim the top job, or release it when the signed-in user already holds it. */
    fun toggleClaim() {
        val job = state.value.current ?: return
        engine.toggleClaim(job.claimedByUserId != null && job.claimedByUserId == userId)
    }

    /** Record time on the top job without changing its status (web "Log Work"). */
    fun logWork(note: String, minutes: Int?) {
        val text = note.trim()
        if (text.isEmpty()) return
        engine.sideAction("Work logged") { job ->
            api().createWorkLog(WorkLogCreate(job.id, text, (minutes ?: 0).coerceAtLeast(0)))
            loadLogs(job.id)
        }
    }

    override fun onCleared() { engine.flush() }

    companion object {
        const val PAGE = 100
        const val MAX_PAGES = 5
        const val OFFLINE = "You are offline. Reconnect to move jobs along the queue."
    }
}
