package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.api.ShoeStatusUpdate
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** What the last shoe triage action did, so [ShoeRepairQueueViewModel.undo] can reverse it. */
sealed class ShoeQueueAction {
    abstract val jobId: String
    /** Moved forward from [fromStatus]; the job left the queue. Undo sets [fromStatus] back and returns it to the front. */
    data class Advanced(override val jobId: String, val fromStatus: String) : ShoeQueueAction()
    /** Sent to the end of the queue locally; no server change. */
    data class Skipped(override val jobId: String) : ShoeQueueAction()
}

data class ShoeRepairQueueUiState(
    val loading: Boolean = true,
    val error: String? = null,
    val queue: List<ShoeRepairJobRead> = emptyList(),
    val total: Int = 0,
    val advanced: Int = 0,
    val skipped: Int = 0,
    val busy: Boolean = false,
    val undoStack: List<ShoeQueueAction> = emptyList(),
) {
    val current: ShoeRepairJobRead? get() = queue.firstOrNull()
    val canUndo: Boolean get() = undoStack.isNotEmpty() && !busy
    val canAdvance: Boolean get() = current?.let { nextShoeQueueStatus(it.status) } != null && !busy
}

/** Shoe lane of the repair queue. Moves use the existing shoe status endpoint; there is no back step, so left = skip. */
class ShoeRepairQueueViewModel(
    private val listJobs: suspend (skip: Int) -> List<ShoeRepairJobRead> = { ApiClient.api.listShoeRepairJobs(skip = it, limit = PAGE) },
    private val moveStatus: suspend (id: String, status: String) -> ShoeRepairJobRead = { id, status -> ApiClient.api.postShoeRepairJobStatus(id, ShoeStatusUpdate(status)) },
    private val isOnline: () -> Boolean = { ConnectivityMonitor.online.value },
) : ViewModel() {
    private val _state = MutableStateFlow(ShoeRepairQueueUiState())
    val state: StateFlow<ShoeRepairQueueUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val all = mutableListOf<ShoeRepairJobRead>()
                for (page in 0 until MAX_PAGES) {
                    val batch = listJobs(page * PAGE)
                    all += batch
                    if (batch.size < PAGE) break
                }
                val queue = shoeQueueEligibleJobs(all.distinctBy { it.id })
                _state.value = ShoeRepairQueueUiState(loading = false, queue = queue, total = queue.size)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    fun dismissError() { _state.update { it.copy(error = null) } }

    /** Swipe right: move the top job to its next status. */
    fun advance() {
        val job = _state.value.takeIf { it.canAdvance }?.current ?: return
        val next = nextShoeQueueStatus(job.status) ?: return
        move(job.id, next) { s, _ ->
            s.copy(queue = s.queue.drop(1), advanced = s.advanced + 1, undoStack = s.undoStack + ShoeQueueAction.Advanced(job.id, job.status))
        }
    }

    /** Swipe left: no back step on the shoe lane, so this skips to the end of the queue. */
    fun backOrSkip() = skip()

    fun skip() {
        val s = _state.value
        val job = s.current ?: return
        if (s.busy) return
        _state.update { it.copy(queue = it.queue.drop(1) + job, skipped = it.skipped + 1, undoStack = it.undoStack + ShoeQueueAction.Skipped(job.id), error = null) }
    }

    fun undo() {
        val s = _state.value
        val action = s.undoStack.lastOrNull() ?: return
        if (s.busy) return
        when (action) {
            is ShoeQueueAction.Skipped -> _state.update { st ->
                val last = st.queue.lastOrNull { it.id == action.jobId }
                st.copy(
                    queue = if (last == null) st.queue else listOf(last) + st.queue.filter { it.id != action.jobId },
                    skipped = (st.skipped - 1).coerceAtLeast(0), undoStack = st.undoStack.dropLast(1),
                )
            }
            is ShoeQueueAction.Advanced -> move(action.jobId, action.fromStatus) { st, updated ->
                st.copy(queue = listOf(updated) + st.queue, advanced = (st.advanced - 1).coerceAtLeast(0), undoStack = st.undoStack.dropLast(1))
            }
        }
    }

    private fun move(id: String, status: String, apply: (ShoeRepairQueueUiState, ShoeRepairJobRead) -> ShoeRepairQueueUiState) {
        if (!isOnline()) { _state.update { it.copy(error = OFFLINE) }; return }
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                val updated = moveStatus(id, status)
                _state.update { apply(it.copy(busy = false), updated) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { _state.update { it.copy(busy = false, error = e.userMessage()) } }
        }
    }

    companion object {
        const val PAGE = 200
        const val MAX_PAGES = 5
        const val OFFLINE = "You are offline. Reconnect to move jobs along the queue."
    }
}
