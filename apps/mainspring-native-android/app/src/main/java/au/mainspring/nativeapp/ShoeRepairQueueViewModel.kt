package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.MainspringApi
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.api.ShoeResendRequest
import au.mainspring.nativeapp.api.ShoeSmsApi
import au.mainspring.nativeapp.api.ShoeStatusUpdate
import kotlinx.coroutines.flow.StateFlow

typealias ShoeRepairQueueUiState = QueueUiState<ShoeRepairJobRead>

/** Shoe lane calls: moves use the shoe status endpoint; notes, claim and SMS use the normal shoe job endpoints. */
internal class ShoeQueueOps(
    private val pageJobs: suspend (skip: Int) -> List<ShoeRepairJobRead>,
    private val moveStatus: suspend (id: String, status: String) -> ShoeRepairJobRead,
    private val api: () -> MainspringApi,
) : QueueOps<ShoeRepairJobRead> {
    override val mode = "shoe"
    override fun row(job: ShoeRepairJobRead) = job.toQueueRow()
    override fun nextStatus(status: String) = nextShoeQueueStatus(status)
    /** No back swipe on the shoe lane, so left means skip. */
    override fun prevStatus(status: String): String? = null
    override fun claimedByUserId(job: ShoeRepairJobRead) = job.claimedByUserId
    override suspend fun listJobs(): List<ShoeRepairJobRead> {
        val all = mutableListOf<ShoeRepairJobRead>()
        for (page in 0 until ShoeRepairQueueViewModel.MAX_PAGES) {
            val batch = pageJobs(page * ShoeRepairQueueViewModel.PAGE)
            all += batch
            if (batch.size < ShoeRepairQueueViewModel.PAGE) break
        }
        return shoeQueueEligibleJobs(all.distinctBy { it.id })
    }
    override suspend fun step(job: ShoeRepairJobRead, forward: Boolean): ShoeRepairJobRead {
        val target = (if (forward) nextShoeQueueStatus(job.status) else previousShoeQueueStatus(job.status)) ?: error("No further step for this job.")
        return moveStatus(job.id, target)
    }
    override suspend fun addNote(job: ShoeRepairJobRead, note: String) { api().postShoeRepairJobNote(job.id, JobNotePayload(note)).requireOk() }
    override suspend fun setClaim(job: ShoeRepairJobRead, claim: Boolean): ShoeRepairJobRead =
        if (claim) api().postShoeRepairJobClaim(job.id) else api().postShoeRepairJobRelease(job.id)
}

/**
 * Shoe lane of the repair queue. Moves use the existing shoe status endpoint; there is no back step, so left = skip.
 * Like the watch lane it saves the day's progress (`mode=shoe`), takes notes and "no update", claims jobs and applies
 * filters; on top of that it can text the customer a reminder (the web shows that on the shoe lane only).
 */
class ShoeRepairQueueViewModel(
    private val listJobs: suspend (skip: Int) -> List<ShoeRepairJobRead> = { ApiClient.api.listShoeRepairJobs(skip = it, limit = PAGE) },
    private val moveStatus: suspend (id: String, status: String) -> ShoeRepairJobRead = { id, status -> ApiClient.api.postShoeRepairJobStatus(id, ShoeStatusUpdate(status)) },
    private val isOnline: () -> Boolean = { ConnectivityMonitor.online.value },
    private val api: () -> MainspringApi = { ApiClient.api },
    private val smsApi: () -> ShoeSmsApi = { ApiClient.service(ShoeSmsApi::class.java) },
    dayStore: QueueDayStore = ApiQueueDayStore(),
    private val myUserId: () -> String = { runCatching { TokenStore.currentUserId() }.getOrDefault("") },
) : ViewModel() {
    private val engine = QueueEngine(viewModelScope, ShoeQueueOps(listJobs, moveStatus, api), dayStore, isOnline, OFFLINE)
    val state: StateFlow<ShoeRepairQueueUiState> = engine.state
    val userId: String get() = myUserId()

    init { engine.refresh() }

    fun refresh() = engine.refresh()
    fun dismissError() = engine.dismissError()
    fun dismissNotice() = engine.dismissNotice()
    fun advance(note: String? = null) = engine.advance(note)
    /** No back step on the shoe lane: left skips. */
    fun backOrSkip() = engine.skip()
    fun skip() = engine.skip()
    fun undo() = engine.undo()
    fun noUpdate(note: String? = null) = engine.noUpdate(note)
    fun saveNote(note: String) = engine.saveNote(note)
    fun setFilters(filters: QueueFilters) = engine.setFilters(filters)
    fun resetDay() = engine.resetDay()

    fun toggleClaim() {
        val job = state.value.current ?: return
        engine.toggleClaim(job.claimedByUserId != null && job.claimedByUserId == userId)
    }

    /** Text the customer about the job's current step ("Remind customer" / "Notify ready"). */
    fun sendReminder() {
        engine.sideAction("SMS sent") { job -> smsApi().resendShoeNotification(job.id, ShoeResendRequest("status_${job.status}")) }
    }

    override fun onCleared() { engine.flush() }

    companion object {
        const val PAGE = 200
        const val MAX_PAGES = 5
        const val OFFLINE = "You are offline. Reconnect to move jobs along the queue."
    }
}
