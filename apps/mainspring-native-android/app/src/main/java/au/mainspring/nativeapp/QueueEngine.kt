package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.QueueDayStatsDto
import au.mainspring.nativeapp.api.RepairQueueApi
import au.mainspring.nativeapp.api.RepairQueueDayPut
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.LocalDate

/** What the last triage action did, so [QueueEngine.undo] can reverse it. */
sealed class QueueAction {
    abstract val jobId: String
    /** Moved forward one step; the job left the queue. Undo steps it back and returns it to the front. */
    data class Advanced(override val jobId: String) : QueueAction()
    /** Moved back one step; the job stayed at the front. Undo steps it forward again. */
    data class SentBack(override val jobId: String) : QueueAction()
    /** Sent to the end of the queue; no server change. */
    data class Skipped(override val jobId: String) : QueueAction()
    /** Marked "No update" (a note was saved). Undo returns the job to the front; the note stays on the job. */
    data class CheckedIn(override val jobId: String) : QueueAction()
}

/** One user's queue progress for the current shop day, as stored on the server. */
data class QueueDay(val doneIds: List<String>, val orderIds: List<String>, val stats: QueueDayStats)

/** Where a lane's day progress is saved (`GET/PUT/DELETE me/repair-queue-day`). */
interface QueueDayStore {
    suspend fun load(mode: String): QueueDay
    suspend fun save(mode: String, day: QueueDay)
    suspend fun clear(mode: String)
}

/** Server-backed [QueueDayStore] so progress syncs with the web app. */
class ApiQueueDayStore(private val api: () -> RepairQueueApi = { ApiClient.service(RepairQueueApi::class.java) }) : QueueDayStore {
    override suspend fun load(mode: String): QueueDay {
        val d = api().queueDay(mode)
        return QueueDay(d.doneIds, d.queueOrderIds, QueueDayStats(d.stats.advanced, d.stats.checkedIn, d.stats.skipped))
    }
    override suspend fun save(mode: String, day: QueueDay) {
        api().putQueueDay(RepairQueueDayPut(
            mode, day.doneIds.takeLast(MAX_DONE_IDS), day.orderIds.take(MAX_ORDER_IDS),
            QueueDayStatsDto(day.stats.advanced, day.stats.checkedIn, day.stats.skipped),
        ))
    }
    override suspend fun clear(mode: String) { api().deleteQueueDay(mode) }

    companion object {
        /** Server limits on the saved lists. */
        const val MAX_DONE_IDS = 500
        const val MAX_ORDER_IDS = 2000
    }
}

/** The lane-specific calls behind a queue; watch and shoe each supply one. */
interface QueueOps<J : Any> {
    /** `watch` or `shoe`, the day-state key. */
    val mode: String
    fun row(job: J): QueueRow
    fun nextStatus(status: String): String?
    /** The status a back step goes to, or null when "back" means skip. */
    fun prevStatus(status: String): String?
    fun claimedByUserId(job: J): String?
    suspend fun listJobs(): List<J>
    suspend fun step(job: J, forward: Boolean): J
    suspend fun addNote(job: J, note: String)
    suspend fun setClaim(job: J, claim: Boolean): J
}

