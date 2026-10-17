package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.QueueSwipeBody
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.RepairQueueApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** What the last triage action did, so [RepairQueueViewModel.undo] can reverse it. */
sealed class QueueAction {
    abstract val jobId: String
    /** Moved forward one step; the job left the queue. Undo swipes it back and returns it to the front. */
    data class Advanced(override val jobId: String) : QueueAction()
    /** Moved back one step; the job stayed at the front. Undo swipes it forward again. */
    data class SentBack(override val jobId: String) : QueueAction()
    /** Sent to the end of the queue locally; no server change. */
    data class Skipped(override val jobId: String) : QueueAction()
}

data class RepairQueueUiState(
    val loading: Boolean = true,
    val error: String? = null,
    /** Jobs still to triage; the first is the card on top. */
    val queue: List<RepairJobRead> = emptyList(),
    /** Jobs in the queue when it was loaded (progress denominator). */
    val total: Int = 0,
    val advanced: Int = 0,
    val skipped: Int = 0,
    val busy: Boolean = false,
    val undoStack: List<QueueAction> = emptyList(),
) {
    val current: RepairJobRead? get() = queue.firstOrNull()
    /** Cards finished this session (advanced out of the queue); skipped and sent-back cards stay in it. */
    val finished: Int get() = advanced
    val canUndo: Boolean get() = undoStack.isNotEmpty() && !busy
    val canAdvance: Boolean get() = current?.let { previewQueueSwipe(it.status, "right") } != null && !busy
    val canGoBack: Boolean get() = current?.let { previewQueueSwipe(it.status, "left") } != null && !busy
    val allDone: Boolean get() = !loading && error == null && queue.isEmpty()
}

class RepairQueueViewModel(
    private val swipeApi: () -> RepairQueueApi = { ApiClient.service(RepairQueueApi::class.java) },
    private val listJobs: suspend (offset: Int) -> List<RepairJobRead> = { ApiClient.api.listRepairJobs(limit = PAGE, offset = it) },
    private val isOnline: () -> Boolean = { ConnectivityMonitor.online.value },
) : ViewModel() {
    private val _state = MutableStateFlow(RepairQueueUiState())
    val state: StateFlow<RepairQueueUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val all = mutableListOf<RepairJobRead>()
                for (page in 0 until MAX_PAGES) {
                    val batch = listJobs(page * PAGE)
                    all += batch
                    if (batch.size < PAGE) break
                }
                val queue = queueEligibleJobs(all.distinctBy { it.id })
                _state.value = RepairQueueUiState(loading = false, queue = queue, total = queue.size)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    fun dismissError() { _state.update { it.copy(error = null) } }

    /** Swipe right: move the top job one step forward along the lane. */
    fun advance() {
        val job = _state.value.takeIf { it.canAdvance }?.current ?: return
        swipe(job, "right") { s, updated ->
            s.copy(queue = s.queue.drop(1), advanced = s.advanced + 1, undoStack = s.undoStack + QueueAction.Advanced(updated.id))
        }
    }

    /** Swipe left: step the top job back; with no earlier step it is skipped to the end of the queue instead (as on the web). */
    fun backOrSkip() {
        val s = _state.value
        if (s.busy || s.current == null) return
        if (s.canGoBack) {
            swipe(s.current!!, "left") { st, updated ->
                st.copy(queue = listOf(updated) + st.queue.drop(1), undoStack = st.undoStack + QueueAction.SentBack(updated.id))
            }
        } else skip()
    }

    /** Move the top job to the end of the queue without changing it. */
    fun skip() {
        val s = _state.value
        val job = s.current ?: return
        if (s.busy) return
        _state.update { it.copy(queue = it.queue.drop(1) + job, skipped = it.skipped + 1, undoStack = it.undoStack + QueueAction.Skipped(job.id), error = null) }
    }

    /** Reverse the most recent action. */
    fun undo() {
        val s = _state.value
        val action = s.undoStack.lastOrNull() ?: return
        if (s.busy) return
        when (action) {
            is QueueAction.Skipped -> _state.update { st ->
                val last = st.queue.lastOrNull { it.id == action.jobId }
                st.copy(
                    queue = if (last == null) st.queue else listOf(last) + st.queue.filter { it.id != action.jobId },
                    skipped = (st.skipped - 1).coerceAtLeast(0), undoStack = st.undoStack.dropLast(1),
                )
            }
            is QueueAction.Advanced -> reverse(action, "left") { st, updated ->
                st.copy(queue = listOf(updated) + st.queue, advanced = (st.advanced - 1).coerceAtLeast(0), undoStack = st.undoStack.dropLast(1))
            }
            is QueueAction.SentBack -> reverse(action, "right") { st, updated ->
                st.copy(queue = st.queue.map { if (it.id == updated.id) updated else it }, undoStack = st.undoStack.dropLast(1))
            }
        }
    }

    private fun swipe(job: RepairJobRead, direction: String, apply: (RepairQueueUiState, RepairJobRead) -> RepairQueueUiState) {
        if (!isOnline()) { _state.update { it.copy(error = OFFLINE) }; return }
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                val updated = swipeApi().queueSwipe(job.id, QueueSwipeBody(direction))
                _state.update { apply(it.copy(busy = false), updated) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    private fun reverse(action: QueueAction, direction: String, apply: (RepairQueueUiState, RepairJobRead) -> RepairQueueUiState) {
        if (!isOnline()) { _state.update { it.copy(error = OFFLINE) }; return }
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                val updated = swipeApi().queueSwipe(action.jobId, QueueSwipeBody(direction))
                _state.update { apply(it.copy(busy = false), updated) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    companion object {
        const val PAGE = 100
        const val MAX_PAGES = 5
        const val OFFLINE = "You are offline. Reconnect to move jobs along the queue."
    }
}