/** Everything the queue screen shows for one lane. */
data class QueueUiState<J : Any>(
    val loading: Boolean = true,
    val error: String? = null,
    /** A short confirmation ("Note saved") that clears itself. */
    val notice: String? = null,
    /** Every job the lane can triage, before filters. */
    val jobs: List<J> = emptyList(),
    /** Jobs still to triage for the active filters; the first is the card on top. */
    val queue: List<J> = emptyList(),
    /** Saved queue order (job ids), shared with the web app. */
    val order: List<String> = emptyList(),
    /** Jobs cleared today (advanced or marked no update). */
    val done: Set<String> = emptySet(),
    val stats: QueueDayStats = QueueDayStats(),
    val filters: QueueFilters = QueueFilters(),
    val busy: Boolean = false,
    val undoStack: List<QueueAction> = emptyList(),
    /** True once today's progress was read from the server, so changes are saved back. */
    val synced: Boolean = false,
    val canGoBackFlag: Boolean = false,
    val canAdvanceFlag: Boolean = false,
) {
    val current: J? get() = queue.firstOrNull()
    /** Cards moved forward today; skipped and sent-back cards stay in the queue. */
    val advanced: Int get() = stats.advanced
    val skipped: Int get() = stats.skipped
    val checkedIn: Int get() = stats.checkedIn
    val doneCount: Int get() = done.size
    /** Everything counted by the progress bar: cleared today plus still waiting. */
    val total: Int get() = done.size + queue.size
    val finished: Int get() = done.size
    val canUndo: Boolean get() = undoStack.isNotEmpty() && !busy
    val canAdvance: Boolean get() = canAdvanceFlag && !busy
    val canGoBack: Boolean get() = canGoBackFlag && !busy
    val allDone: Boolean get() = !loading && error == null && queue.isEmpty()
}

/** Saves run on their own scope so the last change survives leaving the screen. */
private val persistScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

/**
 * The queue state machine shared by the watch and shoe lanes: swipe triage with undo, notes, "no update",
 * claim, filters, and the per-shop-day progress that syncs with the web app. Progress is only saved once it
 * has been read from the server, so a failed read can never overwrite what the web saved.
 */
class QueueEngine<J : Any>(
    private val scope: CoroutineScope,
    private val ops: QueueOps<J>,
    private val store: QueueDayStore,
    private val isOnline: () -> Boolean,
    private val offlineMessage: String,
    private val today: () -> LocalDate = { LocalDate.now() },
    private val saveDelayMs: Long = 450,
    private val noticeMs: Long = 2500,
) {
    private val _state = MutableStateFlow(QueueUiState<J>())
    val state: StateFlow<QueueUiState<J>> = _state.asStateFlow()

    private var saveJob: Job? = null
    private val saveLock = Mutex()
    private var noticeJob: Job? = null

    private fun id(job: J) = ops.row(job).id

    private fun reduce(block: (QueueUiState<J>) -> QueueUiState<J>) { _state.update { derive(block(it)) } }

    private fun derive(s: QueueUiState<J>): QueueUiState<J> {
        val rows = s.jobs.map(ops::row)
        val visible = filterQueueRows(rows, s.filters, today()).map { it.id }.toSet()
        val byId = s.jobs.associateBy { id(it) }
        val queue = s.order.asSequence().filter { it !in s.done && it in visible }.mapNotNull { byId[it] }.toList()
        val top = queue.firstOrNull()?.let(ops::row)
        return s.copy(
            queue = queue,
            canAdvanceFlag = top != null && ops.nextStatus(top.status) != null,
            canGoBackFlag = top != null && ops.prevStatus(top.status) != null,
        )
    }

    fun refresh() {
        reduce { it.copy(loading = true, error = null) }
        scope.launch {
            try {
                flushNow()
                val jobs = ops.listJobs()
                val day = try { store.load(ops.mode) } catch (e: CancellationException) { throw e } catch (_: Exception) { null }
                val before = _state.value
                val done = day?.doneIds?.toCollection(LinkedHashSet()) ?: before.done
                val stats = day?.stats ?: before.stats
                val order = mergeQueueOrder(day?.orderIds ?: before.order, jobs.map(ops::row), today())
                reduce { it.copy(loading = false, jobs = jobs, order = order, done = done, stats = stats, undoStack = emptyList(), synced = day != null) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { reduce { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    fun dismissError() { reduce { it.copy(error = null) } }
    fun dismissNotice() { reduce { it.copy(notice = null) } }

    private fun showNotice(text: String) {
        reduce { it.copy(notice = text) }
        noticeJob?.cancel()
        noticeJob = scope.launch { delay(noticeMs); reduce { s -> if (s.notice == text) s.copy(notice = null) else s } }
    }

    fun setFilters(filters: QueueFilters) { reduce { it.copy(filters = filters) } }

    // ── Saving ──────────────────────────────────────────────────────────────────

    private fun scheduleSave() {
        if (!_state.value.synced) return
        saveJob?.cancel()
        saveJob = persistScope.launch { delay(saveDelayMs); sendSave() }
    }

    private suspend fun sendSave() {
        val s = _state.value
        saveLock.withLock {
            try { store.save(ops.mode, QueueDay(s.done.toList(), s.order, s.stats)) }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { /* offline: the next change tries again */ }
        }
    }

    private suspend fun flushNow() {
        val pending = saveJob?.takeIf { it.isActive } ?: return
        pending.cancel()
        sendSave()
    }

    /** Send any unsaved progress now; call when the screen goes away. */
    fun flush() {
        if (saveJob?.isActive != true) return
        saveJob?.cancel()
        persistScope.launch { sendSave() }
    }

    /** Forget today's saved progress (web "Reset today's queue progress"). */
    fun resetDay() {
        if (!isOnline()) { reduce { it.copy(error = offlineMessage) }; return }
        saveJob?.cancel()
        reduce { it.copy(busy = true, error = null) }
        scope.launch {
            try {
                store.clear(ops.mode)
                val order = mergeQueueOrder(null, _state.value.jobs.map(ops::row), today())
                reduce { it.copy(busy = false, order = order, done = emptySet(), stats = QueueDayStats(), undoStack = emptyList(), synced = true) }
                showNotice("Today's progress cleared")
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { reduce { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    // ── Triage ──────────────────────────────────────────────────────────────────

    /** Swipe right: move the top job one step forward; an optional [note] is saved on the job afterwards. */
    fun advance(note: String? = null) {
        val s = _state.value
        val job = s.takeIf { it.canAdvance }?.current ?: return
        runStep(job, forward = true, note = note?.trim()?.takeIf { it.isNotEmpty() }) { st, updated ->
            st.copy(
                jobs = st.jobs.replaced(updated), done = st.done + id(updated),
                stats = st.stats.copy(advanced = st.stats.advanced + 1), undoStack = st.undoStack + QueueAction.Advanced(id(updated)),
            )
        }
    }

    /** Swipe left: step the top job back; with no earlier step it is skipped to the end of the queue instead (as on the web). */
    fun backOrSkip() {
        val s = _state.value
        val job = s.current ?: return
        if (s.busy) return
        if (s.canGoBack) {
            runStep(job, forward = false) { st, updated ->
                st.copy(jobs = st.jobs.replaced(updated), order = moveToFront(st.order, id(updated)), undoStack = st.undoStack + QueueAction.SentBack(id(updated)))
            }
        } else skip()
    }

    /** Move the top job to the end of the queue without changing it. */
    fun skip() {
        val s = _state.value
        val job = s.current ?: return
        if (s.busy) return
        reduce {
            it.copy(
                order = moveToBack(it.order, id(job)), stats = it.stats.copy(skipped = it.stats.skipped + 1),
                undoStack = it.undoStack + QueueAction.Skipped(id(job)), error = null,
            )
        }
        scheduleSave()
    }

    /** Mark the top job "checked in - no update": a note is saved and the job is cleared for the day. */
    fun noUpdate(note: String? = null) {
        val job = _state.value.takeIf { !it.busy }?.current ?: return
        if (!isOnline()) { reduce { it.copy(error = offlineMessage) }; return }
        reduce { it.copy(busy = true, error = null) }
        scope.launch {
            try {
                ops.addNote(job, note?.trim().takeUnless { it.isNullOrEmpty() } ?: QUEUE_DEFAULT_CHECKED_IN_NOTE)
                reduce {
                    it.copy(
                        busy = false, done = it.done + id(job), stats = it.stats.copy(checkedIn = it.stats.checkedIn + 1),
                        undoStack = it.undoStack + QueueAction.CheckedIn(id(job)),
                    )
                }
                scheduleSave()
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { reduce { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    /** Save a note on the top job without changing its status. */
    fun saveNote(note: String) {
        val text = note.trim()
        if (text.isEmpty()) return
        sideAction("Note saved") { job -> ops.addNote(job, text) }
    }

    /** Claim the top job for the signed-in user, or release it when [mine]. */
    fun toggleClaim(mine: Boolean) {
        val job = _state.value.takeIf { !it.busy }?.current ?: return
        if (!isOnline()) { reduce { it.copy(error = offlineMessage) }; return }
        reduce { it.copy(busy = true, error = null) }
        scope.launch {
            try {
                val updated = ops.setClaim(job, !mine)
                reduce { it.copy(busy = false, jobs = it.jobs.replaced(updated)) }
                showNotice(if (mine) "Released" else "Claimed")
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { reduce { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    /**
     * Run a server call for the top job that does not move it (note, log work, SMS reminder).
     * Shows [success] on completion or the error message on failure.
     */
    fun sideAction(success: String, block: suspend (J) -> Unit) {
        val job = _state.value.takeIf { !it.busy }?.current ?: return
        if (!isOnline()) { reduce { it.copy(error = offlineMessage) }; return }
        reduce { it.copy(busy = true, error = null) }
        scope.launch {
            try {
                block(job)
                reduce { it.copy(busy = false) }
                showNotice(success)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { reduce { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    /** Reverse the most recent action. */
    fun undo() {
        val s = _state.value
        val action = s.undoStack.lastOrNull() ?: return
        if (s.busy) return
        when (action) {
            is QueueAction.Skipped -> {
                reduce { st ->
                    st.copy(order = moveToFront(st.order, action.jobId), stats = st.stats.copy(skipped = (st.stats.skipped - 1).coerceAtLeast(0)), undoStack = st.undoStack.dropLast(1))
                }
                scheduleSave()
            }
            is QueueAction.CheckedIn -> {
                reduce { st ->
                    st.copy(
                        done = st.done - action.jobId, order = moveToFront(st.order, action.jobId),
                        stats = st.stats.copy(checkedIn = (st.stats.checkedIn - 1).coerceAtLeast(0)), undoStack = st.undoStack.dropLast(1),
                    )
                }
                scheduleSave()
            }
            is QueueAction.Advanced -> {
                val job = s.jobs.firstOrNull { id(it) == action.jobId } ?: return
                runStep(job, forward = false) { st, updated ->
                    st.copy(
                        jobs = st.jobs.replaced(updated), done = st.done - action.jobId, order = moveToFront(st.order, action.jobId),
                        stats = st.stats.copy(advanced = (st.stats.advanced - 1).coerceAtLeast(0)), undoStack = st.undoStack.dropLast(1),
                    )
                }
            }
            is QueueAction.SentBack -> {
                val job = s.jobs.firstOrNull { id(it) == action.jobId } ?: return
                runStep(job, forward = true) { st, updated -> st.copy(jobs = st.jobs.replaced(updated), undoStack = st.undoStack.dropLast(1)) }
            }
        }
    }

    private fun runStep(job: J, forward: Boolean, note: String? = null, apply: (QueueUiState<J>, J) -> QueueUiState<J>) {
        if (!isOnline()) { reduce { it.copy(error = offlineMessage) }; return }
        reduce { it.copy(busy = true, error = null) }
        scope.launch {
            try {
                val updated = ops.step(job, forward)
                reduce { apply(it.copy(busy = false), updated) }
                scheduleSave()
                if (note != null) {
                    try { ops.addNote(updated, note) }
                    catch (e: CancellationException) { throw e }
                    catch (e: Exception) { reduce { it.copy(error = "Moved, but the note was not saved: " + e.userMessage()) } }
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { reduce { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    private fun List<J>.replaced(updated: J): List<J> = map { if (id(it) == id(updated)) updated else it }
}
